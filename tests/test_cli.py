from typer.testing import CliRunner

from agentcli.cli import app


def test_help_shows_primary_commands() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "ask" in result.stdout
    assert "note" in result.stdout
