from agentcli.analysis.result_parser import parse_analysis_result


def test_parse_analysis_result_extracts_sections() -> None:
    answer = """## Conclusion
This project is a Typer-based CLI.

## Key Files
- `src/agentcli/cli.py` - CLI entrypoint
- `src/agentcli/agent_loop.py`

## Reading Order
1. `pyproject.toml`
2. `src/agentcli/cli.py`
3. `src/agentcli/agent_loop.py`

## Uncertainties
- Runtime adapter behavior may differ by provider.
"""

    result = parse_analysis_result(answer)

    assert result.conclusion == "This project is a Typer-based CLI."
    assert result.key_files == [
        "src/agentcli/cli.py",
        "src/agentcli/agent_loop.py",
    ]
    assert result.reading_order == [
        "pyproject.toml",
        "src/agentcli/cli.py",
        "src/agentcli/agent_loop.py",
    ]
    assert result.uncertainties == [
        "Runtime adapter behavior may differ by provider.",
    ]


def test_parse_analysis_result_falls_back_to_raw_answer() -> None:
    answer = "Plain answer without explicit sections."

    result = parse_analysis_result(answer)

    assert result.conclusion == answer
    assert result.key_files == []
    assert result.reading_order == []
    assert result.uncertainties == []
