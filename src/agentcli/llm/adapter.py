from typing import Protocol


class LLMAdapter(Protocol):
    def respond(self, messages: list[dict[str, str]], tools: list[dict[str, str]]) -> dict[str, object]:
        ...
