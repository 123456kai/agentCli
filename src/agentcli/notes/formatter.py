import re


def make_note_slug(question: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", question.lower()).strip("-")
    return slug or "source-note"


def render_note(question: str, answer: str) -> str:
    return f"# {question}\n\n{answer}\n"
