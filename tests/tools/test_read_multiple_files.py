from pathlib import Path

from agentcli.tools.read_multiple_files import read_multiple_files


def test_read_multiple_files_reads_several_files(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("one\ntwo\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("three\nfour\n", encoding="utf-8")

    result = read_multiple_files(tmp_path, ["a.py", "b.py"])
    assert result["kind"] == "multi_file_content"
    assert result["total_files_read"] == 2
    contents = [str(f["content"]) for f in result["files"]]
    assert any("one" in c for c in contents)
    assert any("three" in c for c in contents)


def test_read_multiple_files_handles_errors(tmp_path: Path) -> None:
    (tmp_path / "good.py").write_text("valid\n", encoding="utf-8")

    result = read_multiple_files(tmp_path, ["good.py", "missing.py"])
    assert result["kind"] == "multi_file_content"
    assert result["total_files_read"] == 1
    assert len(result["errors"]) == 1
    assert result["errors"][0]["path"] == "missing.py"


def test_read_multiple_files_empty_paths(tmp_path: Path) -> None:
    result = read_multiple_files(tmp_path, [])
    assert result["kind"] == "bad_param"


def test_read_multiple_files_max_limit(tmp_path: Path) -> None:
    result = read_multiple_files(tmp_path, [f"file_{i}.py" for i in range(11)])
    assert result["kind"] == "bad_param"
