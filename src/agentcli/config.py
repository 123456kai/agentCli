import os
import tomllib
from pathlib import Path

from pydantic import BaseModel, Field


class AgentCliConfig(BaseModel):
    model: str = "deepseek-v4-flash"
    base_url: str = "https://api.deepseek.com"
    max_steps: int = Field(default=50, ge=1, le=100)
    read_max_lines: int = Field(default=160, ge=20, le=400)
    grep_head_limit: int = Field(default=30, ge=1, le=200)
    note_output_dir: str = ""
    ignore_names: list[str] = Field(default_factory=list)

    @classmethod
    def from_file(cls, path: Path) -> "AgentCliConfig":
        if not path.exists():
            return cls()
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            return cls.model_validate(data)
        except (tomllib.TOMLDecodeError, ValueError) as exc:
            raise ValueError(f"Invalid config file '{path}': {exc}") from exc


def _env_overrides() -> dict[str, object]:
    """Return only the config keys that have corresponding env vars set."""
    overrides: dict[str, object] = {}
    mapping = {
        "AGENTCLI_MODEL": ("model", str),
        "AGENTCLI_BASE_URL": ("base_url", str),
        "AGENTCLI_MAX_STEPS": ("max_steps", int),
        "AGENTCLI_READ_MAX_LINES": ("read_max_lines", int),
        "AGENTCLI_GREP_HEAD_LIMIT": ("grep_head_limit", int),
        "AGENTCLI_NOTE_OUTPUT_DIR": ("note_output_dir", str),
    }
    for env_key, (field_name, cast) in mapping.items():
        if env_key in os.environ:
            overrides[field_name] = cast(os.environ[env_key])
    return overrides


def resolve_config(
    repo: Path,
    cli_model: str | None = None,
    cli_base_url: str | None = None,
    cli_max_steps: int | None = None,
    cli_read_max_lines: int | None = None,
) -> AgentCliConfig:
    """Resolve config with priority: CLI args > env vars > repo config file > defaults."""
    # Start with defaults
    config = AgentCliConfig()

    # Layer 1: repo config file
    config_path = repo / ".agentcli.toml"
    if config_path.exists():
        try:
            file_config = AgentCliConfig.from_file(config_path)
            config = config.model_copy(update=file_config.model_dump(exclude_defaults=True))
        except ValueError:
            pass

    # Layer 2: env vars
    env_overrides = _env_overrides()
    if env_overrides:
        config = config.model_copy(update=env_overrides)

    # Layer 3: CLI args (highest priority)
    cli_overrides: dict[str, object] = {}
    if cli_model is not None:
        cli_overrides["model"] = cli_model
    if cli_base_url is not None:
        cli_overrides["base_url"] = cli_base_url
    if cli_max_steps is not None:
        cli_overrides["max_steps"] = cli_max_steps
    if cli_read_max_lines is not None:
        cli_overrides["read_max_lines"] = cli_read_max_lines
    if cli_overrides:
        config = config.model_copy(update=cli_overrides)

    return config
