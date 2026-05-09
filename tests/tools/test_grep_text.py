from pathlib import Path

from agentcli.tools.grep_text import grep_text


def test_grep_text_returns_line_matches(tmp_path: Path) -> None:
    target = tmp_path / "auth.py"
    target.write_text("def login():\n    return True\n", encoding="utf-8")
    results = grep_text(tmp_path, "login")
    assert results == [{"path": "auth.py", "line": 1, "text": "def login():"}]
