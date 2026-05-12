from pathlib import Path

from agentcli.agent_loop import AgentLoop
from agentcli.engine.events import InMemoryEventSink
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
                                "function": {"name": "search_files", "arguments": '{"pattern":"main.py"}'},
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
    class DirectoryReadAdapter:
        def __init__(self) -> None:
            self.calls = 0

        def respond(self, messages, tools):
            self.calls += 1
            if self.calls == 1:
                return {
                    "type": "tool_call",
                    "tool_name": "read_file",
                    "arguments": {"path": "src"},
                    "tool_call_id": "call_dir",
                }
            return {"type": "final", "content": "recovered"}

    (tmp_path / "src").mkdir()
    runtime = build_runtime(tmp_path)
    loop = AgentLoop(runtime=runtime, adapter=DirectoryReadAdapter())
    answer = loop.run("Explain this repo")
    assert answer == "recovered"


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
    runtime = build_runtime(tmp_path, max_steps=12)
    loop = AgentLoop(runtime=runtime, adapter=adapter)
    assert loop.run("Explain this repo") == "best effort final answer"
    assert adapter.final_tools == []
    assert "tool budget" in adapter.final_messages[-2]["content"]


def test_agent_loop_recovers_from_unknown_tool(tmp_path: Path) -> None:
    class UnknownToolAdapter:
        def __init__(self) -> None:
            self.calls = 0

        def respond(self, messages, tools):
            self.calls += 1
            if self.calls == 1:
                return {
                    "type": "tool_call",
                    "tool_name": "nonexistent_tool",
                    "arguments": {},
                    "tool_call_id": "call_bad",
                }
            return {"type": "final", "content": "fallback answer"}

    runtime = build_runtime(tmp_path)
    loop = AgentLoop(runtime=runtime, adapter=UnknownToolAdapter())
    answer = loop.run("What is this?")
    assert answer == "fallback answer"


def test_agent_loop_recovers_from_unexpected_response_type(tmp_path: Path) -> None:
    class WeirdResponseAdapter:
        def __init__(self) -> None:
            self.calls = 0

        def respond(self, messages, tools):
            self.calls += 1
            if self.calls == 1:
                return {"type": "weird_unknown_type", "content": "???"}
            return {"type": "final", "content": "recovered after weird response"}

    runtime = build_runtime(tmp_path)
    loop = AgentLoop(runtime=runtime, adapter=WeirdResponseAdapter())
    answer = loop.run("What is this?")
    assert "recovered" in answer


def test_agent_loop_emits_tool_progress_events(tmp_path: Path) -> None:
    events: list[dict[str, object]] = []

    class ProgressAdapter:
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
            return {"type": "final", "content": "done"}

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    runtime = build_runtime(tmp_path)
    loop = AgentLoop(runtime=runtime, adapter=ProgressAdapter(), progress_callback=events.append)
    assert loop.run("Where is the entry point?") == "done"
    assert events[0]["tool_name"] == "search_files"
    assert events[0]["result"]["kind"] == "search_results"


def test_agent_loop_emits_structured_events_for_file_reads(tmp_path: Path) -> None:
    class ReadingAdapter:
        def __init__(self) -> None:
            self.calls = 0

        def respond(self, messages, tools):
            self.calls += 1
            if self.calls == 1:
                return {
                    "type": "tool_call",
                    "tool_name": "read_file",
                    "arguments": {"path": "src/main.py", "line_offset": 1, "n_lines": 2},
                    "tool_call_id": "call_read",
                }
            return {"type": "final", "content": "done"}

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\nprint('bye')\n", encoding="utf-8")
    sink = InMemoryEventSink()
    runtime = build_runtime(tmp_path)
    loop = AgentLoop(runtime=runtime, adapter=ReadingAdapter(), event_sink=sink)

    assert loop.run("Read main") == "done"

    event_types = [event.type for event in sink.events]
    assert event_types == [
        "run_started",
        "project_map_ready",
        "reading_plan_created",
        "tool_started",
        "file_opened",
        "line_range_read",
        "tool_finished",
        "answer_final",
        "run_finished",
    ]
    file_event = next(event for event in sink.events if event.type == "file_opened")
    assert file_event.payload["path"] == "src/main.py"
    range_event = next(event for event in sink.events if event.type == "line_range_read")
    assert range_event.payload["start_line"] == 1
    assert range_event.payload["end_line"] == 2


def test_agent_loop_can_execute_enhanced_source_tools(tmp_path: Path) -> None:
    class DefinitionAdapter:
        def __init__(self) -> None:
            self.calls = 0

        def respond(self, messages, tools):
            self.calls += 1
            if self.calls == 1:
                return {
                    "type": "tool_call",
                    "tool_name": "find_definitions",
                    "arguments": {"symbol": "main"},
                    "tool_call_id": "call_def",
                }
            assert messages[-1]["role"] == "tool"
            assert "symbol_definitions" in messages[-1]["content"]
            return {"type": "final", "content": "found definition"}

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def main():\n    pass\n", encoding="utf-8")
    runtime = build_runtime(tmp_path)
    loop = AgentLoop(runtime=runtime, adapter=DefinitionAdapter())

    assert loop.run("Where is main?") == "found definition"
