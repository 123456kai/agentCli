from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def make_cache_key(file_path: str, content_hash: str, line_start: int, line_end: int) -> str:
    return f"{file_path}:{content_hash}:{line_start}-{line_end}"


class NarrativeCache:
    """JSON-file-backed cache for AI-generated code narratives.

    Key: ``file_path:content_hash:line_start-line_end``
    Value: ``{"summary": str, "design_notes": str, "warnings": str | None, "generated_at": str}``
    """

    def __init__(self, cache_dir: Path) -> None:
        self._dir = cache_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._store_path = self._dir / "narratives.json"
        self._data: dict[str, dict[str, object]] = self._load()

    def _load(self) -> dict[str, dict[str, object]]:
        if self._store_path.exists():
            try:
                return json.loads(self._store_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save(self) -> None:
        self._store_path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get(self, key: str) -> dict[str, object] | None:
        return self._data.get(key)

    def set(self, key: str, value: dict[str, object]) -> None:
        self._data[key] = value
        self._save()

    def get_by_prefix(self, file_path: str, content_hash: str) -> list[tuple[str, dict[str, object]]]:
        prefix = f"{file_path}:{content_hash}:"
        return [(k, v) for k, v in self._data.items() if k.startswith(prefix)]
