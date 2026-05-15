import tempfile
from pathlib import Path

from agentcli.analysis.storyline import (
    StorylineNode,
    discover_storylines,
    resolve_storyline_nodes,
)
from agentcli.analysis.graph import build_graph_index


def _make_repo(files: dict[str, str]) -> Path:
    root = Path(tempfile.mkdtemp())
    for rel, content in files.items():
        abs_path = root / rel
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(content, encoding="utf-8")
    return root


SAMPLE_FILES = {
    "src/main.py": '''
from src.auth import login

def main():
    user = login("test", "pass")
    print(user)

if __name__ == "__main__":
    main()
''',
    "src/auth.py": '''
from src.db import find_user

def login(username: str, password: str):
    user = find_user(username)
    if user and user.get("password") == password:
        return user
    return None
''',
    "src/db.py": '''
_users = [{"username": "admin", "password": "admin123"}]

def find_user(username: str):
    for u in _users:
        if u["username"] == username:
            return u
    return None
''',
}


def test_discover_storylines_finds_entry_based_paths():
    repo_root = _make_repo(SAMPLE_FILES)
    index = build_graph_index(repo_root)

    storylines = discover_storylines(repo_root, index)

    assert len(storylines) >= 1
    auth_storyline = [s for s in storylines if "login" in s.title.lower() or "auth" in s.title.lower()]
    assert len(auth_storyline) >= 1


def test_resolve_storyline_nodes_maps_to_source():
    repo_root = _make_repo(SAMPLE_FILES)
    index = build_graph_index(repo_root)

    storyline = discover_storylines(repo_root, index)[0]
    resolved = resolve_storyline_nodes(repo_root, index, storyline)

    for node in resolved:
        assert isinstance(node, StorylineNode)
        assert node.file_path
        assert node.line_start > 0
        assert node.line_end >= node.line_start, (
            f"line_end ({node.line_end}) should be >= line_start ({node.line_start}) "
            f"for {node.title} in {node.file_path}"
        )
        assert node.graph_node_id
        assert node.order >= 0

    # Verify that at least one node spans multiple lines (line_end > line_start)
    multi_line_nodes = [n for n in resolved if n.line_end > n.line_start]
    assert len(multi_line_nodes) > 0, (
        "Expected at least one multi-line function body, "
        f"but all {len(resolved)} nodes have line_end == line_start"
    )


def test_resolve_line_end_adjacent_functions():
    """line_end should not bleed into the next function definition."""
    from agentcli.analysis.storyline import _resolve_line_end

    tmp = Path(tempfile.mkdtemp()) / "test.py"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(
        """\
def foo():
    x = 1
    return x


def bar():
    y = 2
    return y
"""
    )
    # foo starts at line 2 (1-based); bar is at line 7. foo should end before bar.
    end = _resolve_line_end(tmp, line_start=2)
    assert end < 7, f"line_end ({end}) should be less than bar's start line (7)"
    assert end >= 2, f"line_end ({end}) should be at least foo's start line (2)"


def test_discover_storylines_skips_too_short_paths():
    repo_root = _make_repo(SAMPLE_FILES)
    index = build_graph_index(repo_root)

    storylines = discover_storylines(repo_root, index, min_nodes=3, max_nodes=10)

    for s in storylines:
        assert s.node_count >= 3
        assert s.node_count <= 10


def test_generate_node_narrative_returns_structured_result():
    import json
    import asyncio
    from agentcli.analysis.storyline import generate_node_narrative, NodeNarrative
    from agentcli.analysis.cache import NarrativeCache

    repo_root = _make_repo(SAMPLE_FILES)
    index = build_graph_index(repo_root)
    cache_dir = Path(tempfile.mkdtemp())
    cache = NarrativeCache(cache_dir)

    # Find the "login" node
    node_id = next(
        nid for nid, n in index["nodes_by_id"].items()
        if str(n["label"]) == "login"
    )

    class MockAdapter:
        def chat_sync(self, prompt: str) -> str:
            return json.dumps({
                "summary": "从请求头提取 Bearer Token 并验证 JWT",
                "design_notes": "使用中间件模式解耦认证和业务逻辑",
                "warnings": "HS256 是对称加密，生产建议 RS256",
            })

    narrative = asyncio.run(
        generate_node_narrative(
            repo_root=repo_root,
            node_id=node_id,
            index=index,
            cache=cache,
            adapter_factory=lambda: MockAdapter(),
        )
    )

    assert isinstance(narrative, NodeNarrative)
    assert narrative.summary
    assert narrative.design_notes
    assert narrative.warnings is not None
