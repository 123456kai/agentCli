from typer.testing import CliRunner

from agentcli.cli import app


def test_chat_command_reuses_session_across_turns(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    class FakeLoop:
        def __init__(self, runtime, adapter, **kwargs) -> None:
            self.runtime = runtime

        def run_turn(self, session, user_message: str) -> str:
            if not session.turns:
                session.record_turn(
                    user_message,
                    self.runtime_to_result("Mapped the repo.", "src/agentcli/cli.py"),
                )
                return "First turn"
            assert session.focus_stack == ["src/agentcli/cli.py"]
            session.record_turn(
                user_message,
                self.runtime_to_result("Expanded the agent loop.", "src/agentcli/agent_loop.py"),
            )
            return "Second turn"

        @staticmethod
        def runtime_to_result(conclusion: str, focus: str):
            from agentcli.analysis.models import AnalysisResult

            return AnalysisResult(
                answer=f"## Conclusion\n{conclusion}",
                conclusion=conclusion,
                key_files=[focus],
                reading_order=[focus],
            )

    monkeypatch.setattr("agentcli.cli.AgentLoop", FakeLoop)
    monkeypatch.setattr("agentcli.cli.DeepSeekOpenAIAdapter", lambda **kw: object())

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["chat", "--repo", str(repo)],
        input="How does this repo work?\ncontinue on the agent loop\nexit\n",
    )

    assert result.exit_code == 0
    assert "Session:" in result.stdout
    assert "First turn" in result.stdout
    assert "Second turn" in result.stdout


def test_chat_command_rejects_missing_session(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr("agentcli.cli.DeepSeekOpenAIAdapter", lambda **kw: object())

    runner = CliRunner()
    result = runner.invoke(app, ["chat", "--repo", str(repo), "--session", "missing"])

    assert result.exit_code != 0
    assert "No saved session found" in result.stdout
