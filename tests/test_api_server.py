import json
import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from agentcli.api.server import create_app


class FakeAdapter:
    def __init__(self) -> None:
        self.calls = 0

    def respond(self, messages, tools):
        self.calls += 1
        if self.calls == 1:
            return {
                "type": "tool_call",
                "tool_name": "read_file",
                "arguments": {"path": "src/main.py", "line_offset": 1, "n_lines": 1},
                "tool_call_id": "call_read",
            }
        return {"type": "final", "content": "## Conclusion\nThe app starts in src/main.py."}


def test_api_run_endpoint_exposes_sse_events(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    client = TestClient(create_app(tmp_path, adapter_factory=lambda: FakeAdapter()))

    response = client.post("/api/runs", json={"question": "Where does it start?"})

    assert response.status_code == 200
    run_id = response.json()["run_id"]
    assert response.json()["session_id"]

    events = client.get(f"/api/runs/{run_id}/events")
    assert events.status_code == 200
    assert events.headers["content-type"].startswith("text/event-stream")
    assert "event: file_opened" in events.text
    assert "event: answer_final" in events.text


def test_api_file_endpoint_uses_safe_reader(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    client = TestClient(create_app(tmp_path, adapter_factory=lambda: FakeAdapter()))

    response = client.get("/api/file", params={"path": "src/main.py"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["path"] == "src/main.py"
    assert "print('hi')" in payload["content"]


def test_web_static_entry_includes_react_and_monaco(tmp_path: Path) -> None:
    app = create_app(tmp_path, adapter_factory=lambda: FakeAdapter())
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert ('src="/src/main.tsx"' in response.text) or ('href="/assets/' in response.text)


def test_web_static_entry_prefers_built_dist(tmp_path: Path, monkeypatch) -> None:
    import agentcli.api.server as server

    web_root = tmp_path / "web"
    dist = web_root / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id=\"built-root\"></div>", encoding="utf-8")
    monkeypatch.setattr(server, "WEB_ROOT", web_root)

    app = create_app(tmp_path, adapter_factory=lambda: FakeAdapter())
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "built-root" in response.text


def test_web_server_does_not_expose_source_tree_when_dist_exists(tmp_path: Path, monkeypatch) -> None:
    import agentcli.api.server as server

    web_root = tmp_path / "web"
    dist = web_root / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id=\"built-root\"></div>", encoding="utf-8")
    (web_root / "package.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(server, "WEB_ROOT", web_root)

    app = create_app(tmp_path, adapter_factory=lambda: FakeAdapter())
    client = TestClient(app)

    response = client.get("/web/package.json")

    assert response.status_code == 404


def test_api_files_endpoint_allows_empty_pattern_for_file_explorer(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    client = TestClient(create_app(tmp_path, adapter_factory=lambda: FakeAdapter()))

    response = client.get("/api/files")

    assert response.status_code == 200
    payload = response.json()
    assert payload["kind"] == "file_listing"
    assert "src/main.py" in payload["matches"]


def test_api_project_endpoint_exposes_runtime_metadata(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    client = TestClient(create_app(tmp_path, adapter_factory=lambda: FakeAdapter()))

    response = client.get("/api/project")

    assert response.status_code == 200
    payload = response.json()
    assert payload["repo_root"] == tmp_path.resolve().as_posix()
    assert payload["name"] == tmp_path.name
    assert payload["file_count"] >= 1
    assert "model" in payload


def test_api_session_endpoints_create_and_load_latest(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path, adapter_factory=lambda: FakeAdapter()))

    created = client.post("/api/sessions")
    latest = client.get("/api/sessions/latest")

    assert created.status_code == 200
    assert latest.status_code == 200
    assert latest.json()["session_id"] == created.json()["session_id"]


def test_api_runs_sync_reuses_session_across_turns(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    client = TestClient(create_app(tmp_path, adapter_factory=lambda: FakeAdapter()))

    session_id = client.post("/api/sessions").json()["session_id"]
    first = client.post("/api/runs/sync", json={"question": "Q1", "session_id": session_id})
    second = client.post("/api/runs/sync", json={"question": "Q2", "session_id": session_id})

    assert first.status_code == 200
    assert second.status_code == 200
    session_file = tmp_path / ".agentcli" / "sessions" / f"{session_id}.json"
    payload = json.loads(session_file.read_text(encoding="utf-8"))
    assert len(payload["turns"]) == 2
    assert payload["turns"][0]["question"] == "Q1"
    assert payload["turns"][1]["question"] == "Q2"


def test_api_notes_endpoint_saves_markdown_note(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path, adapter_factory=lambda: FakeAdapter()))

    response = client.post(
        "/api/notes",
        json={
            "question": "Where is the entry point?",
            "answer": "## Conclusion\nEntry is src/main.py\n\n## Key Files\n- `src/main.py`",
        },
    )

    assert response.status_code == 200
    note_path = Path(response.json()["note_path"])
    assert note_path.exists()
    assert "## 结论 / Conclusion" in note_path.read_text(encoding="utf-8")


def test_api_cancel_endpoint_marks_run_cancelled(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")

    class SlowAdapter:
        def respond(self, messages, tools):
            time.sleep(0.2)
            return {"type": "final", "content": "## Conclusion\ndone"}

    client = TestClient(create_app(tmp_path, adapter_factory=lambda: SlowAdapter()))
    run = client.post("/api/runs", json={"question": "cancel me"})
    run_id = run.json()["run_id"]

    cancel = client.post(f"/api/runs/{run_id}/cancel")
    events = client.get(f"/api/runs/{run_id}/events")

    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"
    assert "event: run_finished" in events.text
    assert '"status":"cancelled"' in events.text
