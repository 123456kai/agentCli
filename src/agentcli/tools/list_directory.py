from pathlib import Path

from agentcli.repo_guard import is_ignored, resolve_safe_path

ROOT_WIDTH = 30
CHILD_WIDTH = 10


def list_directory(repo_root: Path, path: str = "") -> dict[str, object]:
    """Return a compact tree of *path* (up to 2 levels deep, width-capped)."""
    resolved = repo_root.resolve()
    if path:
        try:
            target = resolve_safe_path(resolved, path)
        except ValueError as exc:
            return {"error": str(exc), "kind": "path_traversal"}
    else:
        target = resolved

    if not target.exists():
        return {"error": f"'{path or '.'}' does not exist.", "kind": "not_found"}
    if not target.is_dir():
        return {"error": f"'{path or '.'}' is not a directory.", "kind": "not_directory"}

    lines: list[str] = []
    try:
        entries = sorted(
            target.iterdir(),
            key=lambda e: (not e.is_dir(), e.name.lower()),
        )
    except OSError as exc:
        return {"error": f"Cannot list '{path or '.'}': {exc}", "kind": "io_error"}

    visible = [e for e in entries if not is_ignored(e.name)]
    shown = visible[:ROOT_WIDTH]
    remaining = len(visible) - len(shown)

    for i, entry in enumerate(shown):
        is_last = (i == len(shown) - 1) and remaining == 0
        connector = "└── " if is_last else "├── "
        suffix = "/" if entry.is_dir() else ""
        lines.append(f"{connector}{entry.name}{suffix}")

        if entry.is_dir():
            child_prefix = "    " if is_last else "│   "
            try:
                child_entries = sorted(
                    entry.iterdir(),
                    key=lambda e: (not e.is_dir(), e.name.lower()),
                )
            except OSError:
                lines.append(f"{child_prefix}└── [not readable]")
                continue

            visible_children = [c for c in child_entries if not is_ignored(c.name)]
            shown_children = visible_children[:CHILD_WIDTH]
            child_remaining = len(visible_children) - len(shown_children)

            for j, child in enumerate(shown_children):
                child_is_last = (j == len(shown_children) - 1) and child_remaining == 0
                child_connector = "└── " if child_is_last else "├── "
                child_suffix = "/" if child.is_dir() else ""
                lines.append(f"{child_prefix}{child_connector}{child.name}{child_suffix}")

            if child_remaining > 0:
                lines.append(f"{child_prefix}└── ... and {child_remaining} more")

    if remaining > 0:
        lines.append(f"└── ... and {remaining} more entries")

    relative = target.relative_to(resolved).as_posix() if target != resolved else "."

    return {
        "kind": "directory_listing",
        "path": relative,
        "content": "\n".join(lines) if lines else "(empty directory)",
        "total_entries": len(visible),
        "shown_entries": len(shown),
    }
