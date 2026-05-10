import re
from pathlib import Path


def save_note(output_dir: Path, slug: str, content: str) -> Path:
    """Save a note, rotating existing files so nothing is silently overwritten."""
    clean_slug = re.sub(r"[^a-z0-9-]+", "-", slug.lower()).strip("-") or "note"
    output_dir.mkdir(parents=True, exist_ok=True)

    destination = output_dir / f"{clean_slug}.md"
    if destination.exists():
        base = clean_slug
        counter = 1
        while True:
            destination = output_dir / f"{base}-{counter}.md"
            if not destination.exists():
                break
            counter += 1
            if counter > 100:
                destination = output_dir / f"{base}-{counter}.md"
                break

    destination.write_text(content, encoding="utf-8")
    return destination
