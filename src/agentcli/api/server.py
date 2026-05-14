from __future__ import annotations

import json
from pathlib import Path
from queue import Queue
from threading import Event, Lock, Thread
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from agentcli.agent_loop import AgentLoop
from agentcli.analysis import parse_analysis_result
from agentcli.analysis.graph import build_graph_index, expand_call_node, get_node_detail
from agentcli.api.schemas import (
    ExpandResponse,
    GraphEdge,
    GraphNode,
    NodeDetailResponse,
    ProjectResponse,
    RunRequest,
    RunResponse,
    SaveNoteRequest,
    SaveNoteResponse,
    SessionResponse,
    SkeletonResponse,
    TourResponse,
    TourStep,
)
from agentcli.config import resolve_config
from agentcli.engine.events import AgentEvent
from agentcli.llm.adapter import DeepSeekOpenAIAdapter
from agentcli.notes import make_note_slug, render_note
from agentcli.repo_guard import enumerate_repo_files
from agentcli.runtime import build_runtime
from agentcli.session import AnalysisSession
from agentcli.session_store import SessionStore
from agentcli.tools.read_file import read_file
from agentcli.tools.save_note import save_note
from agentcli.tools.search_files import search_files

WEB_ROOT = Path(__file__).resolve().parents[3] / "web"
FILE_LIST_LIMIT = 500


def _default_adapter_factory(runtime):
    return DeepSeekOpenAIAdapter(
        api_key=runtime.llm.api_key,
        base_url=runtime.llm.base_url,
        model=runtime.llm.model,
    )


def _load_web_index() -> str:
    dist_index = WEB_ROOT / "dist" / "index.html"
    if dist_index.exists():
        return dist_index.read_text(encoding="utf-8")
    source_index = WEB_ROOT / "index.html"
    if source_index.exists():
        return source_index.read_text(encoding="utf-8")
    return "<!doctype html><title>agentCli Web</title><div id='root'>agentCli Web</div>"


def _build_runtime(repo_root: Path):
    config = resolve_config(repo_root)
    return build_runtime(
        repo_root,
        model=config.model,
        base_url=config.base_url,
        max_steps=config.max_steps,
        read_max_lines=config.read_max_lines,
    )


def _resolve_notes_dir(repo_root: Path) -> Path:
    config = resolve_config(repo_root)
    if not config.note_output_dir:
        return repo_root / "notes"
    candidate = Path(config.note_output_dir)
    if candidate.is_absolute():
        return candidate
    return repo_root / candidate


