from dataclasses import dataclass


@dataclass(slots=True)
class ToolResult:
    name: str
    payload: object
