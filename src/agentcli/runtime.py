import os
from pathlib import Path

from agentcli.analysis import render_project_map_summary, scan_project_map
from agentcli.config import AgentCliConfig
from agentcli.models import LLMConfig, RuntimeConfig, RuntimeState, ToolSpec
from agentcli.prompts import load_system_prompt
from agentcli.repo_guard import MAX_LINES


def build_runtime(
    repo_root: Path,
    model: str | None = None,
    base_url: str | None = None,
    max_steps: int | None = None,
    read_max_lines: int | None = None,
) -> RuntimeState:
    resolved = repo_root.resolve()
    config = RuntimeConfig(repo_root=resolved)

    # DEEPSEEK_* env vars remain for backward compatibility
    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("AGENTCLI_API_KEY")
    env_model = os.environ.get("DEEPSEEK_MODEL") or os.environ.get("AGENTCLI_MODEL")
    env_base_url = os.environ.get("DEEPSEEK_BASE_URL") or os.environ.get("AGENTCLI_BASE_URL")

    llm = LLMConfig(
        api_key=api_key,
        base_url=base_url or env_base_url or "https://api.deepseek.com",
        model=model or env_model or "deepseek-v4-flash",
    )

    tools = {
        "search_files": ToolSpec(
            name="search_files",
            description="Search for files by path segment (case-insensitive). Use to locate files by partial name or path.",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Path segment to search for (e.g. 'auth.py', 'src/utils'). Case-insensitive substring match.",
                    },
                    "glob": {
                        "type": "string",
                        "description": "Optional glob pattern to further filter (e.g. '*.py', '**/*.ts').",
                    },
                },
                "required": ["pattern"],
                "additionalProperties": False,
            },
        ),
        "grep_text": ToolSpec(
            name="grep_text",
            description="Search for text in repository files using ripgrep (or Python fallback). Returns matching lines with paths and line numbers.",
            parameters={
                "type": "object",
                "properties": {
                    "needle": {
                        "type": "string",
                        "description": "Text to search for (literal string, not regex).",
                    },
                    "path": {
                        "type": "string",
                        "description": "Optional subdirectory scope (e.g. 'src/').",
                    },
                    "glob": {
                        "type": "string",
                        "description": "Optional glob pattern to filter files (e.g. '*.py').",
                    },
                    "ignore_case": {
                        "type": "boolean",
                        "description": "Case-insensitive search. Default: false.",
                    },
                },
                "required": ["needle"],
                "additionalProperties": False,
            },
        ),
        "read_file": ToolSpec(
            name="read_file",
            description=f"Read a file with absolute line numbers. Max {MAX_LINES} lines, 100KB, and 2000 chars/line. Returns total lines, EOF status, and truncation info.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative file path inside the repository.",
                    },
                    "line_offset": {
                        "type": "integer",
                        "description": "Line to start reading from (1-based). Negative values read from the end (e.g. -100 = last 100 lines). Default: 1.",
                        "default": 1,
                    },
                    "n_lines": {
                        "type": "integer",
                        "description": f"Number of lines to read. Default: {MAX_LINES}.",
                        "default": MAX_LINES,
                    },
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        ),
        "list_directory": ToolSpec(
            name="list_directory",
            description="Show a 2-level directory tree to understand project structure. Use before reading files to orient yourself.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Subdirectory to list. Omit or use empty string for repo root.",
                        "default": "",
                    },
                },
                "additionalProperties": False,
            },
        ),
        "read_multiple_files": ToolSpec(
            name="read_multiple_files",
            description="Read up to 10 short files at once with a total 50KB budget. Useful for reading related files together.",
            parameters={
                "type": "object",
                "properties": {
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of relative file paths to read.",
                    },
                    "line_offset": {
                        "type": "integer",
                        "description": "Line to start reading from for all files. Default: 1.",
                        "default": 1,
                    },
                },
                "required": ["paths"],
                "additionalProperties": False,
            },
        ),
        "trace_flow": ToolSpec(
            name="trace_flow",
            description="Trace a likely Python call chain for a function, class, or method using static analysis. Best for CLI entrypoints and top-level flow questions.",
            parameters={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Function, class, or method symbol to trace (for example 'ask' or 'AgentLoop.run').",
                    },
                    "path": {
                        "type": "string",
                        "description": "Optional relative file path that anchors the starting symbol.",
                    },
                },
                "required": ["symbol"],
                "additionalProperties": False,
            },
        ),
    }
    project_map = scan_project_map(config.repo_root)
    project_map_summary = render_project_map_summary(project_map)
    return RuntimeState(
        repo_root=config.repo_root,
        system_prompt=f"{load_system_prompt()}\n\n{project_map_summary}",
        llm=llm,
        max_steps=max_steps if max_steps is not None else config.max_steps,
        read_max_lines=read_max_lines if read_max_lines is not None else config.read_max_lines,
        project_map_summary=project_map_summary,
        tools=tools,
    )
