import json
from pathlib import Path

from agentcli.repo_guard import MAX_BYTES, resolve_safe_path
from agentcli.tools.read_file import read_file

MAX_TOTAL_BYTES = 50 << 10  # 50KB budget for multi-file reads


def read_multiple_files(
    repo_root: Path,
    paths: list[str],
    line_offset: int = 1,
) -> dict[str, object]:
    """Read multiple short files at once, with a total output budget."""
    if not paths:
        return {"error": "At least one path is required.", "kind": "bad_param"}
    if len(paths) > 10:
        return {"error": "Maximum 10 files per read_multiple_files call.", "kind": "bad_param"}

    files: list[dict[str, object]] = []
    total_bytes = 0
    errors: list[dict[str, str]] = []

    for p in paths:
        result = read_file(repo_root, p, line_offset=line_offset, n_lines=200)
        if result.get("kind") != "file_content":
            errors.append({"path": p, "error": str(result.get("error", "unknown"))})
            continue

        content = str(result.get("content", ""))
        file_bytes = len(content.encode("utf-8"))
        if total_bytes + file_bytes > MAX_TOTAL_BYTES:
            files.append({
                "path": result.get("path", p),
                "message": "Skipped: would exceed total output budget.",
            })
            continue

        files.append({
            "path": result.get("path", p),
            "total_lines": result.get("total_lines"),
            "message": result.get("message"),
            "content": content,
        })
        total_bytes += file_bytes

    return {
        "kind": "multi_file_content",
        "files": files,
        "errors": errors,
        "total_files_read": len([f for f in files if "content" in f]),
        "total_size_bytes": total_bytes,
    }
