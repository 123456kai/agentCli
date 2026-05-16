import json
from typing import Protocol

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - exercised in real runtime, not unit tests
    OpenAI = None


class LLMAdapter(Protocol):
    def respond(self, messages: list[dict[str, object]], tools: list[dict[str, object]]) -> dict[str, object]:
        ...

    def chat_sync(self, prompt: str) -> str:
        ...


class DemoAdapter:
    def chat_sync(self, prompt: str) -> str:
        """Return a demo JSON response for testing."""
        if "领域" in prompt or "dir_tree" in prompt:
            return json.dumps({
                "domains": [
                    {"id": "api", "name": "Web API", "description": "HTTP接口", "files": ["src/agentcli/api/server.py"]},
                    {"id": "agent", "name": "Agent引擎", "description": "Agent循环", "files": ["src/agentcli/agent_loop.py"]},
                    {"id": "cli", "name": "CLI入口", "description": "命令行", "files": ["src/agentcli/cli.py"]},
                ]
            })
        if "node_sequence" in prompt or "storylines" in prompt:
            return json.dumps({
                "storylines": [
                    {
                        "title": "Agent 循环执行流程",
                        "description": "Agent 如何处理一个用户问题",
                        "theme": "agent",
                        "node_sequence": [
                            {"order": 0, "role_title": "Agent入口", "file_path": "src/agentcli/agent_loop.py", "graph_node_id": "src/agentcli/agent_loop.py::AgentLoop.run_turn"},
                            {"order": 1, "role_title": "消息处理循环", "file_path": "src/agentcli/agent_loop.py", "graph_node_id": "src/agentcli/agent_loop.py::AgentLoop._run_with_messages"},
                            {"order": 2, "role_title": "事件发射", "file_path": "src/agentcli/agent_loop.py", "graph_node_id": "src/agentcli/agent_loop.py::AgentLoop._emit"},
                        ]
                    }
                ]
            })
        return json.dumps({
            "summary": "这段代码处理核心逻辑",
            "design_notes": "使用了清晰的模块化设计",
            "warnings": None,
            "next_teaser": "接下来你会好奇数据从哪里来",
        })

    def respond(self, messages: list[dict[str, object]], tools: list[dict[str, object]]) -> dict[str, object]:
        last_message = messages[-1]
        if last_message.get("role") != "tool":
            return {
                "type": "tool_call",
                "tool_name": "search_files",
                "arguments": {"pattern": "main.py"},
            }
        return {
            "type": "final",
            "content": "## Conclusion\nLikely entry point: src/main.py\n\n## Reading Path\n1. Read src/main.py\n2. Follow imports from the entry module",
        }


class DeepSeekOpenAIAdapter:
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        if OpenAI is None:
            raise RuntimeError("The openai package is required for DeepSeek integration.")
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def chat_sync(self, prompt: str) -> str:
        """Send a single prompt and return the text response (no tools)."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""

    def respond(self, messages: list[dict[str, object]], tools: list[dict[str, object]]) -> dict[str, object]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        message = response.choices[0].message
        if message.tool_calls:
            tool_call = message.tool_calls[0]
            arguments = json.loads(tool_call.function.arguments or "{}")
            assistant_message = {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                    }
                ],
            }
            reasoning_content = getattr(message, "reasoning_content", None)
            if reasoning_content:
                assistant_message["reasoning_content"] = reasoning_content
            return {
                "type": "tool_call",
                "tool_name": tool_call.function.name,
                "arguments": arguments,
                "tool_call_id": tool_call.id,
                "assistant_message": assistant_message,
            }
        return {"type": "final", "content": message.content or ""}
