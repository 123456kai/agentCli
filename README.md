# agentCli

Source-reading agent CLI for repository understanding and note generation.

## DeepSeek setup

```bash
uv sync --extra dev
export DEEPSEEK_API_KEY="your-key"
export DEEPSEEK_MODEL="deepseek-v4-flash"
```

Optional:

```bash
export DEEPSEEK_BASE_URL="https://api.deepseek.com"
```

## Real usage

```bash
uv run agentcli ask --repo /path/to/repo "Where is the entry point?"
uv run agentcli note --repo /path/to/repo "Explain the auth flow"
```

## Notes

- The project now uses DeepSeek through the OpenAI-compatible Chat Completions API.
- If `DEEPSEEK_API_KEY` is missing, the CLI will stop with a clear error.
- The default model is `deepseek-v4-flash`.
