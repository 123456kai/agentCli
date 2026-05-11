from agentcli.notes.formatter import make_note_slug, render_note


def test_make_note_slug_handles_empty_question() -> None:
    assert make_note_slug("???") == "source-note"


def test_render_note_includes_structured_sections() -> None:
    note = render_note(
        question="How does this repo work?",
        answer="This project is a Typer-based CLI.",
        key_files=["src/agentcli/cli.py", "src/agentcli/agent_loop.py"],
        reading_order=["pyproject.toml", "src/agentcli/cli.py"],
        uncertainties=["The production adapter was not exercised."],
    )

    assert "# How does this repo work?" in note
    assert "## 结论 / Conclusion" in note
    assert "- `src/agentcli/cli.py`" in note
    assert "1. pyproject.toml" in note
    assert "- The production adapter was not exercised." in note
