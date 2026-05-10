from pathlib import Path

from agentcli.repo_guard import (
    MAX_BYTES,
    MAX_LINE_LENGTH,
    MAX_LINES,
    is_binary_by_extension,
    is_sensitive_file,
    resolve_safe_path,
)


def read_file(
    repo_root: Path,
    path: str,
    line_offset: int = 1,
    n_lines: int = MAX_LINES,
) -> dict[str, object]:
    """Read a file snippet with absolute line numbers, respecting safety limits."""
    if not path:
        return {"error": "File path cannot be empty.", "kind": "invalid_path"}

    try:
        resolved = resolve_safe_path(repo_root, path)
    except ValueError as exc:
        return {"error": str(exc), "kind": "path_traversal"}

    if not resolved.exists():
        return {"error": f"File '{path}' does not exist.", "kind": "not_found"}
    if resolved.is_dir():
        return {
            "error": f"'{path}' is a directory, not a file. Use search_files or list_directory to explore it.",
            "kind": "is_directory",
        }
    if not resolved.is_file():
        return {"error": f"'{path}' is not a regular file.", "kind": "invalid_path"}
    if is_sensitive_file(resolved):
        return {
            "error": f"'{path}' appears to contain secrets. Reading blocked for security.",
            "kind": "sensitive_file",
        }
    if is_binary_by_extension(resolved):
        return {
            "error": f"'{path}' appears to be a binary file and cannot be read as text.",
            "kind": "binary_file",
        }

    if line_offset == 0:
        return {"error": "line_offset cannot be 0. Use 1 for first line or -1 for last line.", "kind": "bad_param"}
    if n_lines < 1:
        return {"error": "n_lines must be >= 1.", "kind": "bad_param"}

    try:
        text = resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {
            "error": f"'{path}' is not a valid UTF-8 text file.",
            "kind": "binary_file",
        }

    all_lines = text.splitlines()
    total_lines = len(all_lines)

    if line_offset < 0:
        tail_count = min(abs(line_offset), MAX_LINES)
        start_index = max(0, total_lines - tail_count)
        end_index = total_lines
    else:
        start_index = max(0, line_offset - 1)
        end_index = min(total_lines, start_index + min(n_lines, MAX_LINES))

    selected = all_lines[start_index:end_index]
    n_bytes = 0
    result_lines: list[str] = []
    truncated_line_numbers: list[int] = []
    max_bytes_reached = False
    max_lines_reached = False

    for i, raw_line in enumerate(selected):
        absolute_line_no = start_index + i + 1
        if len(raw_line) > MAX_LINE_LENGTH:
            truncated_line_numbers.append(absolute_line_no)
            raw_line = raw_line[:MAX_LINE_LENGTH]
        line_bytes = len(raw_line.encode("utf-8"))
        if n_bytes + line_bytes > MAX_BYTES and result_lines:
            max_bytes_reached = True
            break
        result_lines.append(f"{absolute_line_no:6d}\t{raw_line}")
        n_bytes += line_bytes
        if len(result_lines) >= MAX_LINES:
            max_lines_reached = len(selected) > MAX_LINES
            break

    message_parts: list[str] = []
    if result_lines:
        first_shown = start_index + 1
        last_shown = start_index + len(result_lines)
        message_parts.append(f"{len(result_lines)} lines read (lines {first_shown}-{last_shown})")
    else:
        message_parts.append("0 lines read")
    message_parts.append(f"total lines: {total_lines}")

    if start_index + len(result_lines) >= total_lines:
        message_parts.append("EOF reached")
    if max_lines_reached:
        message_parts.append(f"max {MAX_LINES} lines limit reached")
    if max_bytes_reached:
        message_parts.append(f"max {MAX_BYTES} bytes limit reached")
    if truncated_line_numbers:
        message_parts.append(f"lines {truncated_line_numbers} were truncated (max {MAX_LINE_LENGTH} chars)")

    return {
        "kind": "file_content",
        "path": resolved.relative_to(repo_root.resolve()).as_posix(),
        "total_lines": total_lines,
        "message": " | ".join(message_parts),
        "content": "\n".join(result_lines),
    }
