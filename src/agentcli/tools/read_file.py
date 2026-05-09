from pathlib import Path


def read_file(path: Path, start: int = 1, end: int = 80) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    start_index = max(start, 1)
    end_index = max(end, start_index)
    excerpt = []
    for line_no in range(start_index, min(end_index, len(lines)) + 1):
        excerpt.append(f"{line_no}: {lines[line_no - 1]}")
    return "\n".join(excerpt)
