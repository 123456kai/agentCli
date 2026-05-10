from pathlib import Path

from agentcli.tools.save_note import save_note


def test_save_note_writes_markdown(tmp_path: Path) -> None:
    output = save_note(tmp_path, "repo-map", "# Repo Map\n")
    assert output.name == "repo-map.md"
    assert output.read_text(encoding="utf-8") == "# Repo Map\n"


def test_save_note_rotates_existing_file(tmp_path: Path) -> None:
    first = save_note(tmp_path, "my-note", "first version")
    second = save_note(tmp_path, "my-note", "second version")
    assert first.name == "my-note.md"
    assert second.name == "my-note-1.md"
    assert first.read_text(encoding="utf-8") == "first version"
    assert second.read_text(encoding="utf-8") == "second version"
