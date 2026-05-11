import re

from agentcli.analysis.models import AnalysisResult

_HEADING_RE = re.compile(r"^\s*##+\s*(.+?)\s*$")
_CODE_RE = re.compile(r"`([^`]+)`")


def _normalize_heading(title: str) -> str:
    normalized = title.strip().lower()
    if "conclusion" in normalized or "结论" in normalized:
        return "conclusion"
    if "key file" in normalized or "关键文件" in normalized:
        return "key_files"
    if "reading order" in normalized or "reading path" in normalized or "建议阅读顺序" in normalized:
        return "reading_order"
    if "uncertaint" in normalized or "不确定" in normalized:
        return "uncertainties"
    return "other"


def _strip_list_marker(line: str) -> str:
    return re.sub(r"^\s*(?:[-*]|\d+\.)\s*", "", line).strip()


def _extract_path_or_text(line: str) -> str:
    match = _CODE_RE.search(line)
    if match:
        return match.group(1).strip()
    cleaned = _strip_list_marker(line)
    cleaned = re.split(r"\s[-:]\s", cleaned, maxsplit=1)[0].strip()
    return cleaned


def _extract_lines(section: list[str]) -> list[str]:
    return [line.strip() for line in section if line.strip()]


def parse_analysis_result(answer: str) -> AnalysisResult:
    current = "preamble"
    sections: dict[str, list[str]] = {current: []}

    for line in answer.splitlines():
        match = _HEADING_RE.match(line)
        if match:
            current = _normalize_heading(match.group(1))
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)

    conclusion_lines = _extract_lines(sections.get("conclusion", []))
    if not conclusion_lines:
        conclusion_lines = _extract_lines(sections.get("preamble", []))
    conclusion = "\n".join(conclusion_lines).strip() or answer.strip()

    key_files = [
        _extract_path_or_text(line)
        for line in _extract_lines(sections.get("key_files", []))
    ]
    reading_order = [
        _extract_path_or_text(line)
        for line in _extract_lines(sections.get("reading_order", []))
    ]
    uncertainties = [
        _strip_list_marker(line)
        for line in _extract_lines(sections.get("uncertainties", []))
    ]

    return AnalysisResult(
        answer=answer,
        conclusion=conclusion,
        key_files=[item for item in key_files if item],
        reading_order=[item for item in reading_order if item],
        uncertainties=[item for item in uncertainties if item],
    )
