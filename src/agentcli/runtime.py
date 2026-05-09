from pathlib import Path

from agentcli.models import RuntimeConfig, RuntimeState, ToolSpec
from agentcli.prompts import load_system_prompt


def build_runtime(repo_root: Path) -> RuntimeState:
    resolved = repo_root.resolve()
    config = RuntimeConfig(repo_root=resolved)
    tools = {
        "search_files": ToolSpec(name="search_files", description="Search files by glob-like pattern."),
        "grep_text": ToolSpec(name="grep_text", description="Search for text in repository files."),
        "read_file": ToolSpec(name="read_file", description="Read a file snippet with line numbers."),
        "save_note": ToolSpec(name="save_note", description="Save the final answer as a Markdown note."),
    }
    return RuntimeState(repo_root=config.repo_root, system_prompt=load_system_prompt(), tools=tools)
