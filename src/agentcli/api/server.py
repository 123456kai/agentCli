from __future__ import annotations

from queue import Queue
from pathlib import Path
from threading import Thread
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from agentcli.agent_loop import AgentLoop
from agentcli.api.schemas import RunRequest, RunResponse, TourResponse, TourStep
from agentcli.engine.events import AgentEvent
from agentcli.llm.adapter import DeepSeekOpenAIAdapter
from agentcli.repo_guard import enumerate_repo_files
from agentcli.runtime import build_runtime
from agentcli.tools.read_file import read_file
from agentcli.tools.search_files import search_files

WEB_ROOT = Path(__file__).resolve().parents[3] / "web"


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


def create_app(repo_root: Path, adapter_factory=None) -> FastAPI:
    app = FastAPI(title="agentCli Web Workbench")
    resolved_repo = repo_root.resolve()
    runs: dict[str, "RunStream"] = {}
    dist_assets = WEB_ROOT / "dist" / "assets"
    if dist_assets.exists():
        app.mount("/assets", StaticFiles(directory=dist_assets), name="assets")
    elif WEB_ROOT.exists():
        app.mount("/web", StaticFiles(directory=WEB_ROOT), name="web")

    class RunStream:
        def __init__(self) -> None:
            self.events: list[AgentEvent] = []
            self.queue: Queue[AgentEvent | None] = Queue()
            self.answer = ""

        def emit(self, event_type: str, *, run_id: str, **payload: object) -> AgentEvent:
            event = AgentEvent(type=event_type, run_id=run_id, payload=dict(payload))
            self.events.append(event)
            self.queue.put(event)
            if event.type == "run_finished":
                self.queue.put(None)
            return event

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _load_web_index()

    @app.post("/api/runs", response_model=RunResponse)
    def create_run(request: RunRequest) -> RunResponse:
        run_id = uuid4().hex
        stream = RunStream()
        runs[run_id] = stream

        def _worker() -> None:
            runtime = build_runtime(resolved_repo)
            factory = adapter_factory or (lambda: _default_adapter_factory(runtime))
            loop = AgentLoop(runtime=runtime, adapter=factory(), event_sink=stream, run_id=run_id)
            try:
                stream.answer = loop.run(request.question)
            except Exception as exc:
                stream.emit("run_error", run_id=run_id, error=str(exc))
                stream.emit("run_finished", run_id=run_id, status="failed")

        Thread(target=_worker, daemon=True).start()
        return RunResponse(run_id=run_id, answer="")

    @app.post("/api/runs/sync", response_model=RunResponse)
    def create_run_sync(request: RunRequest) -> RunResponse:
        run_id = uuid4().hex
        stream = RunStream()
        runs[run_id] = stream
        runtime = build_runtime(resolved_repo)
        factory = adapter_factory or (lambda: _default_adapter_factory(runtime))
        loop = AgentLoop(runtime=runtime, adapter=factory(), event_sink=stream, run_id=run_id)
        answer = loop.run(request.question)
        stream.answer = answer
        return RunResponse(run_id=run_id, answer=answer)

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
                "matches": files[:500],
                "total_matches": len(files),
                "truncated": len(files) > 500,
            }
        return search_files(resolved_repo, pattern)

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
        import json

        runtime = build_runtime(resolved_repo)
        factory = adapter_factory or (lambda: _default_adapter_factory(runtime))
        loop = AgentLoop(runtime=runtime, adapter=factory())
        raw = loop.run(_TOUR_PROMPT)

        try:
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1]
                if raw.endswith("```"):
                    raw = raw[:-3]
            data = json.loads(raw)
            steps = [TourStep(**s) for s in data.get("steps", [])]
            return TourResponse(title=data.get("title", "Code Tour"), steps=steps)
        except (json.JSONDecodeError, TypeError, ValueError):
            return TourResponse(
                title="Code Tour",
                steps=[
                    TourStep(
                        order=1, title="Tour Overview", file="",
                        description=raw[:500],
                        next_read=None, key_lines=None,
                    )
                ],
            )

    return app
