from pathlib import Path

from agentcli.tools.grep_text import grep_text


def test_grep_text_returns_line_matches(tmp_path: Path) -> None:
    target = tmp_path / "auth.py"
    target.write_text("def login():\n    return True\n", encoding="utf-8")
    result = grep_text(tmp_path, "login")
    assert result["kind"] == "grep_results"
    assert result["matches"] == [{"path": "auth.py", "line": 1, "text": "def login():"}]


def test_grep_text_empty_needle(tmp_path: Path) -> None:
    result = grep_text(tmp_path, "")
    assert "error" in result


def test_grep_text_case_insensitive(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text("LOGIN_HANDLER = True\n", encoding="utf-8")
    result = grep_text(tmp_path, "login", ignore_case=True)
    assert len(result["matches"]) == 1


def test_grep_text_skips_sensitive_files(tmp_path: Path) -> None:
    sensitive = tmp_path / ".env"
    sensitive.write_text("API_KEY=secret-value\n", encoding="utf-8")
    result = grep_text(tmp_path, "secret-value", ignore_case=True)
    assert result["matches"] == []
