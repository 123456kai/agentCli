from pathlib import Path

from agentcli.agent_loop import AgentLoop
from agentcli.llm.adapter import DemoAdapter
from agentcli.runtime import build_runtime


class FakeAdapter:
    def __init__(self) -> None:
        self.calls = 0

    def respond(self, messages, tools):
        self.calls += 1
        if self.calls == 1:
            return {
                "type": "tool_call",
                "tool_name": "search_files",
                "arguments": {"pattern": "main.py"},
            }
        return {
            "type": "final",
            "content": "Conclusion\n- main entry is src/main.py",
        }


def test_agent_loop_executes_tool_then_returns_answer(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    runtime = build_runtime(tmp_path)
    loop = AgentLoop(runtime=runtime, adapter=FakeAdapter())
    answer = loop.run("Where is the entry point?")
    assert "src/main.py" in answer


def test_demo_adapter_returns_final_answer_after_tool_result(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def main():\n    pass\n", encoding="utf-8")
    runtime = build_runtime(tmp_path)
    loop = AgentLoop(runtime=runtime, adapter=DemoAdapter())
    answer = loop.run("Where is the entry point?")
    assert "Conclusion" in answer