def create_app(repo_root: Path, adapter_factory=None) -> FastAPI:
    app = FastAPI(title="agentCli Web Workbench")
    resolved_repo = repo_root.resolve()
    session_store = SessionStore(resolved_repo)
    runs: dict[str, "RunStream"] = {}
    graph_cache: dict[str, object] = {"signature": None, "index": None}
    dist_index = WEB_ROOT / "dist" / "index.html"
    dist_assets = WEB_ROOT / "dist" / "assets"
    if dist_index.exists():
        if dist_assets.exists():
            app.mount("/assets", StaticFiles(directory=dist_assets), name="assets")
    elif WEB_ROOT.exists():
        app.mount("/web", StaticFiles(directory=WEB_ROOT), name="web")

    class RunStream:
        def __init__(self) -> None:
            self.events: list[AgentEvent] = []
            self.queue: Queue[AgentEvent | None] = Queue()
            self.answer = ""
            self.cancel_event = Event()
            self._lock = Lock()
            self.terminal_emitted = False

        def emit(self, event_type: str, *, run_id: str, **payload: object) -> AgentEvent:
            with self._lock:
                if event_type == "run_finished":
                    if self.terminal_emitted:
                        return AgentEvent(type=event_type, run_id=run_id, payload=dict(payload))
                    self.terminal_emitted = True
                event = AgentEvent(type=event_type, run_id=run_id, payload=dict(payload))
                self.events.append(event)
                self.queue.put(event)
                if event.type == "run_finished":
                    self.queue.put(None)
                return event

        def cancel(self, run_id: str) -> None:
            self.cancel_event.set()
            self.emit("run_finished", run_id=run_id, status="cancelled")

        def is_cancelled(self) -> bool:
            return self.cancel_event.is_set()

    def _resolve_session(session_id: str | None) -> AnalysisSession:
        if session_id:
            session = session_store.load(session_id)
            if session is None:
                raise HTTPException(status_code=404, detail="session not found")
            return session
        return AnalysisSession.new(resolved_repo)

    def _repo_graph_signature() -> tuple[tuple[str, int, int], ...]:
        signature: list[tuple[str, int, int]] = []
        for rel_path in enumerate_repo_files(resolved_repo):
            if not rel_path.endswith(".py"):
                continue
            path = resolved_repo / rel_path
            try:
                stat = path.stat()
            except OSError:
                continue
            signature.append((rel_path, int(stat.st_mtime_ns), int(stat.st_size)))
        return tuple(signature)

    def _get_graph_index() -> dict[str, object]:
        signature = _repo_graph_signature()
        if graph_cache["signature"] != signature:
            graph_cache["signature"] = signature
            graph_cache["index"] = build_graph_index(resolved_repo)
        return graph_cache["index"]  # type: ignore[return-value]

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _load_web_index()

    @app.get("/api/project", response_model=ProjectResponse)
    def get_project() -> ProjectResponse:
        files = enumerate_repo_files(resolved_repo)
        runtime = _build_runtime(resolved_repo)
        return ProjectResponse(
            repo_root=resolved_repo.as_posix(),
            name=resolved_repo.name,
            model=runtime.llm.model,
            file_count=len(files),
            truncated=len(files) > FILE_LIST_LIMIT,
        )

    @app.post("/api/sessions", response_model=SessionResponse)
    def create_session() -> SessionResponse:
        session = AnalysisSession.new(resolved_repo)
        session_store.save(session)
        return SessionResponse(session_id=session.session_id)

    @app.get("/api/sessions/latest", response_model=SessionResponse)
    def get_latest_session() -> SessionResponse:
        session = session_store.load_latest()
        return SessionResponse(session_id=session.session_id if session else None)

    @app.post("/api/notes", response_model=SaveNoteResponse)
    def create_note(request: SaveNoteRequest) -> SaveNoteResponse:
        analysis = parse_analysis_result(request.answer)
        question = request.title or request.question
        note_path = save_note(
            _resolve_notes_dir(resolved_repo),
            make_note_slug(question),
            render_note(
                question,
                analysis.conclusion,
                key_files=analysis.key_files,
                reading_order=analysis.reading_order,
                uncertainties=analysis.uncertainties,
            ),
        )
        return SaveNoteResponse(note_path=str(note_path))

    @app.post("/api/runs", response_model=RunResponse)
    def create_run(request: RunRequest) -> RunResponse:
        run_id = uuid4().hex
        stream = RunStream()
        runs[run_id] = stream
        session = _resolve_session(request.session_id)

        def _worker() -> None:
            runtime = _build_runtime(resolved_repo)
            factory = adapter_factory or (lambda: _default_adapter_factory(runtime))
            loop = AgentLoop(
                runtime=runtime,
                adapter=factory(),
                event_sink=stream,
                run_id=run_id,
                should_cancel=stream.is_cancelled,
            )
            try:
                stream.answer = loop.run_turn(session, request.question)
                session_store.save(session)
            except Exception as exc:
                if stream.is_cancelled():
                    return
                stream.emit("run_error", run_id=run_id, error=str(exc))
                stream.emit("run_finished", run_id=run_id, status="failed")

        Thread(target=_worker, daemon=True).start()
        return RunResponse(run_id=run_id, answer="", session_id=session.session_id)

    @app.post("/api/runs/sync", response_model=RunResponse)
    def create_run_sync(request: RunRequest) -> RunResponse:
        run_id = uuid4().hex
        stream = RunStream()
        runs[run_id] = stream
        session = _resolve_session(request.session_id)
        runtime = _build_runtime(resolved_repo)
        factory = adapter_factory or (lambda: _default_adapter_factory(runtime))
        loop = AgentLoop(
            runtime=runtime,
            adapter=factory(),
            event_sink=stream,
            run_id=run_id,
            should_cancel=stream.is_cancelled,
        )
        answer = loop.run_turn(session, request.question)
        session_store.save(session)
        stream.answer = answer
        return RunResponse(run_id=run_id, answer=answer, session_id=session.session_id)

    @app.get("/api/runs/{run_id}/events")
    def run_events(run_id: str) -> StreamingResponse:
        stream = runs.get(run_id)
        if stream is None:
            raise HTTPException(status_code=404, detail="run not found")

        def _iter_events():
            sent = 0
            sent_ids: set[str] = set()
            while sent < len(stream.events):
                event = stream.events[sent]
                sent_ids.add(event.id)
                yield event.to_sse()
                sent += 1
            while True:
                event = stream.queue.get()
                if event is None:
                    break
                if event.id in sent_ids:
                    continue
                sent_ids.add(event.id)
                yield event.to_sse()

        return StreamingResponse(_iter_events(), media_type="text/event-stream")

    @app.post("/api/runs/{run_id}/cancel")
    def cancel_run(run_id: str) -> dict[str, str]:
        stream = runs.get(run_id)
        if stream is None:
            raise HTTPException(status_code=404, detail="run not found")
        stream.cancel(run_id)
        return {"status": "cancelled"}

    @app.get("/api/file")
    def get_file(path: str = Query(...), line_offset: int = 1, n_lines: int = 1000) -> dict[str, object]:
        result = read_file(resolved_repo, path, line_offset=line_offset, n_lines=n_lines)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result)
        return result

    @app.get("/api/files")
    def get_files(pattern: str = "") -> dict[str, object]:
        if not pattern:
            files = enumerate_repo_files(resolved_repo)
            return {
                "kind": "file_listing",
                "pattern": "",
                "matches": files[:FILE_LIST_LIMIT],
                "total_matches": len(files),
                "truncated": len(files) > FILE_LIST_LIMIT,
            }
        return search_files(resolved_repo, pattern)

    @app.get("/api/graph/skeleton", response_model=SkeletonResponse)
    def get_graph_skeleton() -> SkeletonResponse:
        index = _get_graph_index()
        return SkeletonResponse(
            nodes=[GraphNode(**node) for node in index["nodes_by_id"].values()],
            edges=[GraphEdge(**edge) for edge in index["edges"]],
            warning=index.get("warning"),
            skipped_files=list(index.get("skipped_files", [])),
        )

    @app.get("/api/graph/expand", response_model=ExpandResponse)
    def get_graph_expand(node_id: str = Query(...), depth: int = Query(3, ge=1, le=5)) -> ExpandResponse:
        result = expand_call_node(resolved_repo, node_id, depth)
        return ExpandResponse(
            root=str(result["root"]),
            nodes=[GraphNode(**node) for node in result["nodes"]],
            edges=[GraphEdge(**edge) for edge in result["edges"]],
        )

    @app.get("/api/graph/node", response_model=NodeDetailResponse)
    def get_graph_node(node_id: str = Query(...)) -> NodeDetailResponse:
        result = get_node_detail(resolved_repo, node_id)
        node = result["node"]
        return NodeDetailResponse(
            node=GraphNode(**node) if node else None,
            incoming=[GraphEdge(**edge) for edge in result["incoming"]],
            outgoing=[GraphEdge(**edge) for edge in result["outgoing"]],
        )

    _TOUR_PROMPT = """\
你正在给一位第一次看这个代码库的开发者做导览。请用中文回答。

按以下步骤探索：
1. 扫描项目结构（list_directory），了解整体布局
2. 找到并阅读入口文件（CLI 入口、main 函数、app 启动点）
3. 追踪主流程在代码库中的执行路径
4. 识别 5-8 个关键文件，解释它们的角色
5. 为每个文件标注"接下来该看什么"及原因

探索完成后，只返回一个 JSON 对象（不要 markdown，不要额外文字），结构如下：
{
  "title": "<项目名> 代码导览",
  "steps": [
    {
      "order": 1,
      "title": "入口：<简短标签>",
      "file": "relative/path/to/file.py",
      "description": "这个文件做什么、为什么重要、能学到什么。控制在2-3句话，中文。",
      "next_read": {"file": "relative/path/to/next.py", "reason": "因为它被 xxx 调用"},
      "key_lines": "10-45"
    }
  ]
}

规则：
- 每一步聚焦一个文件
- 流程逻辑：入口 → 核心引擎 → 支撑模块 → 配置/工具
- next_read.file 必须是仓库中真实存在的文件
- key_lines 是可选的 — 只有需要高亮特定区域时才填
- 总共 5-8 步
- 描述用中文，简明易懂，1-2 句话
- JSON 必须有效 — 使用双引号，不要尾部逗号"""

    @app.post("/api/tour", response_model=TourResponse)
    def create_tour() -> TourResponse:
        runtime = _build_runtime(resolved_repo)
        factory = adapter_factory or (lambda: _default_adapter_factory(runtime))
        loop = AgentLoop(runtime=runtime, adapter=factory())
        raw = loop.run(_TOUR_PROMPT)

        try:
            payload = raw.strip()
            if payload.startswith("```"):
                payload = payload.split("\n", 1)[1]
                if payload.endswith("```"):
                    payload = payload[:-3]
            data = json.loads(payload)
            steps = [TourStep(**s) for s in data.get("steps", [])]
            return TourResponse(title=data.get("title", "Code Tour"), steps=steps)
        except (json.JSONDecodeError, TypeError, ValueError):
            return TourResponse(
                title="Code Tour",
                warning="tour_parse_failed",
                steps=[
                    TourStep(
                        order=1,
                        title="Tour Overview",
                        file="",
                        description=raw[:500],
                        next_read=None,
                        key_lines=None,
                    )
                ],
            )

    return app
