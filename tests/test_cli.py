from typer.testing import CliRunner

from agentcli.cli import app


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
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    class FakeLoop:
        def __init__(self, runtime, adapter) -> None:
            self.runtime = runtime

        def run(self, question: str) -> str:
            return "## Conclusion\nEntry point is src/main.py"

    monkeypatch.setattr("agentcli.cli.AgentLoop", FakeLoop)
    monkeypatch.setattr("agentcli.cli.DeepSeekOpenAIAdapter", lambda **kw: object())

    runner = CliRunner()
    result = runner.invoke(app, ["note", "--repo", str(repo), "Find entrypoint"])
    assert result.exit_code == 0
    assert "notes" in result.stdout and "find-entrypoint.md" in result.stdout


def test_note_output_dir_option(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    custom_dir = tmp_path / "my-notes"
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    class FakeLoop:
        def __init__(self, runtime, adapter) -> None:
            self.runtime = runtime

        def run(self, question: str) -> str:
            return "## Conclusion\nDone"

    monkeypatch.setattr("agentcli.cli.AgentLoop", FakeLoop)
    monkeypatch.setattr("agentcli.cli.DeepSeekOpenAIAdapter", lambda **kw: object())

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["note", "--repo", str(repo), "--output-dir", str(custom_dir), "Test question"],
    )
    assert result.exit_code == 0
    assert "my-notes" in result.stdout


def test_ask_json_output(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    class FakeLoop:
        def __init__(self, runtime, adapter) -> None:
            self.runtime = runtime

        def run(self, question: str) -> str:
            return "## Conclusion\nTest answer"

    monkeypatch.setattr("agentcli.cli.AgentLoop", FakeLoop)
    monkeypatch.setattr("agentcli.cli.DeepSeekOpenAIAdapter", lambda **kw: object())

    runner = CliRunner()
    result = runner.invoke(app, ["ask", "--repo", str(repo), "--format", "json", "Test question"])
    assert result.exit_code == 0
    assert '"question"' in result.stdout
    assert '"answer"' in result.stdout


def test_ask_rejects_nonexistent_repo() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["ask", "--repo", "/nonexistent/path", "test"])
    assert result.exit_code != 0
