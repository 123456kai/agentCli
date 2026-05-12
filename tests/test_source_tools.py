from pathlib import Path

from agentcli.analysis.symbols import find_definitions, find_references, inspect_tests, trace_cli_command
from agentcli.runtime import build_runtime


def test_symbol_tools_find_python_definitions_and_references(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text(
        "def run():\n"
        "    return helper()\n\n"
        "def helper():\n"
        "    return 'ok'\n",
        encoding="utf-8",
    )

    definitions = find_definitions(tmp_path, "helper")
    references = find_references(tmp_path, "helper")

    assert definitions["matches"][0]["path"] == "src/app.py"
    assert definitions["matches"][0]["line"] == 4
    assert any(match["line"] == 2 for match in references["matches"])


def test_trace_cli_command_reads_pyproject_script_target(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project.scripts]\nagentcli = \"agentcli.cli:app\"\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "agentcli").mkdir(parents=True)
    (tmp_path / "src" / "agentcli" / "cli.py").write_text("app = object()\n", encoding="utf-8")

    result = trace_cli_command(tmp_path, "agentcli")

    assert result["kind"] == "cli_trace"
    assert result["command"] == "agentcli"
    assert result["target"] == "agentcli.cli:app"
    assert result["path"] == "src/agentcli/cli.py"


def test_inspect_tests_lists_test_directories_and_files(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text("def test_app():\n    pass\n", encoding="utf-8")

    result = inspect_tests(tmp_path)

    assert result["kind"] == "test_inspection"
    assert result["test_directories"] == ["tests"]
    assert result["test_files"] == ["tests/test_app.py"]


def test_runtime_registers_enhanced_source_tools(tmp_path: Path) -> None:
    runtime = build_runtime(tmp_path)

    assert "find_references" in runtime.tools
    assert "find_definitions" in runtime.tools
    assert "trace_cli_command" in runtime.tools
    assert "inspect_tests" in runtime.tools
