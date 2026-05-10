from pathlib import Path

from agentcli.runtime import build_runtime


def test_build_runtime_loads_repo_and_prompt(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# demo\n", encoding="utf-8")
    runtime = build_runtime(tmp_path)
    assert runtime.repo_root == tmp_path
    assert "read and understand code" in runtime.system_prompt.lower()
    assert set(runtime.tools) == {"search_files", "grep_text", "read_file", "list_directory", "read_multiple_files"}
    assert "save_note" not in runtime.tools


def test_build_runtime_loads_deepseek_defaults_and_tool_schema(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    runtime = build_runtime(tmp_path)
    assert runtime.llm.api_key == "test-key"
    assert runtime.llm.base_url == "https://api.deepseek.com"
    assert runtime.llm.model == "deepseek-v4-flash"
    assert runtime.tools["read_file"].parameters["type"] == "object"


def test_read_file_schema_uses_line_offset_not_start(tmp_path: Path) -> None:
    runtime = build_runtime(tmp_path)
    params = runtime.tools["read_file"].parameters
    assert "line_offset" in params["properties"]
    assert "n_lines" in params["properties"]
    assert "start" not in params["properties"]
    assert "end" not in params["properties"]
