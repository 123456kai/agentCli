from pathlib import Path

from agentcli.tools.read_file import read_file


def test_read_file_includes_line_numbers(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text("one\ntwo\nthree\n", encoding="utf-8")
    content = read_file(target, start=2, end=3)
    assert "2: two" in content
    assert "3: three" in content
