from __future__ import annotations

import ast
import tomllib
from pathlib import Path

from agentcli.repo_guard import walk_filtered


def _python_files(repo_root: Path, path: str | None = None) -> list[Path]:
    files = walk_filtered(repo_root, scope=path)
    return [file for file in files if file.suffix == ".py"]


def _relative(repo_root: Path, path: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def find_definitions(repo_root: Path, symbol: str, path: str | None = None) -> dict[str, object]:
    if not symbol:
        return {"error": "symbol is required", "kind": "bad_param"}

    matches: list[dict[str, object]] = []
    for file_path in _python_files(repo_root, path):
        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == symbol:
                matches.append({
                    "path": _relative(repo_root, file_path),
                    "line": node.lineno,
                    "kind": type(node).__name__,
                    "symbol": symbol,
                })

    return {"kind": "symbol_definitions", "symbol": symbol, "matches": matches}


def find_references(repo_root: Path, symbol: str, path: str | None = None) -> dict[str, object]:
    if not symbol:
        return {"error": "symbol is required", "kind": "bad_param"}

    matches: list[dict[str, object]] = []
    for file_path in _python_files(repo_root, path):
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for line_no, line in enumerate(lines, start=1):
            if symbol in line:
                matches.append({
                    "path": _relative(repo_root, file_path),
                    "line": line_no,
                    "preview": line.strip(),
                    "symbol": symbol,
                })

    return {"kind": "symbol_references", "symbol": symbol, "matches": matches}


def trace_cli_command(repo_root: Path, command: str) -> dict[str, object]:
    if not command:
        return {"error": "command is required", "kind": "bad_param"}

    pyproject = repo_root.resolve() / "pyproject.toml"
    if not pyproject.exists():
        return {"error": "pyproject.toml not found", "kind": "not_found"}

    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError) as exc:
        return {"error": f"Could not read pyproject.toml: {exc}", "kind": "parse_error"}

    scripts = data.get("project", {}).get("scripts", {})
    target = scripts.get(command)
    if not target:
        return {"error": f"Command '{command}' not found in project.scripts", "kind": "not_found"}

    module_name, _, attribute = str(target).partition(":")
    module_path = Path("src") / Path(*module_name.split("."))
    candidate = repo_root.resolve() / module_path.with_suffix(".py")
    path = candidate.relative_to(repo_root.resolve()).as_posix() if candidate.exists() else None
    return {
        "kind": "cli_trace",
        "command": command,
        "target": target,
        "module": module_name,
        "attribute": attribute or None,
        "path": path,
    }


def inspect_tests(repo_root: Path) -> dict[str, object]:
    test_files: list[str] = []
    test_dirs: set[str] = set()
    for file_path in walk_filtered(repo_root):
        rel = _relative(repo_root, file_path)
        parts = Path(rel).parts
        is_test_file = file_path.name.startswith("test_") or file_path.name.endswith("_test.py")
        in_test_dir = any(part in {"test", "tests"} for part in parts)
        if is_test_file or in_test_dir:
            test_files.append(rel)
            if parts:
                test_dirs.add(parts[0])

    return {
        "kind": "test_inspection",
        "test_directories": sorted(test_dirs),
        "test_files": sorted(test_files),
    }
