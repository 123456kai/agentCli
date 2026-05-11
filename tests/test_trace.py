from pathlib import Path

from agentcli.analysis.trace import trace_python_flow
from agentcli.runtime import build_runtime


def test_trace_python_flow_follows_local_helper_and_class_method(tmp_path: Path) -> None:
    (tmp_path / "src" / "demo").mkdir(parents=True)
    (tmp_path / "src" / "demo" / "cli.py").write_text(
        """
from demo.runtime import build_runtime
from demo.loop import AgentLoop


def ask() -> None:
    runtime = build_runtime()
    loop = AgentLoop(runtime)
    loop.run()
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "src" / "demo" / "runtime.py").write_text(
        """
def build_runtime() -> str:
    return "runtime"
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "src" / "demo" / "loop.py").write_text(
        """
class AgentLoop:
    def __init__(self, runtime: str) -> None:
        self.runtime = runtime

    def run(self) -> str:
        return self.runtime
""".strip(),
        encoding="utf-8",
    )

    result = trace_python_flow(tmp_path, "ask", path="src/demo/cli.py")

    assert result["kind"] == "call_chain"
    step_symbols = [step["symbol"] for step in result["steps"]]
    step_paths = [step["path"] for step in result["steps"]]
    assert "ask" in step_symbols
    assert "build_runtime" in step_symbols
    assert "AgentLoop.run" in step_symbols
    assert "src/demo/runtime.py" in step_paths
    assert "src/demo/loop.py" in step_paths


def test_runtime_registers_trace_flow_tool(tmp_path: Path) -> None:
    runtime = build_runtime(tmp_path)

    assert "trace_flow" in runtime.tools
