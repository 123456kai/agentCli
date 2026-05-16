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
    NodeAskRequest,
    NodeAskResponse,
    NodeDetailResponse,
    ProjectResponse,
    RunRequest,
    RunResponse,
    SaveNoteRequest,
    SaveNoteResponse,
    SessionResponse,
    SkeletonResponse,
    StorylineDetailResponse,
    StorylineGenerateRequest,
    StorylineGenerateResponse,
    StorylineListResponse,
    StorylineNodeResponse,
    StorylineNodeSchema,
    StorylineSchema,
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

    # ---- Storyline endpoints ----

    from agentcli.analysis.storyline import (
        discover_storylines,
        generate_node_narrative,
        _read_node_source,
        _file_content_hash,
        _generate_progressive_narrative,
        _build_entry_summary,
    )
    from agentcli.analysis.cache import NarrativeCache, make_cache_key

    _narrative_cache = NarrativeCache(resolved_repo / ".agentcli" / "storyline-cache")
    _storyline_cache: dict[str, object] = {"storylines": None, "signature": None}

    def _graph_signature() -> str:
        if graph_cache["signature"] is not None:
            return str(graph_cache["signature"])
        return "fresh"

    def _storylines_from_index(
        index: dict[str, object],
        adapter_factory=None,
    ) -> list[dict[str, object]]:
        raw = discover_storylines(
            resolved_repo, index, adapter_factory=adapter_factory,
        )
        result: list[dict[str, object]] = []
        for s in raw:
            result.append({
                "id": s.id,
                "title": s.title,
                "description": s.description,
                "theme": s.theme,
                "nodes": [
                    {
                        "order": n.order,
                        "title": n.title,
                        "file_path": n.file_path,
                        "line_start": n.line_start,
                        "line_end": n.line_end,
                        "graph_node_id": n.graph_node_id,
                        "summary": n.summary,
                        "design_notes": n.design_notes,
                        "warnings": n.warnings,
                        "next_teaser": n.next_teaser,
                    }
                    for n in s.nodes
                ],
                "node_count": s.node_count,
                "estimated_minutes": s.estimated_minutes,
                "file_count": s.file_count,
            })
        return result

    @app.get("/api/storylines", response_model=StorylineListResponse)
    def list_storylines() -> StorylineListResponse:
        index = _get_graph_index()
        sig = _graph_signature()
        if _storyline_cache["storylines"] is not None and _storyline_cache["signature"] == sig:
            return StorylineListResponse(
                storylines=[StorylineSchema(**s) for s in _storyline_cache["storylines"]]
            )
        raw = _storylines_from_index(index)
        _storyline_cache["storylines"] = raw
        _storyline_cache["signature"] = sig
        return StorylineListResponse(
            storylines=[StorylineSchema(**s) for s in raw]
        )

    @app.get("/api/storylines/{storyline_id}", response_model=StorylineDetailResponse)
    def get_storyline(storyline_id: str) -> StorylineDetailResponse:
        index = _get_graph_index()
        raw_list = _storylines_from_index(index)
        match = next((s for s in raw_list if s["id"] == storyline_id), None)
        if not match:
            raise HTTPException(status_code=404, detail="storyline not found")
        return StorylineDetailResponse(**match)

    @app.get("/api/storylines/{storyline_id}/enhance")
    def enhance_storyline(storyline_id: str):
        index = _get_graph_index()
        raw_list = _storylines_from_index(index)
        match = next((s for s in raw_list if s["id"] == storyline_id), None)
        if not match:
            raise HTTPException(status_code=404, detail="storyline not found")

        storyline_title = str(match["title"])
        nodes = list(match["nodes"])
        runtime = _build_runtime(resolved_repo)
        factory = adapter_factory or (lambda: _default_adapter_factory(runtime))

        def _iter_events():
            yield f"data: {json.dumps({'type': 'enhancement_start', 'storyline_id': storyline_id, 'total_nodes': len(nodes)}, ensure_ascii=False)}\n\n"

            prev_nodes: list[dict[str, str]] = []
            for i, node in enumerate(nodes):
                graph_node_id = str(node["graph_node_id"])
                try:
                    adapter = factory()
                    narrative = _generate_progressive_narrative(
                        resolved_repo,
                        graph_node_id,
                        index,
                        storyline_title=storyline_title,
                        prev_nodes=prev_nodes if prev_nodes else None,
                        cache=_narrative_cache,
                        adapter=adapter,
                    )
                    enhanced = {
                        "graph_node_id": graph_node_id,
                        "order": node.get("order", i),
                        "summary": narrative.summary,
                        "design_notes": narrative.design_notes,
                        "warnings": narrative.warnings,
                        "next_teaser": narrative.next_teaser,
                    }
                    prev_nodes.append({
                        "role": str(node.get("title", "")),
                        "summary": narrative.summary,
                    })
                except Exception as exc:
                    enhanced = {
                        "graph_node_id": graph_node_id,
                        "order": node.get("order", i),
                        "summary": node.get("summary") or "",
                        "design_notes": node.get("design_notes") or "",
                        "warnings": node.get("warnings"),
                        "next_teaser": node.get("next_teaser"),
                        "error": str(exc),
                    }

                yield f"data: {json.dumps({'type': 'node_enhanced', 'node': enhanced}, ensure_ascii=False, default=str)}\n\n"

            yield f"data: {json.dumps({'type': 'enhancement_complete', 'storyline_id': storyline_id}, ensure_ascii=False)}\n\n"

        return StreamingResponse(_iter_events(), media_type="text/event-stream")

    @app.get(
        "/api/storylines/{storyline_id}/nodes/{node_id:path}",
        response_model=StorylineNodeResponse,
    )
    def get_storyline_node(storyline_id: str, node_id: str) -> StorylineNodeResponse:
        index = _get_graph_index()
        raw_list = _storylines_from_index(index)
        match = next((s for s in raw_list if s["id"] == storyline_id), None)
        if not match:
            raise HTTPException(status_code=404, detail="storyline not found")

        node_match = next(
            (n for n in match["nodes"] if n["graph_node_id"] == node_id), None
        )
        if not node_match:
            raise HTTPException(status_code=404, detail="node not found in storyline")

        storyline_title = str(match.get("title", ""))
        storyline_nodes = list(match.get("nodes", []))

        # Build previous-nodes context for progressive narrative
        prev_nodes: list[dict[str, str]] = []
        for n in storyline_nodes:
            if n["graph_node_id"] == node_id:
                break
            prev_nodes.append({
                "role": str(n.get("title", "")),
                "summary": str(n.get("summary", "")),
            })

        nodes_by_id = index["nodes_by_id"]
        graph_node = nodes_by_id.get(node_id)

        source_code = ""
        if graph_node:
            file_path = resolved_repo / str(graph_node["path"])
            if file_path.exists():
                try:
                    lines = file_path.read_text(encoding="utf-8").splitlines()
                    start = max(0, int(graph_node["line"]) - 1)
                    end = min(len(lines), start + 50)
                    source_code = "\n".join(lines[start:end])
                except (OSError, UnicodeDecodeError):
                    source_code = f"# Cannot read: {graph_node['path']}"

        narrative: dict[str, str | None] | None = None
        if graph_node:
            fpath = resolved_repo / str(graph_node["path"])
            content_hash = (
                _file_content_hash(fpath) if fpath.exists() else "external"
            )
            cache_key = make_cache_key(
                str(graph_node["path"]),
                content_hash,
                int(graph_node["line"]),
                int(graph_node["line"]),
            )
            cached = _narrative_cache.get(cache_key)
            if cached:
                narrative = {
                    "summary": str(cached.get("summary", "")),
                    "design_notes": str(cached.get("design_notes", "")),
                    "warnings": (
                        cached.get("warnings") if cached.get("warnings") else None
                    ),
                    "next_teaser": (
                        cached.get("next_teaser") if cached.get("next_teaser") else None
                    ),
                }
            else:
                # Generate narrative with progressive context
                try:
                    runtime = _build_runtime(resolved_repo)
                    factory = adapter_factory or (
                        lambda: _default_adapter_factory(runtime)
                    )
                    adapter = factory()
                    node_narrative = _generate_progressive_narrative(
                        resolved_repo, node_id, index,
                        storyline_title=storyline_title,
                        prev_nodes=prev_nodes if prev_nodes else None,
                        cache=_narrative_cache,
                        adapter=adapter,
                    )
                    narrative = {
                        "summary": node_narrative.summary,
                        "design_notes": node_narrative.design_notes,
                        "warnings": node_narrative.warnings,
                        "next_teaser": node_narrative.next_teaser,
                    }
                except Exception:
                    narrative = {
                        "summary": str(node_match.get("summary", "")),
                        "design_notes": str(node_match.get("design_notes", "")),
                        "warnings": node_match.get("warnings"),
                        "next_teaser": node_match.get("next_teaser"),
                    }

        return StorylineNodeResponse(
            node=StorylineNodeSchema(**node_match),
            source_code=source_code,
            narrative=narrative,
        )

    @app.post("/api/storylines/generate", response_model=StorylineGenerateResponse)
    def generate_storyline(
        request: StorylineGenerateRequest,
    ) -> StorylineGenerateResponse:
        index = _get_graph_index()
        entry_nodes = _build_entry_summary(index)
        entries_json = json.dumps(entry_nodes, ensure_ascii=False, indent=2)

        from agentcli.prompts.storyline import STAGE4_STORYLINE_GENERATION

        prompt = STAGE4_STORYLINE_GENERATION.format(
            entry_nodes=entries_json,
            description=request.description,
        )

        nodes_by_id = index["nodes_by_id"]
        storyline = None

        try:
            runtime = _build_runtime(resolved_repo)
            factory = adapter_factory or (
                lambda: _default_adapter_factory(runtime)
            )
            adapter = factory()
            raw = adapter.chat_sync(prompt)
            data = json.loads(raw.strip())

            nodes: list[dict[str, object]] = []
            for ns in data.get("node_sequence", []):
                gid = str(ns.get("graph_node_id", ""))
                graph_node = nodes_by_id.get(gid, {})
                nodes.append({
                    "order": int(ns.get("order", len(nodes))),
                    "title": str(ns.get("role_title", graph_node.get("label", ""))),
                    "file_path": str(ns.get("file_path", graph_node.get("path", ""))),
                    "line_start": int(graph_node.get("line", 0)),
                    "line_end": int(graph_node.get("line", 0)),
                    "graph_node_id": gid,
                })

            if len(nodes) >= 2:
                import hashlib
                sid = hashlib.sha256(request.description.encode()).hexdigest()[:12]
                storyline = {
                    "id": sid,
                    "title": str(data.get("title", "自定义路径")),
                    "description": str(data.get("description", request.description)),
                    "theme": str(data.get("theme", "custom")),
                    "nodes": nodes,
                    "node_count": len(nodes),
                    "estimated_minutes": max(1, len(nodes)),
                    "file_count": len({n["file_path"] for n in nodes}),
                }
        except Exception:
            pass

        if storyline is None:
            raw_list = _storylines_from_index(index)
            if raw_list:
                storyline = raw_list[0]
            else:
                raise HTTPException(status_code=400, detail="no storylines available")

        return StorylineGenerateResponse(
            storyline=StorylineSchema(**storyline),
            status="ready",
        )

    @app.post(
        "/api/storylines/{storyline_id}/nodes/{node_id:path}/ask",
        response_model=NodeAskResponse,
    )
    def ask_node(
        storyline_id: str, node_id: str, request: NodeAskRequest
    ) -> NodeAskResponse:
        index = _get_graph_index()
        nodes_by_id = index["nodes_by_id"]
        node = nodes_by_id.get(node_id)
        if not node:
            raise HTTPException(status_code=404, detail="node not found")

        code_snippet = _read_node_source(resolved_repo, node)
        context = (
            f"当前代码:\n```python\n{code_snippet}\n```\n\n"
            f"用户问题: {request.question}"
        )

        try:
            runtime = _build_runtime(resolved_repo)
            factory = adapter_factory or (
                lambda: _default_adapter_factory(runtime)
            )
            adapter = factory()
            answer = adapter.chat_sync(context)
        except Exception:
            answer = "AI 问答暂不可用，请稍后重试。"

        return NodeAskResponse(answer=answer, source_refs=[])

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
