# agentCli

An interactive source-reading assistant for understanding unfamiliar repositories. It builds a lightweight project map, answers repo questions with evidence, and now supports multi-turn chat sessions for continued analysis.

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Set your API key (DeepSeek)
export DEEPSEEK_API_KEY="your-key"

# Ask a question about a repo
agentcli ask --repo /path/to/repo "Where is the entry point?"

# Start an interactive analysis session
agentcli chat --repo /path/to/repo

# Save answer as a structured Markdown note
agentcli note --repo /path/to/repo "Explain the auth flow"
```

## Configuration

Configuration is resolved in this priority order: **CLI args > environment variables > repo `.agentcli.toml` > defaults**.

### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--repo` | Repository root path | Current directory |
| `--model` | Model name override | `deepseek-v4-flash` |
| `--base-url` | API base URL override | `https://api.deepseek.com` |
| `--max-steps` | Max agent steps (tool calls) | `50` |
| `--read-max-lines` | Max lines per `read_file` | `160` |
| `--format` | Output format: `text` or `json` | `text` |
| `--explain-tools` | Print tool progress while the agent explores | `false` |
| `--output-dir` | Note output directory (note command) | `<repo>/notes` |

### Environment Variables

```bash
export AGENTCLI_MODEL="deepseek-v4-flash"
export AGENTCLI_BASE_URL="https://api.deepseek.com"
export AGENTCLI_MAX_STEPS="50"
export AGENTCLI_READ_MAX_LINES="160"
export AGENTCLI_GREP_HEAD_LIMIT="30"
export AGENTCLI_NOTE_OUTPUT_DIR="/path/to/notes"
```

Backward compatible: `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`, `DEEPSEEK_BASE_URL` are still supported.

### Per-Repo Config (`.agentcli.toml`)

Place a `.agentcli.toml` in the repo root:

```toml
model = "custom-model"
max_steps = 20
read_max_lines = 200
note_output_dir = "docs/notes"
ignore_names = ["generated", "third_party"]
```

## Commands

### `ask` — Ask a question

```bash
agentcli ask "What does the authentication module look like?"

# With options
agentcli ask --repo /path/to/repo --max-steps 15 --format json "Explain the router"

# Show tool progress while investigating
agentcli ask --repo /path/to/repo --explain-tools "Trace the CLI entrypoint"
```

JSON output format:
```json
{
  "question": "What does the authentication module look like?",
  "answer": "## Conclusion\n...",
  "key_files": ["src/app/auth.py"],
  "reading_order": ["README.md", "src/app/auth.py"],
  "uncertainties": ["Runtime-only behavior not verified"]
}
```

### `chat` — Continue the discussion

```bash
# Start a new session
agentcli chat --repo /path/to/repo

# Resume the latest saved session
agentcli chat --repo /path/to/repo --session latest
```

The chat command stores session state under `.agentcli/sessions/` in the target repository so follow-up questions can keep the same project map, focus, and evidence trail.

### `note` — Ask and save as Markdown

```bash
agentcli note "Map the project structure"

# Custom output directory
agentcli note --output-dir ~/my-notes "Explain error handling"
```

Notes are saved with structured sections: Conclusion, Key Files, Reading Order, Uncertainties. Existing notes are rotated (`note.md` → `note-1.md` → `note-2.md`) rather than overwritten.

## Available Tools

The agent has access to these tools when exploring a repository:

| Tool | Description |
|------|-------------|
| `list_directory` | Show 2-level directory tree for project structure |
| `search_files` | Find files by path segment (case-insensitive) |
| `grep_text` | Search file contents (uses ripgrep if available) |
| `read_file` | Read a file with line numbers, safety limits (100KB, 1000 lines) |
| `read_multiple_files` | Read up to 10 files at once (50KB total budget) |
| `trace_flow` | Approximate a Python call chain for entrypoints, helpers, and class methods |

## Safety

- Path traversal (`..`) and out-of-repo reads are blocked
- Binary files, sensitive files (`.env`, credentials), and common ignored directories are excluded from listing, reading, and grep/search output
- File reads have hard limits: 100KB max size, 2000 chars/line, 1000 lines max
- Notes use file rotation to prevent silent overwrites

## What It Is

This project is intentionally focused on source reading, not code execution or repository mutation. It is most useful when you want to:

- map a new repository quickly
- discuss a subsystem over multiple turns
- trace a likely Python entry flow
- save a reading note with evidence and open questions

## Common Issues

**"API key not found"**: Set `DEEPSEEK_API_KEY` or `AGENTCLI_API_KEY` environment variable.

**"Repository path does not exist"**: Use `--repo` to point to an existing directory.

**"ripgrep not found"**: The agent falls back to Python-based search. Install `rg` for faster search.

**Config file errors**: Ensure `.agentcli.toml` is valid TOML. Invalid configs are silently ignored with a fallback to defaults.

## Development

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
```
