from typing import Protocol


class LLMAdapter(Protocol):
    def respond(self, messages: list[dict[str, str]], tools: list[dict[str, str]]) -> dict[str, object]:
        ...


class DemoAdapter:
    def respond(self, messages: list[dict[str, str]], tools: list[dict[str, str]]) -> dict[str, object]:
        last_message = messages[-1]["content"]
        if "search_files =>" not in last_message:
            return {
                "type": "tool_call",
                "tool_name": "search_files",
                "arguments": {"pattern": "main.py"},
            }
        return {
            "type": "final",
            "content": "## Conclusion\nLikely entry point: src/main.py\n\n## Reading Path\n1. Read src/main.py\n2. Follow imports from the entry module",
        }
