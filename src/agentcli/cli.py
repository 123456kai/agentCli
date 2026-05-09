from pathlib import Path

import typer
from rich.console import Console

from agentcli.agent_loop import AgentLoop
from agentcli.notes import make_note_slug, render_note
from agentcli.runtime import build_runtime
from agentcli.tools.save_note import save_note

app = typer.Typer(help="Source-reading agent CLI.")
console = Console()


def build_adapter():
    raise NotImplementedError("Provide a real adapter in a later task")


@app.command()
def ask(question: str, repo: Path = typer.Option(Path.cwd(), "--repo")) -> None:
    runtime = build_runtime(repo)
    loop = AgentLoop(runtime=runtime, adapter=build_adapter())
    console.print(loop.run(question))


@app.command()
def note(question: str, repo: Path = typer.Option(Path.cwd(), "--repo")) -> None:
    runtime = build_runtime(repo)
    loop = AgentLoop(runtime=runtime, adapter=build_adapter())
    answer = loop.run(question)
    slug = make_note_slug(question)
    note_path = save_note(runtime.repo_root / "notes", slug, render_note(question, answer))
    console.print(str(note_path))
