from pathlib import Path

from pydantic import BaseModel, Field


class ToolSpec(BaseModel):
    name: str
    description: str
    parameters: dict[str, object]


class LLMConfig(BaseModel):
    api_key: str | None = None
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-flash"


class RuntimeConfig(BaseModel):
    repo_root: Path
    max_steps: int = Field(default=50, ge=1, le=100)
    read_max_lines: int = Field(default=160, ge=20, le=400)


class RuntimeState(BaseModel):
    repo_root: Path
    system_prompt: str
    llm: LLMConfig
    max_steps: int
    read_max_lines: int
    project_map_summary: str = ""
    tools: dict[str, ToolSpec]
