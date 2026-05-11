import json
from pathlib import Path

import typer
from rich.console import Console

from agentcli.agent_loop import AgentLoop
from agentcli.analysis import parse_analysis_result
from agentcli.config import resolve_config
from agentcli.llm.adapter import DeepSeekOpenAIAdapter
from agentcli.notes import make_note_slug, render_note
from agentcli.runtime import build_runtime
from agentcli.session import AnalysisSession
from agentcli.session_store import SessionStore
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


def _build_runtime_and_adapter(
    repo: Path,
    model: str | None,
    base_url: str | None,
    max_steps: int | None,
    read_max_lines: int | None,
):
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
    return runtime, adapter


def _build_progress_callback(enabled: bool):
    if not enabled:
        return None

    def _callback(event: dict[str, object]) -> None:
        tool_name = str(event["tool_name"])
        result = dict(event["result"])
        kind = str(result.get("kind", "unknown"))
        extra = []
        if "path" in result:
            extra.append(f"path={result['path']}")
        if "matches" in result:
            extra.append(f"matches={len(result['matches'])}")
        if result.get("truncated"):
            extra.append("truncated=true")
        details = f" ({', '.join(extra)})" if extra else ""
        console.print(f"[dim][tool][/dim] {tool_name} -> {kind}{details}")

    return _callback


@app.command()
def ask(
    question: str,
    repo: Path = typer.Option(Path.cwd(), "--repo", help="Repository root directory."),
    max_steps: int | None = typer.Option(None, "--max-steps", help="Maximum agent steps (1-30)."),
    read_max_lines: int | None = typer.Option(None, "--read-max-lines", help="Maximum lines per read_file call."),
    model: str | None = typer.Option(None, "--model", help="Model name override."),
    base_url: str | None = typer.Option(None, "--base-url", help="API base URL override."),
    output_format: str = typer.Option("text", "--format", help="Output format: text or json."),
    explain_tools: bool = typer.Option(False, "--explain-tools", help="Show tool progress during execution."),
) -> None:
    """Ask a question about a code repository."""
    if not repo.exists() or not repo.is_dir():
        raise typer.BadParameter(f"Repository path does not exist or is not a directory: {repo}")

    runtime, adapter = _build_runtime_and_adapter(repo, model, base_url, max_steps, read_max_lines)

    loop = AgentLoop(runtime=runtime, adapter=adapter, progress_callback=_build_progress_callback(explain_tools))
    answer = loop.run(question)
    analysis = parse_analysis_result(answer)

    if output_format == "json":
        result = {
            "question": question,
            "answer": answer,
            "key_files": analysis.key_files,
            "reading_order": analysis.reading_order,
            "uncertainties": analysis.uncertainties,
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
    explain_tools: bool = typer.Option(False, "--explain-tools", help="Show tool progress during execution."),
) -> None:
    """Ask a question and save the answer as a structured Markdown note."""
    if not repo.exists() or not repo.is_dir():
        raise typer.BadParameter(f"Repository path does not exist or is not a directory: {repo}")

    runtime, adapter = _build_runtime_and_adapter(repo, model, base_url, max_steps, read_max_lines)
    loop = AgentLoop(runtime=runtime, adapter=adapter, progress_callback=_build_progress_callback(explain_tools))
    answer = loop.run(question)
    analysis = parse_analysis_result(answer)

    slug = make_note_slug(question)
    notes_dir = output_dir or (runtime.repo_root / "notes")
    note_content = render_note(
        question,
        analysis.conclusion,
        key_files=analysis.key_files,
        reading_order=analysis.reading_order,
        uncertainties=analysis.uncertainties,
    )
    note_path = save_note(notes_dir, slug, note_content)

    if output_format == "json":
        result = {
            "question": question,
            "answer": answer,
            "key_files": analysis.key_files,
            "reading_order": analysis.reading_order,
            "uncertainties": analysis.uncertainties,
            "note_path": str(note_path),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        console.print(str(note_path))


@app.command()
def chat(
    repo: Path = typer.Option(Path.cwd(), "--repo", help="Repository root directory."),
    max_steps: int | None = typer.Option(None, "--max-steps", help="Maximum agent steps (1-30)."),
    read_max_lines: int | None = typer.Option(None, "--read-max-lines", help="Maximum lines per read_file call."),
    model: str | None = typer.Option(None, "--model", help="Model name override."),
    base_url: str | None = typer.Option(None, "--base-url", help="API base URL override."),
    session_ref: str | None = typer.Option(None, "--session", help="Existing session id or 'latest' to resume."),
    explain_tools: bool = typer.Option(False, "--explain-tools", help="Show tool progress during execution."),
) -> None:
    """Start an interactive source-reading chat session."""
    if not repo.exists() or not repo.is_dir():
        raise typer.BadParameter(f"Repository path does not exist or is not a directory: {repo}")

    runtime, adapter = _build_runtime_and_adapter(repo, model, base_url, max_steps, read_max_lines)
    loop = AgentLoop(runtime=runtime, adapter=adapter, progress_callback=_build_progress_callback(explain_tools))
    store = SessionStore(repo)

    if session_ref:
        session = store.load_latest() if session_ref == "latest" else store.load(session_ref)
        if session is None:
            console.print(f"No saved session found for '{session_ref}'.")
            raise typer.Exit(code=2)
    else:
        session = AnalysisSession.new(repo)

    console.print(f"Session: {session.session_id}")
    console.print("Type 'exit' or 'quit' to end the chat.")

    while True:
        user_message = typer.prompt("chat").strip()
        if not user_message:
            continue
        if user_message.lower() in {"exit", "quit"}:
            break
        answer = loop.run_turn(session, user_message)
        store.save(session)
        console.print(answer)
