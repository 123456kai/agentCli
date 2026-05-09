from pathlib import Path

from agentcli.tools.save_note import save_note


def test_save_note_writes_markdown(tmp_path: Path) -> None:
    output = save_note(tmp_path, "repo-map", "# Repo Map\n")
    assert output.name == "repo-map.md"
    assert output.read_text(encoding="utf-8") == "# Repo Map\n"
