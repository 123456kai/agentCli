from __future__ import annotations

from queue import Queue
from pathlib import Path
from threading import Thread
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from agentcli.agent_loop import AgentLoop
from agentcli.api.schemas import RunRequest, RunResponse
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

    return app
