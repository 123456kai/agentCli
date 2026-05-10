import re


def make_note_slug(question: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", question.lower()).strip("-")
    return slug or "source-note"


def render_note(
    question: str,
    answer: str,
    key_files: list[str] | None = None,
    reading_order: list[str] | None = None,
    uncertainties: list[str] | None = None,
) -> str:
    lines: list[str] = []
    lines.append(f"# {question}\n")

    lines.append("## 结论 / Conclusion\n")
    lines.append(answer.strip())
    lines.append("")

    if key_files:
        lines.append("## 关键文件 / Key Files\n")
        for f in key_files:
            lines.append(f"- `{f}`")
        lines.append("")

    if reading_order:
        lines.append("## 建议阅读顺序 / Reading Order\n")
        for i, step in enumerate(reading_order, start=1):
            lines.append(f"{i}. {step}")
        lines.append("")

    if uncertainties:
        lines.append("## 不确定点 / Uncertainties\n")
        for u in uncertainties:
            lines.append(f"- {u}")
        lines.append("")

    return "\n".join(lines)
