from pathlib import Path

from agentcli.analysis.models import AnalysisResult
from agentcli.session import AnalysisSession


def test_analysis_session_records_turn_and_updates_focus(tmp_path: Path) -> None:
    session = AnalysisSession.new(tmp_path / "repo")
    result = AnalysisResult(
        answer="## Conclusion\nA CLI tool.",
        conclusion="A CLI tool.",
        key_files=["src/agentcli/cli.py"],
        reading_order=["pyproject.toml", "src/agentcli/cli.py"],
        uncertainties=["Adapter internals not verified."],
    )

    session.record_turn("How does this repo work?", result)

    assert session.turns[0].question == "How does this repo work?"
    assert session.claims == ["A CLI tool."]
    assert session.focus_stack == ["src/agentcli/cli.py"]
    assert session.open_questions == ["Adapter internals not verified."]


def test_analysis_session_summary_mentions_previous_focus(tmp_path: Path) -> None:
    session = AnalysisSession.new(tmp_path / "repo")
    session.record_turn(
        "How does this repo work?",
        AnalysisResult(
            answer="## Conclusion\nA CLI tool.",
            conclusion="A CLI tool.",
            key_files=["src/agentcli/cli.py"],
            reading_order=["src/agentcli/cli.py"],
        ),
    )

    summary = session.render_summary()

    assert "Current focus" in summary
    assert "src/agentcli/cli.py" in summary


def test_analysis_session_records_structured_knowledge(tmp_path: Path) -> None:
    session = AnalysisSession.new(tmp_path / "repo")

    session.record_turn(
        "How does the CLI start?",
        AnalysisResult(
            answer="## Conclusion\nThe CLI entrypoint is agentcli.cli:app.",
            conclusion="The CLI entrypoint is agentcli.cli:app.",
            key_files=["pyproject.toml", "src/agentcli/cli.py"],
            reading_order=["pyproject.toml", "src/agentcli/cli.py"],
            uncertainties=["Need to inspect runtime wiring."],
        ),
    )

    assert session.knowledge.claims[0].text == "The CLI entrypoint is agentcli.cli:app."
    assert session.knowledge.claims[0].evidence_ids
    assert session.knowledge.evidence[0].path == "pyproject.toml"
    assert session.knowledge.open_questions[0].text == "Need to inspect runtime wiring."
    assert session.knowledge.next_actions[0].text == "Read pyproject.toml"
