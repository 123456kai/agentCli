from pathlib import Path

import typer
from rich.console import Console

from agentcli.agent_loop import AgentLoop
from agentcli.llm.adapter import DeepSeekOpenAIAdapter
from agentcli.notes import make_note_slug, render_note
from agentcli.runtime import build_runtime
from agentcli.tools.save_note import save_note

app = typer.Typer(help="Source-reading agent CLI.")
console = Console()


def build_adapter():
    runtime = build_runtime(Path.cwd())
    if not runtime.llm.api_key:
        raise RuntimeError("Missing DEEPSEEK_API_KEY. Please export it before running agentcli.")
    return DeepSeekOpenAIAdapter(
        api_key=runtime.llm.api_key,
        base_url=runtime.llm.base_url,
        model=runtime.llm.model,
    )


@app.command()
def ask(question: str, repo: Path = typer.Option(Path.cwd(), "--repo")) -> None:
    runtime = build_runtime(repo)
    try:
        adapter = build_adapter()
    except RuntimeError as exc:
        raise typer.BadParameter(str(exc)) from exc
    loop = AgentLoop(runtime=runtime, adapter=adapter)
    console.print(loop.run(question))


@app.command()
def note(question: str, repo: Path = typer.Option(Path.cwd(), "--repo")) -> None:
    runtime = build_runtime(repo)
    try:
        adapter = build_adapter()
    except RuntimeError as exc:
        raise typer.BadParameter(str(exc)) from exc
    loop = AgentLoop(runtime=runtime, adapter=adapter)
    answer = loop.run(question)
    slug = make_note_slug(question)
    note_path = save_note(runtime.repo_root / "notes", slug, render_note(question, answer))
    console.print(str(note_path))
