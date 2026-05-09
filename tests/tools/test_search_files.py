from pathlib import Path

from agentcli.tools.search_files import search_files


def test_search_files_returns_matching_paths(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    results = search_files(tmp_path, "main.py")
    assert results == ["src/main.py"]
