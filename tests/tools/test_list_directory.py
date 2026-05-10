from pathlib import Path

from agentcli.tools.list_directory import list_directory


def test_list_directory_shows_tree(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# test\n", encoding="utf-8")

    result = list_directory(tmp_path)
    assert result["kind"] == "directory_listing"
    content = str(result["content"])
    assert "src/" in content
    assert "main.py" in content
    assert "README.md" in content


def test_list_directory_subdirectory(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "auth.py").write_text("# auth\n", encoding="utf-8")
    (tmp_path / "src" / "models.py").write_text("# models\n", encoding="utf-8")

    result = list_directory(tmp_path, "src")
    assert result["kind"] == "directory_listing"
    content = str(result["content"])
    assert "auth.py" in content
    assert "models.py" in content


def test_list_directory_empty(tmp_path: Path) -> None:
    result = list_directory(tmp_path)
    assert result["kind"] == "directory_listing"
    assert result["content"] == "(empty directory)"


def test_list_directory_rejects_file(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# test\n", encoding="utf-8")
    result = list_directory(tmp_path, "README.md")
    assert result["kind"] == "not_directory"


def test_list_directory_rejects_traversal(tmp_path: Path) -> None:
    result = list_directory(tmp_path, "..")
    assert result["kind"] == "path_traversal"


def test_list_directory_ignores_hidden_dirs(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / ".git").mkdir()
    (tmp_path / "src" / "main.py").write_text("hi\n", encoding="utf-8")

    result = list_directory(tmp_path)
    content = str(result["content"])
    assert "src/" in content
    assert ".git" not in content
