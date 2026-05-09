import json
from typing import Protocol

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - exercised in real runtime, not unit tests
    OpenAI = None


class LLMAdapter(Protocol):
    def respond(self, messages: list[dict[str, object]], tools: list[dict[str, object]]) -> dict[str, object]:
        ...


class DemoAdapter:
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
            return {
                "type": "tool_call",
                "tool_name": tool_call.function.name,
                "arguments": arguments,
                "tool_call_id": tool_call.id,
                "assistant_message": assistant_message,
            }
        return {"type": "final", "content": message.content or ""}
