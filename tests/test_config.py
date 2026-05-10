from pathlib import Path

from agentcli.config import AgentCliConfig, resolve_config


def test_config_defaults() -> None:
    config = AgentCliConfig()
    assert config.model == "deepseek-v4-flash"
    assert config.base_url == "https://api.deepseek.com"
    assert config.max_steps == 12
    assert config.read_max_lines == 160
    assert config.grep_head_limit == 30


def test_config_from_file(tmp_path: Path) -> None:
    config_path = tmp_path / ".agentcli.toml"
    config_path.write_text(
        """\
model = "custom-model"
max_steps = 20
""",
        encoding="utf-8",
    )
    config = AgentCliConfig.from_file(config_path)
    assert config.model == "custom-model"
    assert config.max_steps == 20
    assert config.base_url == "https://api.deepseek.com"  # default


def test_config_from_missing_file(tmp_path: Path) -> None:
    config = AgentCliConfig.from_file(tmp_path / "nonexistent.toml")
    assert config.model == "deepseek-v4-flash"


def test_config_from_empty_file(tmp_path: Path) -> None:
    config_path = tmp_path / ".agentcli.toml"
    config_path.write_text("", encoding="utf-8")
    config = AgentCliConfig.from_file(config_path)
    assert config.model == "deepseek-v4-flash"


def test_resolve_config_cli_priority(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTCLI_MODEL", "env-model")
    result = resolve_config(tmp_path, cli_model="cli-model")
    assert result.model == "cli-model"


def test_resolve_config_env_priority(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTCLI_MODEL", "env-model")
    result = resolve_config(tmp_path)
    assert result.model == "env-model"


def test_resolve_config_repo_file_priority(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / ".agentcli.toml"
    config_path.write_text('model = "repo-model"', encoding="utf-8")
    monkeypatch.delenv("AGENTCLI_MODEL", raising=False)
    result = resolve_config(tmp_path)
    assert result.model == "repo-model"


def test_resolve_config_cli_overrides_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTCLI_MAX_STEPS", "15")
    result = resolve_config(tmp_path, cli_max_steps=5)
    assert result.max_steps == 5


def test_resolve_config_env_overrides_file(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / ".agentcli.toml"
    config_path.write_text('model = "repo-model"\nmax_steps = 8', encoding="utf-8")
    monkeypatch.setenv("AGENTCLI_MAX_STEPS", "20")
    result = resolve_config(tmp_path)
    assert result.model == "repo-model"  # env doesn't set model
    assert result.max_steps == 20  # env overrides file for steps
