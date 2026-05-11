import subprocess
from pathlib import Path

from agentcli.repo_guard import (
    enumerate_repo_files,
    is_ignored,
    is_sensitive_path,
    resolve_safe_path,
)

_RG_ARGS = [
    "--no-heading",
    "--with-filename",
    "--line-number",
    "--color=never",
    "--no-config",
    "--fixed-strings",
    "-z",
]


def _grep_with_rg(
    repo_root: Path,
    needle: str,
    scope: str | None,
    glob: str | None,
    ignore_case: bool,
    head_limit: int,
) -> dict[str, object]:
    """Run ripgrep and return structured results."""
    resolved = repo_root.resolve()
    cmd: list[str] = [
        "rg",
        *_RG_ARGS,
    ]

    # Suppress ignored directories via .gitignore-style rules
    cmd.extend(["--glob", "!.git/*"])
    cmd.extend(["--glob", "!**/node_modules/**"])
    cmd.extend(["--glob", "!**/__pycache__/**"])
    cmd.extend(["--glob", "!**/.venv/**"])

    if ignore_case:
        cmd.append("-i")
    if glob:
        cmd.extend(["--glob", glob])
    cmd.append("--")
    cmd.append(needle)

    search_dir = resolved
    if scope:
        try:
            safe = resolve_safe_path(resolved, scope)
            if safe.is_dir():
                search_dir = safe
        except ValueError:
            pass

    cmd.append(str(search_dir))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return _grep_with_python(repo_root, needle, scope, glob, ignore_case, head_limit)

    if result.returncode not in (0, 1):
        return _grep_with_python(repo_root, needle, scope, glob, ignore_case, head_limit)

    matches: list[dict[str, object]] = []
    for entry in result.stdout.split("\0"):
        if not entry:
            continue
        parts = entry.split(":", 2)
        if len(parts) < 3:
            continue
        file_path, line_no_str, text = parts[0], parts[1], parts[2]
        try:
            line_no = int(line_no_str)
        except ValueError:
            continue
        relative_path = Path(file_path).resolve().relative_to(resolved).as_posix()

        # Skip ignored paths
        path_parts = relative_path.split("/")
        if any(is_ignored(p) for p in path_parts):
            continue
        if is_sensitive_path(relative_path):
            continue

        matches.append(
            {
                "path": relative_path,
                "line": line_no,
                "text": text.strip(),
            }
        )
        if len(matches) >= head_limit:
            break

    return {
        "kind": "grep_results",
        "engine": "rg",
        "matches": matches,
        "total_matches": len(matches),
    }


def _grep_with_python(
    repo_root: Path,
    needle: str,
    scope: str | None,
    glob: str | None,
    ignore_case: bool,
    head_limit: int,
) -> dict[str, object]:
    """Fallback grep using pure Python."""
    resolved = repo_root.resolve()
    search_needle = needle.lower() if ignore_case else needle

    files = enumerate_repo_files(resolved)
    matches: list[dict[str, object]] = []

    for rel_path in files:
        if len(matches) >= head_limit:
            break
        if scope and not rel_path.startswith(scope.rstrip("/") + "/"):
            continue
        if is_sensitive_path(rel_path):
            continue
        if glob:
            import fnmatch
            if not fnmatch.fnmatch(rel_path, glob):
                continue
        try:
            file_path = resolved / rel_path
            for i, line in enumerate(file_path.read_text(encoding="utf-8").splitlines(), start=1):
                if (search_needle in line.lower()) if ignore_case else (needle in line):
                    matches.append(
                        {
                            "path": rel_path,
                            "line": i,
                            "text": line.strip(),
                        }
                    )
                    if len(matches) >= head_limit:
                        break
        except (UnicodeDecodeError, OSError):
            continue

    return {
        "kind": "grep_results",
        "engine": "python",
        "matches": matches,
        "total_matches": len(matches),
    }


def grep_text(
    repo_root: Path,
    needle: str,
    path: str | None = None,
    glob: str | None = None,
    ignore_case: bool = False,
    head_limit: int = 30,
) -> dict[str, object]:
    """Search for text in repository files, preferring ripgrep."""
    if not needle:
        return {"error": "needle cannot be empty.", "kind": "bad_param"}

    return _grep_with_rg(
        repo_root,
        needle,
        scope=path,
        glob=glob,
        ignore_case=ignore_case,
        head_limit=head_limit,
    )
