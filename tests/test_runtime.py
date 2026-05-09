from pathlib import Path

from agentcli.runtime import build_runtime


def test_build_runtime_loads_repo_and_prompt(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# demo\n", encoding="utf-8")
    runtime = build_runtime(tmp_path)
    assert runtime.repo_root == tmp_path
    assert "read code" in runtime.system_prompt.lower()
    assert set(runtime.tools) == {"search_files", "grep_text", "read_file", "save_note"}
