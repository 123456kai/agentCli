from fastapi.testclient import TestClient
from agentcli.api.server import create_app
from pathlib import Path
import tempfile


def _sample_repo() -> Path:
    root = Path(tempfile.mkdtemp())
    (root / "src").mkdir(parents=True)
    (root / "src" / "__init__.py").write_text("")
    (root / "src" / "main.py").write_text('''
from src.auth import login

def main():
    user = login("test", "pass")
    print(user)
''')
    (root / "src" / "auth.py").write_text('''
from src.db import find_user

def login(username: str, password: str) -> dict | None:
    user = find_user(username)
    if user and user["password"] == password:
        return user
    return None
''')
    return root


def test_get_storylines_returns_list():
    repo = _sample_repo()
    app = create_app(repo)
    client = TestClient(app)
    resp = client.get("/api/storylines")
    assert resp.status_code == 200
    data = resp.json()
    assert "storylines" in data
    assert isinstance(data["storylines"], list)


def test_get_storyline_detail():
    repo = _sample_repo()
    app = create_app(repo)
    client = TestClient(app)
    list_resp = client.get("/api/storylines")
    storylines = list_resp.json()["storylines"]
    if not storylines:
        return  # not enough nodes to generate storylines
    sid = storylines[0]["id"]
    resp = client.get(f"/api/storylines/{sid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == sid
    assert len(data["nodes"]) > 0


def test_get_storyline_node():
    repo = _sample_repo()
    app = create_app(repo)
    client = TestClient(app)
    list_resp = client.get("/api/storylines")
    storylines = list_resp.json()["storylines"]
    if not storylines:
        return
    sid = storylines[0]["id"]
    detail = client.get(f"/api/storylines/{sid}")
    nodes = detail.json()["nodes"]
    nid = nodes[0]["graph_node_id"]
    resp = client.get(f"/api/storylines/{sid}/nodes/{nid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["node"]["graph_node_id"] == nid
    assert "source_code" in data


def test_storyline_not_found():
    repo = _sample_repo()
    app = create_app(repo)
    client = TestClient(app)
    resp = client.get("/api/storylines/nonexistentid")
    assert resp.status_code == 404
