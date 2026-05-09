import typer

app = typer.Typer(help="Source-reading agent CLI.")


@app.command()
def ask(question: str) -> None:
    raise NotImplementedError("ask command not implemented yet")


@app.command()
def note(question: str) -> None:
    raise NotImplementedError("note command not implemented yet")
