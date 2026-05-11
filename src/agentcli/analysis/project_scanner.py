import json
import re
import tomllib
from pathlib import Path

from agentcli.analysis.models import EntryCandidate, MapNode, ProjectMap
from agentcli.repo_guard import enumerate_repo_files


def _top_level_role(name: str) -> str | None:
    lowered = name.lower()
    if lowered in {"src", "app", "lib"}:
        return "application source"
    if lowered in {"tests", "test"}:
        return "test suite"
    if lowered == "docs":
        return "documentation"
    if lowered in {"scripts", "bin"}:
        return "automation and entry scripts"
    return None


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def _append_unique_candidate(candidates: list[EntryCandidate], candidate: EntryCandidate) -> None:
    if all(existing.path != candidate.path for existing in candidates):
        candidates.append(candidate)


def _parse_python_module_target(module_target: str, files: set[str]) -> str | None:
    module_path = module_target.split(":", 1)[0].replace(".", "/")
    direct = f"{module_path}.py"
    src_scoped = f"src/{module_path}.py"
    if direct in files:
        return direct
    if src_scoped in files:
        return src_scoped
    return None


def _scan_pyproject(repo_root: Path, files: set[str], tech_stack: list[str], important_files: list[str], candidates: list[EntryCandidate]) -> None:
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.exists():
        return
    _append_unique(tech_stack, "python")
    _append_unique(important_files, "pyproject.toml")

    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return

    dependencies = data.get("project", {}).get("dependencies", [])
    for dependency in dependencies:
        lowered = str(dependency).lower()
        if lowered.startswith("typer"):
            _append_unique(tech_stack, "typer")

    scripts = data.get("project", {}).get("scripts", {})
    for command_name, target in scripts.items():
        resolved = _parse_python_module_target(str(target), files)
        if resolved:
            _append_unique_candidate(
                candidates,
                EntryCandidate(
                    path=resolved,
                    reason=f"console script '{command_name}' from pyproject.toml",
                    confidence="high",
                ),
            )


def _scan_package_json(repo_root: Path, files: set[str], tech_stack: list[str], important_files: list[str], candidates: list[EntryCandidate]) -> None:
    package_json = repo_root / "package.json"
    if not package_json.exists():
        return
    _append_unique(tech_stack, "node")
    _append_unique(important_files, "package.json")

    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return

    for script_name, command in data.get("scripts", {}).items():
        match = re.search(r"(?:node|tsx?|bun)\s+([^\s]+)", str(command))
        if match and match.group(1) in files:
            _append_unique_candidate(
                candidates,
                EntryCandidate(
                    path=match.group(1),
                    reason=f"script '{script_name}' from package.json",
                    confidence="high",
                ),
            )

    bin_field = data.get("bin")
    if isinstance(bin_field, str) and bin_field in files:
        _append_unique_candidate(
            candidates,
            EntryCandidate(
                path=bin_field,
                reason="CLI binary from package.json",
                confidence="high",
            ),
        )


def scan_project_map(repo_root: Path) -> ProjectMap:
    files = set(enumerate_repo_files(repo_root))
    top_levels = {path.split("/", 1)[0] for path in files if "/" in path}
    for child in repo_root.iterdir():
        if child.is_dir():
            top_levels.add(child.name)
    top_levels = sorted(top_levels)

    tech_stack: list[str] = []
    important_files: list[str] = []
    entry_candidates: list[EntryCandidate] = []
    nodes: list[MapNode] = []
    test_directories: list[str] = []

    _scan_pyproject(repo_root, files, tech_stack, important_files, entry_candidates)
    _scan_package_json(repo_root, files, tech_stack, important_files, entry_candidates)

    if "Cargo.toml" in files:
        _append_unique(tech_stack, "rust")
        _append_unique(important_files, "Cargo.toml")
    if "go.mod" in files:
        _append_unique(tech_stack, "go")
        _append_unique(important_files, "go.mod")
    if "README.md" in files:
        _append_unique(important_files, "README.md")

    for top_level in top_levels:
        role = _top_level_role(top_level)
        if role:
            nodes.append(MapNode(path=top_level, role=role))
        if top_level.lower() in {"tests", "test"} and top_level not in test_directories:
            test_directories.append(top_level)

    for fallback in ("main.py", "src/main.py", "app.py", "manage.py", "src/index.js"):
        if fallback in files:
            _append_unique_candidate(
                entry_candidates,
                EntryCandidate(
                    path=fallback,
                    reason="common application entrypoint filename",
                    confidence="medium",
                ),
            )

    return ProjectMap(
        repo_root=repo_root.resolve().as_posix(),
        tech_stack=tech_stack,
        nodes=nodes,
        entry_candidates=entry_candidates,
        important_files=important_files,
        test_directories=test_directories,
    )
