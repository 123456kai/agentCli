from pathlib import Path

import pytest

from agentcli.tools.read_file import read_file


def test_read_file_with_line_offset_and_n_lines(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text("one\ntwo\nthree\nfour\nfive\n", encoding="utf-8")
    result = read_file(tmp_path, "app.py", line_offset=2, n_lines=2)
    assert result["kind"] == "file_content"
    assert result["total_lines"] == 5
    content = str(result["content"])
    assert "two" in content
    assert "three" in content
    assert "one" not in content
    assert "four" not in content


def test_read_file_eof_detected(tmp_path: Path) -> None:
    target = tmp_path / "small.py"
    target.write_text("line1\nline2\n", encoding="utf-8")
    result = read_file(tmp_path, "small.py", line_offset=1, n_lines=10)
    assert "EOF reached" in str(result["message"])


def test_read_file_rejects_directory(tmp_path: Path) -> None:
    (tmp_path / "subdir").mkdir()
    result = read_file(tmp_path, "subdir")
    assert result["kind"] == "is_directory"


def test_read_file_rejects_nonexistent(tmp_path: Path) -> None:
    result = read_file(tmp_path, "nonexistent.py")
    assert result["kind"] == "not_found"


def test_read_file_rejects_path_traversal(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("hi\n", encoding="utf-8")
    result = read_file(tmp_path, "../outside.py")
    assert result["kind"] == "path_traversal"


def test_read_file_rejects_sensitive_file(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("SECRET=123\n", encoding="utf-8")
    result = read_file(tmp_path, ".env")
    assert result["kind"] == "sensitive_file"


def test_read_file_rejects_binary_extension(tmp_path: Path) -> None:
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    result = read_file(tmp_path, "image.png")
    assert result["kind"] == "binary_file"


def test_read_file_negative_offset_reads_tail(tmp_path: Path) -> None:
    target = tmp_path / "log.txt"
    lines = [f"line {i}" for i in range(1, 11)]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = read_file(tmp_path, "log.txt", line_offset=-3)
    content = str(result["content"])
    assert "line 8" in content
    assert "line 9" in content
    assert "line 10" in content
    assert "line 7" not in content
