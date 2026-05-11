from agentcli.analysis.models import ProjectMap


def render_project_map_summary(project_map: ProjectMap) -> str:
    lines: list[str] = []
    lines.append("## Project Map Pre-Scan")
    lines.append(f"- Repo root: {project_map.repo_root}")
    if project_map.tech_stack:
        lines.append(f"- Tech stack: {', '.join(project_map.tech_stack)}")
    if project_map.important_files:
        lines.append(f"- Important files: {', '.join(project_map.important_files[:5])}")
    if project_map.entry_candidates:
        lines.append("- Entry candidates:")
        for candidate in project_map.entry_candidates[:5]:
            lines.append(f"  - {candidate.path}: {candidate.reason}")
    if project_map.nodes:
        lines.append("- Key directories:")
        for node in project_map.nodes[:5]:
            lines.append(f"  - {node.path}: {node.role}")
    if project_map.test_directories:
        lines.append(f"- Test directories: {', '.join(project_map.test_directories)}")
    return "\n".join(lines)
