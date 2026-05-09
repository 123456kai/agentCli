import re
from pathlib import Path


def save_note(output_dir: Path, slug: str, content: str) -> Path:
    clean_slug = re.sub(r"[^a-z0-9-]+", "-", slug.lower()).strip("-") or "note"
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{clean_slug}.md"
    destination.write_text(content, encoding="utf-8")
    return destination
