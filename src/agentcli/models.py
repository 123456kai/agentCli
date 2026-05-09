from pathlib import Path

from pydantic import BaseModel, Field


class ToolSpec(BaseModel):
    name: str
    description: str


class RuntimeConfig(BaseModel):
    repo_root: Path
    max_steps: int = Field(default=6, ge=1, le=20)
    read_max_lines: int = Field(default=160, ge=20, le=400)


class RuntimeState(BaseModel):
    repo_root: Path
    system_prompt: str
    tools: dict[str, ToolSpec]
