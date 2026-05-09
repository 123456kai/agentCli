from typer.testing import CliRunner

from agentcli.cli import app, build_adapter


def test_help_shows_primary_commands() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "ask" in result.stdout
    assert "note" in result.stdout


def test_ask_requires_question() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["ask"])
    assert result.exit_code != 0


def test_note_saves_markdown_with_repo_option(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    class FakeLoop:
        def __init__(self, runtime, adapter) -> None:
            self.runtime = runtime

        def run(self, question: str) -> str:
            return "## Conclusion\nEntry point is src/main.py"

    monkeypatch.setattr("agentcli.cli.AgentLoop", FakeLoop)
    monkeypatch.setattr("agentcli.cli.build_adapter", lambda: object())

    runner = CliRunner()
    result = runner.invoke(app, ["note", "--repo", str(repo), "Find entrypoint"])
    assert result.exit_code == 0
    assert "notes/find-entrypoint.md" in result.stdout


def test_build_adapter_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    try:
        build_adapter()
    except RuntimeError as exc:
        assert "DEEPSEEK_API_KEY" in str(exc)
    else:
        raise AssertionError("build_adapter should require DEEPSEEK_API_KEY")
