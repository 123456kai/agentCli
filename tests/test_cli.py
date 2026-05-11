import json
from pathlib import Path

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
        def __init__(self, runtime, adapter, **kwargs) -> None:
            self.runtime = runtime

        def run(self, question: str) -> str:
            return "## Conclusion\nEntry point is src/main.py"

    monkeypatch.setattr("agentcli.cli.AgentLoop", FakeLoop)
    monkeypatch.setattr("agentcli.cli.DeepSeekOpenAIAdapter", lambda **kw: object())

    runner = CliRunner()
    result = runner.invoke(app, ["note", "--repo", str(repo), "Find entrypoint"])
    assert result.exit_code == 0
    assert "notes" in result.stdout and "find-entrypoint.md" in result.stdout
    note_path = Path("".join(result.stdout.split()))
    content = note_path.read_text(encoding="utf-8")
    assert "## 结论 / Conclusion" in content


def test_note_output_dir_option(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    custom_dir = tmp_path / "my-notes"
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    class FakeLoop:
        def __init__(self, runtime, adapter, **kwargs) -> None:
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
        def __init__(self, runtime, adapter, **kwargs) -> None:
            self.runtime = runtime

        def run(self, question: str) -> str:
            return """## Conclusion
Test answer

## Key Files
- `src/agentcli/cli.py`

## Reading Order
1. `src/agentcli/cli.py`

## Uncertainties
- Need to inspect runtime behavior.
"""

    monkeypatch.setattr("agentcli.cli.AgentLoop", FakeLoop)
    monkeypatch.setattr("agentcli.cli.DeepSeekOpenAIAdapter", lambda **kw: object())

    runner = CliRunner()
    result = runner.invoke(app, ["ask", "--repo", str(repo), "--format", "json", "Test question"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["question"] == "Test question"
    assert payload["answer"].startswith("## Conclusion")
    assert payload["key_files"] == ["src/agentcli/cli.py"]
    assert payload["reading_order"] == ["src/agentcli/cli.py"]
    assert payload["uncertainties"] == ["Need to inspect runtime behavior."]


def test_note_json_output_includes_structured_fields(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    class FakeLoop:
        def __init__(self, runtime, adapter, **kwargs) -> None:
            self.runtime = runtime

        def run(self, question: str) -> str:
            return """## Conclusion
Entry point is src/main.py

## Key Files
- `src/main.py`

## Reading Order
1. `src/main.py`

## Uncertainties
- Startup side effects were not inspected.
"""

    monkeypatch.setattr("agentcli.cli.AgentLoop", FakeLoop)
    monkeypatch.setattr("agentcli.cli.DeepSeekOpenAIAdapter", lambda **kw: object())

    runner = CliRunner()
    result = runner.invoke(app, ["note", "--repo", str(repo), "--format", "json", "Find entrypoint"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["key_files"] == ["src/main.py"]
    assert payload["reading_order"] == ["src/main.py"]
    assert payload["uncertainties"] == ["Startup side effects were not inspected."]
    note_path = Path(payload["note_path"])
    assert note_path.exists()
    assert "## 关键文件 / Key Files" in note_path.read_text(encoding="utf-8")


def test_ask_rejects_nonexistent_repo() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["ask", "--repo", "/nonexistent/path", "test"])
    assert result.exit_code != 0
