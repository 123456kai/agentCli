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
    CodeTutorStartRequest,
    CodeTutorMessageRequest,
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

    # ---- CodeTutor endpoints ----

    from agentcli.codetutor import (
        CodeTutorSession,
        CodeTutorContext,
        CODETUTOR_OVERVIEW_PROMPT,
        CODETUTOR_SYSTEM_PROMPT,
        CODETUTOR_DIRECTION_SWITCH_PROMPT,
    )
    from agentcli.codetutor.context import TutorMessage
    from agentcli.analysis.storyline import _analyze_project_domains

    _codetutor_sessions: dict[str, CodeTutorSession] = {}

    def _get_or_load_codetutor_session(session_id: str) -> CodeTutorSession | None:
        if session_id in _codetutor_sessions:
            return _codetutor_sessions[session_id]
        session = CodeTutorSession.load(resolved_repo, session_id)
        if session:
            _codetutor_sessions[session_id] = session
        return session

    @app.post("/api/codetutor/start")
    def codetutor_start(request: CodeTutorStartRequest):
        """Start a CodeTutor session for a domain. Returns overview message."""
        domains = _analyze_project_domains(resolved_repo, None)
        domain = next((d for d in domains if str(d.get("id")) == request.domain_id), None)
        if not domain:
            raise HTTPException(status_code=404, detail="domain not found")

        session = CodeTutorSession.new(
            resolved_repo,
            request.domain_id,
            str(domain.get("name", "")),
            str(domain.get("description", "")),
        )
        session.save_state()
        _codetutor_sessions[session.session_id] = session

        domain_files = domain.get("files", [])
        files_str = ", ".join([str(f) for f in domain_files[:10]])

        try:
            runtime = _build_runtime(resolved_repo)
            factory = adapter_factory or (lambda: _default_adapter_factory(runtime))
            adapter = factory()
            prompt = CODETUTOR_OVERVIEW_PROMPT.format(
                domain_name=session.domain_name,
                domain_description=session.domain_description,
                domain_files=files_str,
            )
            overview_text = adapter.chat_sync(prompt)
        except Exception:
            overview_text = (
                f"欢迎来到 **{session.domain_name}** 领域。{session.domain_description}\n"
                f"涉及的核心文件包括：{files_str}。\n"
                f"要不要我打开第一个文件，带你看看从哪里开始？"
            )

        ctx = session.get_context()
        msg = TutorMessage(
            role="tutor",
            content=overview_text,
            code_ref=None,
            branch_id="main",
            parent_index=-1,
        )
        ctx.append_message(msg)
        ctx.checkpoint(label=f"领域入口: {session.domain_name}")

        return {
            "session_id": session.session_id,
            "message": msg.to_dict(),
            "breadcrumbs": ctx.get_breadcrumbs(session.domain_name),
        }

    @app.post("/api/codetutor/message")
    def codetutor_message(request: CodeTutorMessageRequest):
        """Process a user message and return the tutor's response."""
        session = _get_or_load_codetutor_session(request.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="session not found")

        ctx = session.get_context()
        index = _get_graph_index()
        nodes_by_id = index["nodes_by_id"]

        active_msgs = ctx.get_active_messages()
        parent_index = len(active_msgs) - 1 if active_msgs else -1
        user_msg = TutorMessage(
            role="user",
            content=request.message,
            branch_id="main",
            parent_index=parent_index,
        )
        ctx.append_message(user_msg)

        user_text = request.message.strip()
        is_confirm = user_text in (
            "好", "继续", "嗯", "对", "是的", "可以", "行",
            "ok", "OK", "yes", "go", "next",
        )
        is_direction_switch = any(
            kw in user_text
            for kw in ["看", "换", "跳", "去", "打开", "讲讲", "解释"]
        )

        try:
            runtime = _build_runtime(resolved_repo)
            factory = adapter_factory or (lambda: _default_adapter_factory(runtime))
            adapter = factory()
        except Exception:
            fallback_msg = TutorMessage(
                role="tutor",
                content="AI 服务暂不可用，请稍后重试。",
                branch_id="main",
                parent_index=len(ctx.get_active_messages()) - 1,
            )
            ctx.append_message(fallback_msg)
            return {
                "session_id": session.session_id,
                "message": fallback_msg.to_dict(),
                "breadcrumbs": ctx.get_breadcrumbs(session.domain_name),
            }

        if is_direction_switch and not is_confirm:
            response = _codetutor_handle_direction_switch(
                user_text, session, ctx, index, adapter,
                nodes_by_id, resolved_repo,
            )
        else:
            response = _codetutor_handle_advance(
                user_text, is_confirm, session, ctx, index, adapter,
                nodes_by_id, resolved_repo,
            )

        tutor_msg = TutorMessage(
            role="tutor",
            content=response["content"],
            code_ref=response.get("code_ref"),
            branch_id="main",
            parent_index=len(ctx.get_active_messages()) - 1,
        )
        ctx.append_message(tutor_msg)

        if response.get("code_ref"):
            cr = response["code_ref"]
            session.current_file = str(cr.get("file_path", ""))
            session.current_line_start = int(cr.get("line_start", 0))
            session.current_line_end = int(cr.get("line_end", 0))
            session.save_state()

        ctx.checkpoint(label=f"反问: {session.current_file or '概括'}")

        return {
            "session_id": session.session_id,
            "message": tutor_msg.to_dict(),
            "breadcrumbs": ctx.get_breadcrumbs(session.domain_name),
        }

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

        # Gather related definitions from the codebase
        current_file = str(node.get("path", ""))
        related_context = _gather_related_definitions(resolved_repo, code_snippet, current_file, request.question)

        system_prompt = (
            "你是一个代码阅读助手，正在帮开发者理解一段具体的源码。\n\n"
            "规则：\n"
            "- 优先基于上面给出的源码回答。如果附加了相关函数的源码，可以引用它们来给出更完整的解释。\n"
            "- 回答控制在 4-8 句话，直接、精炼。\n"
            "- 引用代码位置时直接写 文件路径:起始行-结束行（例如直接写 src/agentcli/agent_loop.py:42-56），不要用反引号或任何 Markdown 语法包裹它。它可以被自动识别为可点击链接。\n"
            "- 不要编造代码——只引用上下文里实际存在的代码。\n"
            "- 可以使用简短的 Markdown（代码块、加粗、列表）提升可读性，但代码块不超过 15 行。\n"
            "- 用中文回答。"
        )
        context = (
            f"{system_prompt}\n\n"
            f"当前文件: {current_file}\n"
            f"当前代码:\n```python\n{code_snippet}\n```\n"
        )
        if related_context:
            context += f"\n相关函数/类的源码（来自代码库其他位置）:\n{related_context}\n"
        context += f"\n用户问题: {request.question}"

        try:
            runtime = _build_runtime(resolved_repo)
            factory = adapter_factory or (
                lambda: _default_adapter_factory(runtime)
            )
            adapter = factory()
            answer = adapter.chat_sync(context)
        except Exception:
            answer = "AI 问答暂不可用，请稍后重试。"

        source_refs = _extract_code_refs(answer, related_context, current_file)
        return NodeAskResponse(answer=answer, source_refs=source_refs, debug_context=context)

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

    def _extract_code_refs(answer: str, related_context: str = "", current_file: str = "") -> list[dict[str, object]]:
        """Extract code references from AI answer and related context.

        Scans for patterns like `path/to/file.py:42-56` or `path/to/file.py:42`
        and returns structured {path, line_start, line_end} dicts.
        """
        import re
        refs: list[dict[str, object]] = []
        seen: set[tuple[str, int, int]] = set()

        # Pattern 1: path/to/file.py:42-56 (line range)
        for m in re.finditer(r"([\w/\-.]+\.\w{1,6}):(\d+)-(\d+)", answer):
            path = m.group(1)
            start = int(m.group(2))
            end = int(m.group(3))
            key = (path, start, end)
            if key not in seen:
                seen.add(key)
                refs.append({"path": path, "line_start": start, "line_end": end})

        # Pattern 2: path/to/file.py:42 (single line)
        for m in re.finditer(r"([\w/\-.]+\.\w{1,6}):(\d+)(?![-\d])", answer):
            path = m.group(1)
            line = int(m.group(2))
            key = (path, line, line)
            if key not in seen:
                seen.add(key)
                refs.append({"path": path, "line_start": line, "line_end": line})

        # Pattern 3: extract from related_context (e.g. "定义于 src/.../file.py:42")
        for m in re.finditer(r"定义于\s+([\w/\-.]+\.\w{1,6}):(\d+)", related_context):
            path = m.group(1)
            line = int(m.group(2))
            key = (path, line, line)
            if key not in seen:
                seen.add(key)
                refs.append({"path": path, "line_start": line, "line_end": line})

        # Dedup: merge same-path refs, preferring range refs over single-line
        merged: dict[str, dict[str, object]] = {}
        for ref in refs:
            p = str(ref["path"])
            if p in merged:
                existing = merged[p]
                # If either is a range (start != end), keep the range; else keep existing
                if existing["line_start"] == existing["line_end"] and ref["line_start"] != ref["line_end"]:
                    merged[p] = ref
            else:
                merged[p] = ref

        # If no refs found, at least include the current file context
        if not merged and current_file:
            merged[current_file] = {"path": current_file, "line_start": 1, "line_end": 1}

        return list(merged.values())[:6]

    def _gather_related_definitions(repo_root: Path, code_snippet: str, current_file: str = "", user_question: str = "") -> str:
        """Extract referenced symbols from code, find their definitions in the repo,
        and return formatted source code for inclusion in LLM context.

        Skips definitions in the same file as the current code snippet.
        Symbols mentioned in user_question are prioritized first.
        """
        import ast
        import re
        import textwrap
        from agentcli.analysis.symbols import find_definitions

        _BUILTINS = {
            "print", "len", "range", "int", "str", "float", "bool", "list", "dict",
            "set", "tuple", "type", "isinstance", "hasattr", "getattr", "setattr",
            "open", "enumerate", "zip", "map", "filter", "sorted", "reversed",
            "min", "max", "sum", "any", "all", "abs", "round",
            "True", "False", "None", "self", "cls", "super", "Exception",
            "Path", "os", "json", "re", "sys", "datetime", "time",
        }

        # Extract function-call symbols from code snippet (regex first for robustness)
        symbols: set[str] = set()
        for m in re.finditer(r"\b([a-z_][a-z0-9_]{2,})\s*\(", code_snippet):
            symbols.add(m.group(1))
        # AST pass for attribute calls (obj.method)
        try:
            tree = ast.parse(textwrap.dedent(code_snippet))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    symbols.add(node.func.attr)
        except (SyntaxError, ValueError):
            pass

        # Filter builtins and private symbols (starts with _)
        symbols = {s for s in symbols if s not in _BUILTINS and not s.startswith("_")}
        if not symbols:
            return ""

        # Extract identifiers from user question to prioritize relevant symbols
        question_lower = user_question.lower()
        question_symbols: set[str] = set()
        for m in re.finditer(r"\b([a-z_][a-z0-9_]{2,})\b", question_lower):
            question_symbols.add(m.group(1))

        MAX_CHUNKS = 5
        current_file_normalized = current_file.replace("\\", "/")

        def _priority(sym: str) -> tuple[int, int, str]:
            # Tier 0: symbol mentioned in user question → highest priority
            # Tier 1: symbol NOT in question
            # Sub-tier: cross-file (1) > same-file (2) > no-match (3)
            in_question = 0 if sym in question_symbols or sym.lower() in question_symbols else 1
            result = find_definitions(repo_root, sym)
            for m in result.get("matches", []):
                path = str(m.get("path", "")).replace("\\", "/")
                if path == current_file_normalized:
                    return (in_question, 2, sym)
                return (in_question, 1, sym)
            return (in_question, 3, sym)

        chunks: list[str] = []
        for sym in sorted(symbols, key=_priority)[:15]:
            if len(chunks) >= MAX_CHUNKS:
                break
            result = find_definitions(repo_root, sym)
            matches = result.get("matches", [])
            if not matches:
                continue
            for match in matches[:1]:
                match_path = str(match.get("path", "")).replace("\\", "/")
                if match_path == current_file_normalized:
                    continue
                fpath = repo_root / str(match.get("path", ""))
                if not fpath.exists():
                    continue
                try:
                    lines = fpath.read_text(encoding="utf-8").splitlines()
                except (UnicodeDecodeError, OSError):
                    continue
                line_no = int(match.get("line", 1))
                start = max(0, line_no - 1)
                end = min(len(lines), start + 40)
                snippet = "\n".join(
                    f"{start + i + 1}: {ln}"
                    for i, ln in enumerate(lines[start:end])
                )
                kind = match.get("kind", "function")
                chunks.append(
                    f"### {kind} `{sym}` 定义于 {match.get('path', '')}:{line_no}\n"
                    f"```python\n{snippet}\n```"
                )

        return "\n\n".join(chunks)

    def _codetutor_handle_advance(
        user_text: str,
        is_confirm: bool,
        session: CodeTutorSession,
        ctx: CodeTutorContext,
        index: dict,
        adapter,
        nodes_by_id: dict,
        repo_root: Path,
    ) -> dict:
        """Handle confirm/advance or free-form question from user."""
        from agentcli.analysis.storyline import _read_node_source, _resolve_line_end

        visited = ctx.get_visited_nodes()
        breadcrumbs = ctx.get_breadcrumbs(session.domain_name)

        last_code_ref = None
        for m in reversed(ctx.get_active_messages()):
            if m.role == "tutor" and m.code_ref:
                last_code_ref = m.code_ref
                break

        next_candidates: list[dict[str, object]] = []
        if last_code_ref:
            node_id = str(last_code_ref.get("graph_node_id", ""))
            edges = index["edges"]
            for edge in edges:
                if str(edge["source"]) == node_id:
                    target = nodes_by_id.get(str(edge["target"]))
                    if target and str(target.get("kind")) != "external":
                        next_candidates.append({
                            "node_id": str(edge["target"]),
                            "label": str(target.get("label", "")),
                            "path": str(target.get("path", "")),
                        })
                    if len(next_candidates) >= 5:
                        break

        if is_confirm and last_code_ref and next_candidates:
            target = next_candidates[0]
            node = nodes_by_id.get(str(target["node_id"]))
            if node:
                file_path = repo_root / str(node["path"])
                line_start = int(node["line"])
                code = _read_node_source(repo_root, node)
                prompt = CODETUTOR_SYSTEM_PROMPT.format(
                    domain_name=session.domain_name,
                    domain_description=session.domain_description,
                    file_path=str(node["path"]),
                    line_start=line_start,
                    line_end=line_start,
                    visited_summary="\n".join(
                        [f"- {v['node']}: {v['summary']}" for v in visited]
                    ),
                    breadcrumbs=breadcrumbs,
                    code_snippet=code,
                )
                raw = adapter.chat_sync(prompt)
                return {
                    "content": raw.strip(),
                    "code_ref": {
                        "file_path": str(node["path"]),
                        "line_start": line_start,
                        "line_end": _resolve_line_end(file_path, line_start),
                        "graph_node_id": str(node["id"]),
                    },
                }

        prompt = (
            f"你是一位代码导游。学生正在阅读\"{session.domain_name}\"领域的代码。\n\n"
            f"当前路径: {breadcrumbs}\n\n"
            f"学生说: \"{user_text}\"\n\n"
            f"请直接回答问题，如果学生是在提问代码相关的具体问题，给出简洁的解答（2-4句话）。"
            f"结尾反问学生是否要继续原来的方向。\n\n"
            f"只返回纯文本。"
        )
        raw = adapter.chat_sync(prompt)
        return {"content": raw.strip(), "code_ref": None}

    def _codetutor_handle_direction_switch(
        user_text: str,
        session: CodeTutorSession,
        ctx: CodeTutorContext,
        index: dict,
        adapter,
        nodes_by_id: dict,
        repo_root: Path,
    ) -> dict:
        """Handle user direction switch (e.g. '我想看XXX')."""
        from agentcli.analysis.storyline import _read_node_source, _resolve_line_end

        visited = ctx.get_visited_nodes()
        breadcrumbs = ctx.get_breadcrumbs(session.domain_name)

        available: list[dict[str, object]] = []
        for v in visited[-8:]:
            nid = v.get("node", "")
            if nid in nodes_by_id:
                available.append({
                    "node_id": nid,
                    "label": str(nodes_by_id[nid].get("label", "")),
                    "path": str(nodes_by_id[nid].get("path", "")),
                })
        if len(available) < 5:
            for nid, node in list(nodes_by_id.items())[:30]:
                if str(node.get("kind")) != "external":
                    available.append({
                        "node_id": nid,
                        "label": str(node.get("label", "")),
                        "path": str(node.get("path", "")),
                    })

        prompt = CODETUTOR_DIRECTION_SWITCH_PROMPT.format(
            breadcrumbs=breadcrumbs,
            visited_summary="\n".join(
                [f"- {v['node']}: {v['summary']}" for v in visited]
            ),
            user_message=user_text,
            available_nodes=json.dumps(available, ensure_ascii=False, indent=2),
        )
        raw = adapter.chat_sync(prompt)

        code_ref = None
        content = raw.strip()
        if content.startswith("CODE_REF:"):
            lines = content.split("\n", 1)
            try:
                code_ref = json.loads(lines[0][9:].strip())
            except json.JSONDecodeError:
                pass
            content = lines[1].strip() if len(lines) > 1 else content

        if code_ref:
            fpath = repo_root / str(code_ref.get("file_path", ""))
            code_ref["line_end"] = _resolve_line_end(
                fpath, int(code_ref.get("line_start", 0))
            )

        return {"content": content, "code_ref": code_ref}

    return app
