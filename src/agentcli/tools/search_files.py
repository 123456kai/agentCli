from pathlib import Path


def search_files(repo_root: Path, pattern: str) -> list[str]:
    matches: list[str] = []
    for path in repo_root.rglob("*"):
        if path.is_file() and pattern.lower() in path.name.lower():
            matches.append(path.relative_to(repo_root).as_posix())
    return sorted(matches)[:20]
