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


def test_agent_loop_appends_assistant_and_tool_messages(tmp_path: Path) -> None:
    observed_messages: list[dict[str, object]] = []

    class InspectingAdapter:
        def __init__(self) -> None:
            self.calls = 0

        def respond(self, messages, tools):
            self.calls += 1
            if self.calls == 1:
                return {
                    "type": "tool_call",
                    "tool_name": "search_files",
                    "arguments": {"pattern": "main.py"},
                    "tool_call_id": "call_123",
                    "assistant_message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "type": "function",
                                "function": {"name": "search_files", "arguments": "{\"pattern\":\"main.py\"}"},
                            }
                        ],
                    },
                }
            observed_messages.extend(messages)
            return {"type": "final", "content": "done"}

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    runtime = build_runtime(tmp_path)
    loop = AgentLoop(runtime=runtime, adapter=InspectingAdapter())
    loop.run("Where is the entry point?")
    assert observed_messages[-2]["role"] == "assistant"
    assert observed_messages[-1]["role"] == "tool"
    assert observed_messages[-1]["tool_call_id"] == "call_123"


def test_agent_loop_returns_tool_error_when_read_file_gets_directory(tmp_path: Path) -> None:
    observed_messages: list[dict[str, object]] = []

    class DirectoryReadAdapter:
        def __init__(self) -> None:
            self.calls = 0

        def respond(self, messages, tools):
            self.calls += 1
            if self.calls == 1:
                return {
                    "type": "tool_call",
                    "tool_name": "read_file",
                    "arguments": {"path": "", "start": 1, "end": 10},
                    "tool_call_id": "call_dir",
                }
            observed_messages.extend(messages)
            return {"type": "final", "content": "recovered"}

    runtime = build_runtime(tmp_path)
    loop = AgentLoop(runtime=runtime, adapter=DirectoryReadAdapter())
    answer = loop.run("Explain this repo")
    assert answer == "recovered"
    assert "error" in observed_messages[-1]["content"]
    assert "not a file" in observed_messages[-1]["content"]


def test_agent_loop_uses_runtime_max_steps_for_longer_reading_sessions(tmp_path: Path) -> None:
    class LongerReadingAdapter:
        def __init__(self) -> None:
            self.calls = 0

        def respond(self, messages, tools):
            self.calls += 1
            if self.calls <= 7:
                return {
                    "type": "tool_call",
                    "tool_name": "search_files",
                    "arguments": {"pattern": "py"},
                    "tool_call_id": f"call_{self.calls}",
                }
            return {"type": "final", "content": "done after deeper reading"}

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    runtime = build_runtime(tmp_path)
    loop = AgentLoop(runtime=runtime, adapter=LongerReadingAdapter())
    assert loop.run("Explain this repo") == "done after deeper reading"


def test_agent_loop_requests_final_answer_when_tool_budget_is_exhausted(tmp_path: Path) -> None:
    class BudgetHungryAdapter:
        def __init__(self) -> None:
            self.calls = 0
            self.final_tools = None
            self.final_messages = None

        def respond(self, messages, tools):
            self.calls += 1
            if self.calls <= 12:
                return {
                    "type": "tool_call",
                    "tool_name": "search_files",
                    "arguments": {"pattern": "py"},
                    "tool_call_id": f"call_{self.calls}",
                }
            self.final_tools = tools
            self.final_messages = messages
            return {"type": "final", "content": "best effort final answer"}

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    adapter = BudgetHungryAdapter()
    runtime = build_runtime(tmp_path)
    loop = AgentLoop(runtime=runtime, adapter=adapter)
    assert loop.run("Explain this repo") == "best effort final answer"
    assert adapter.final_tools == []
    assert "tool budget" in adapter.final_messages[-1]["content"]
