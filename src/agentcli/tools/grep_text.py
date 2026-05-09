from pathlib import Path


def grep_text(repo_root: Path, needle: str) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for index, line in enumerate(lines, start=1):
            if needle.lower() in line.lower():
                results.append(
                    {
                        "path": path.relative_to(repo_root).as_posix(),
                        "line": index,
                        "text": line.strip(),
                    }
                )
                if len(results) >= 30:
                    return results
    return results
