import json
from pathlib import Path

import typer
from rich.console import Console

from agentcli.agent_loop import AgentLoop
from agentcli.config import resolve_config
from agentcli.llm.adapter import DeepSeekOpenAIAdapter
from agentcli.notes import make_note_slug, render_note
from agentcli.runtime import build_runtime
from agentcli.tools.save_note import save_note

app = typer.Typer(help="Source-reading agent CLI — understand unfamiliar repositories.")
console = Console()


def _check_api_key() -> str:
    import os

    key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("AGENTCLI_API_KEY")
    if not key:
        raise typer.BadParameter(
            "API key not found. Set DEEPSEEK_API_KEY or AGENTCLI_API_KEY environment variable."
        )
    return key


@app.command()
def ask(
    question: str,
    repo: Path = typer.Option(Path.cwd(), "--repo", help="Repository root directory."),
    max_steps: int | None = typer.Option(None, "--max-steps", help="Maximum agent steps (1-30)."),
    read_max_lines: int | None = typer.Option(None, "--read-max-lines", help="Maximum lines per read_file call."),
    model: str | None = typer.Option(None, "--model", help="Model name override."),
    base_url: str | None = typer.Option(None, "--base-url", help="API base URL override."),
    output_format: str = typer.Option("text", "--format", help="Output format: text or json."),
) -> None:
    """Ask a question about a code repository."""
    if not repo.exists() or not repo.is_dir():
        raise typer.BadParameter(f"Repository path does not exist or is not a directory: {repo}")

    config = resolve_config(
        repo,
        cli_model=model,
        cli_base_url=base_url,
        cli_max_steps=max_steps,
        cli_read_max_lines=read_max_lines,
    )

    runtime = build_runtime(
        repo,
        model=config.model,
        base_url=config.base_url,
        max_steps=config.max_steps,
        read_max_lines=config.read_max_lines,
    )

    api_key = _check_api_key()
    adapter = DeepSeekOpenAIAdapter(
        api_key=api_key,
        base_url=runtime.llm.base_url,
        model=runtime.llm.model,
    )

    loop = AgentLoop(runtime=runtime, adapter=adapter)
    answer = loop.run(question)

    if output_format == "json":
        result = {
            "question": question,
            "answer": answer,
            "key_files": [],
            "reading_order": [],
            "uncertainties": [],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        console.print(answer)


@app.command()
def note(
    question: str,
    repo: Path = typer.Option(Path.cwd(), "--repo", help="Repository root directory."),
    max_steps: int | None = typer.Option(None, "--max-steps", help="Maximum agent steps (1-30)."),
    read_max_lines: int | None = typer.Option(None, "--read-max-lines", help="Maximum lines per read_file call."),
    model: str | None = typer.Option(None, "--model", help="Model name override."),
    base_url: str | None = typer.Option(None, "--base-url", help="API base URL override."),
    output_dir: Path | None = typer.Option(None, "--output-dir", help="Custom note output directory."),
    output_format: str = typer.Option("text", "--format", help="Output format: text or json."),
) -> None:
    """Ask a question and save the answer as a structured Markdown note."""
    if not repo.exists() or not repo.is_dir():
        raise typer.BadParameter(f"Repository path does not exist or is not a directory: {repo}")

    config = resolve_config(
        repo,
        cli_model=model,
        cli_base_url=base_url,
        cli_max_steps=max_steps,
        cli_read_max_lines=read_max_lines,
    )

    runtime = build_runtime(
        repo,
        model=config.model,
        base_url=config.base_url,
        max_steps=config.max_steps,
        read_max_lines=config.read_max_lines,
    )

    api_key = _check_api_key()
    adapter = DeepSeekOpenAIAdapter(
        api_key=api_key,
        base_url=runtime.llm.base_url,
        model=runtime.llm.model,
    )

    loop = AgentLoop(runtime=runtime, adapter=adapter)
    answer = loop.run(question)

    slug = make_note_slug(question)
    notes_dir = output_dir or (runtime.repo_root / "notes")
    note_content = render_note(question, answer)
    note_path = save_note(notes_dir, slug, note_content)

    if output_format == "json":
        result = {
            "question": question,
            "answer": answer,
            "key_files": [],
            "reading_order": [],
            "uncertainties": [],
            "note_path": str(note_path),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        console.print(str(note_path))
