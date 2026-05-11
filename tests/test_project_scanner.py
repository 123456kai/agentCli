import json
from pathlib import Path

from agentcli.analysis.project_scanner import scan_project_map


def test_scan_project_map_detects_python_cli_project(tmp_path: Path) -> None:
    (tmp_path / "src" / "demo").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "demo" / "cli.py").write_text("import typer\napp = typer.Typer()\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# demo\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "demo"
dependencies = ["typer>=0.12"]

[project.scripts]
demo = "demo.cli:app"
""".strip(),
        encoding="utf-8",
    )

    project_map = scan_project_map(tmp_path)

    assert "python" in project_map.tech_stack
    assert "typer" in project_map.tech_stack
    assert any(candidate.path == "src/demo/cli.py" for candidate in project_map.entry_candidates)
    assert any(node.path == "src" and node.role == "application source" for node in project_map.nodes)
    assert project_map.test_directories == ["tests"]


def test_scan_project_map_detects_node_project(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "index.js").write_text("console.log('hi')\n", encoding="utf-8")
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "name": "demo-node",
                "scripts": {"start": "node src/index.js"},
            }
        ),
        encoding="utf-8",
    )

    project_map = scan_project_map(tmp_path)

    assert "node" in project_map.tech_stack
    assert any(candidate.path == "src/index.js" for candidate in project_map.entry_candidates)
    assert any(node.path == "src" for node in project_map.nodes)
