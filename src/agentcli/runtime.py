import os
from pathlib import Path

from agentcli.models import LLMConfig, RuntimeConfig, RuntimeState, ToolSpec
from agentcli.prompts import load_system_prompt


def build_runtime(repo_root: Path) -> RuntimeState:
    resolved = repo_root.resolve()
    config = RuntimeConfig(repo_root=resolved)
    llm = LLMConfig(
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        model=os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash"),
    )
    tools = {
        "search_files": ToolSpec(
            name="search_files",
            description="Search files by glob-like pattern.",
            parameters={
                "type": "object",
                "properties": {"pattern": {"type": "string", "description": "Filename or path fragment to search for."}},
                "required": ["pattern"],
                "additionalProperties": False,
            },
        ),
        "grep_text": ToolSpec(
            name="grep_text",
            description="Search for text in repository files.",
            parameters={
                "type": "object",
                "properties": {"needle": {"type": "string", "description": "Text to search for in repository files."}},
                "required": ["needle"],
                "additionalProperties": False,
            },
        ),
        "read_file": ToolSpec(
            name="read_file",
            description="Read a file snippet with line numbers.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path inside the repository."},
                    "start": {"type": "integer", "description": "Starting line number.", "default": 1},
                    "end": {"type": "integer", "description": "Ending line number.", "default": 80},
                },
                "required": ["path", "start", "end"],
                "additionalProperties": False,
            },
        ),
        "save_note": ToolSpec(
            name="save_note",
            description="Save the final answer as a Markdown note.",
            parameters={
                "type": "object",
                "properties": {
                    "slug": {"type": "string", "description": "File slug for the note."},
                    "content": {"type": "string", "description": "Markdown note content."},
                },
                "required": ["slug", "content"],
                "additionalProperties": False,
            },
        ),
    }
    return RuntimeState(repo_root=config.repo_root, system_prompt=load_system_prompt(), llm=llm, tools=tools)
