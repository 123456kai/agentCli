from pathlib import Path

from agentcli.tools.search_files import search_files


def test_search_files_returns_matching_paths(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    result = search_files(tmp_path, "main.py")
    assert result["kind"] == "search_results"
    assert result["matches"] == ["src/main.py"]


def test_search_files_truncates_at_limit(tmp_path: Path) -> None:
    for i in range(10):
        (tmp_path / f"file_{i}.py").write_text(f"# {i}\n", encoding="utf-8")
    result = search_files(tmp_path, ".py", head_limit=3)
    assert result["kind"] == "search_results"
    assert len(result["matches"]) == 3
    assert result["truncated"] is True


def test_search_files_empty_pattern(tmp_path: Path) -> None:
    result = search_files(tmp_path, "")
    assert "error" in result
