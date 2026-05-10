import fnmatch
from pathlib import Path

from agentcli.repo_guard import enumerate_repo_files


def search_files(
    repo_root: Path,
    pattern: str,
    glob: str | None = None,
    head_limit: int = 20,
) -> dict[str, object]:
    """Search files by path segment match, with optional glob filtering."""
    if not pattern:
        return {"error": "pattern cannot be empty.", "kind": "bad_param"}

    files = enumerate_repo_files(repo_root)
    matches: list[str] = []

    for rel_path in files:
        if len(matches) >= head_limit:
            break
        # Match pattern as a path segment substring (case-insensitive for convenience)
        if pattern.lower() in rel_path.lower():
            if glob and not fnmatch.fnmatch(rel_path, glob):
                continue
            matches.append(rel_path)

    return {
        "kind": "search_results",
        "pattern": pattern,
        "matches": sorted(matches),
        "total_matches": len(matches),
        "truncated": len(matches) >= head_limit,
    }
