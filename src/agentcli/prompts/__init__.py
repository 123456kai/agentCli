from importlib.resources import files


def load_system_prompt() -> str:
    return files("agentcli.prompts").joinpath("system_prompt.txt").read_text(encoding="utf-8")
