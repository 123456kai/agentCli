from pathlib import Path

from agentcli.analysis.models import AnalysisResult
from agentcli.session import AnalysisSession
from agentcli.session_store import SessionStore


def test_session_store_round_trips_session(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    store = SessionStore(repo)
    session = AnalysisSession.new(repo)
    session.record_turn(
        "How does this repo work?",
        AnalysisResult(
            answer="## Conclusion\nA CLI project.",
            conclusion="A CLI project.",
            key_files=["src/cli.py"],
            reading_order=["pyproject.toml", "src/cli.py"],
            uncertainties=["Runtime flow not yet verified."],
        ),
    )

    saved_path = store.save(session)
    loaded = store.load(session.session_id)

    assert saved_path.exists()
    assert loaded.session_id == session.session_id
    assert loaded.turns[0].question == "How does this repo work?"
    assert loaded.focus_stack == ["src/cli.py"]
    assert loaded.knowledge.claims[0].text == "A CLI project."
    assert loaded.knowledge.evidence[0].path == "src/cli.py"


def test_session_store_load_latest_returns_newest_session(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    store = SessionStore(repo)

    first = AnalysisSession.new(repo)
    first.record_turn(
        "q1",
        AnalysisResult(answer="a1", conclusion="a1"),
    )
    second = AnalysisSession.new(repo)
    second.record_turn(
        "q2",
        AnalysisResult(answer="a2", conclusion="a2"),
    )

    store.save(first)
    newest_path = store.save(second)
    latest = store.load_latest()

    assert latest is not None
    assert latest.session_id == second.session_id
    assert newest_path.name == f"{second.session_id}.json"
