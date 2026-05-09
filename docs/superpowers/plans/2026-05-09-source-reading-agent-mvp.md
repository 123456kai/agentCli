# 源码阅读助手 MVP 实现计划

> **给执行型 Agent 的要求：** 实施本计划时，必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，并按任务逐项推进。步骤使用复选框 `- [ ]` 语法跟踪。

**目标：** 构建一个 Python CLI，能够围绕本地代码仓库回答“源码阅读类问题”，通过搜索仓库、读取相关文件并生成结构化 Markdown 笔记来帮助用户理解项目。

**架构：** 项目使用一个轻量 Runtime 容器来装配仓库上下文、工具注册表和系统提示词。一个可控的 Agent 主循环负责向 LLM 请求“最终回答”或“工具调用”，执行本地文件类工具后回填结果，并持续循环直到答案完成。

**技术栈：** Python 3.12、Typer、Pydantic、Rich、Pytest

---

## 文件结构

- 新建：`pyproject.toml`
- 新建：`README.md`
- 新建：`src/agentcli/__init__.py`
- 新建：`src/agentcli/cli.py`
- 新建：`src/agentcli/models.py`
- 新建：`src/agentcli/runtime.py`
- 新建：`src/agentcli/agent_loop.py`
- 新建：`src/agentcli/prompts/__init__.py`
- 新建：`src/agentcli/prompts/system_prompt.txt`
- 新建：`src/agentcli/llm/__init__.py`
- 新建：`src/agentcli/llm/adapter.py`
- 新建：`src/agentcli/tools/__init__.py`
- 新建：`src/agentcli/tools/base.py`
- 新建：`src/agentcli/tools/search_files.py`
- 新建：`src/agentcli/tools/grep_text.py`
- 新建：`src/agentcli/tools/read_file.py`
- 新建：`src/agentcli/tools/save_note.py`
- 新建：`src/agentcli/notes/__init__.py`
- 新建：`src/agentcli/notes/formatter.py`
- 新建：`tests/test_cli.py`
- 新建：`tests/test_runtime.py`
- 新建：`tests/test_agent_loop.py`
- 新建：`tests/tools/test_search_files.py`
- 新建：`tests/tools/test_grep_text.py`
- 新建：`tests/tools/test_read_file.py`
- 新建：`tests/tools/test_save_note.py`

## 任务 1：搭建项目骨架

**文件：**
- 新建：`pyproject.toml`
- 新建：`README.md`
- 新建：`src/agentcli/__init__.py`
- 新建：`tests/test_cli.py`

- [ ] **步骤 1：先写一个失败的 CLI 冒烟测试**

```python
from typer.testing import CliRunner

from agentcli.cli import app


def test_help_shows_primary_commands() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "ask" in result.stdout
    assert "note" in result.stdout
```

- [ ] **步骤 2：运行测试，确认它先失败**

运行：`pytest tests/test_cli.py::test_help_shows_primary_commands -v`
预期：FAIL，并出现 `ModuleNotFoundError: No module named 'agentcli'`

- [ ] **步骤 3：创建最小可运行的包结构和 CLI 入口**

`pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "agentcli"
version = "0.1.0"
description = "A source-reading agent CLI for understanding unfamiliar repositories."
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
  "typer>=0.12,<1.0",
  "pydantic>=2.7,<3.0",
  "rich>=13.7,<14.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2,<9.0",
]

[project.scripts]
agentcli = "agentcli.cli:app"

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[tool.setuptools.packages.find]
where = ["src"]
```

`src/agentcli/__init__.py`

```python
__all__ = ["__version__"]

__version__ = "0.1.0"
```

`src/agentcli/cli.py`

```python
import typer

app = typer.Typer(help="Source-reading agent CLI.")


@app.command()
def ask(question: str) -> None:
    raise NotImplementedError("ask command not implemented yet")


@app.command()
def note(question: str) -> None:
    raise NotImplementedError("note command not implemented yet")
```

`README.md`

```md
# agentCli

Source-reading agent CLI for repository understanding and note generation.
```

- [ ] **步骤 4：再次运行冒烟测试**

运行：`pytest tests/test_cli.py::test_help_shows_primary_commands -v`
预期：PASS

- [ ] **步骤 5：初始化 git 仓库，为后续任务提交做准备**

运行：`git init`
预期：输出中包含 `Initialized empty Git repository`

- [ ] **步骤 6：提交项目骨架**

```bash
git add pyproject.toml README.md src/agentcli/__init__.py src/agentcli/cli.py tests/test_cli.py
git commit -m "chore: bootstrap source reading agent cli"
```

## 任务 2：加入核心模型与 Runtime 装配

**文件：**
- 新建：`src/agentcli/models.py`
- 新建：`src/agentcli/runtime.py`
- 新建：`src/agentcli/prompts/__init__.py`
- 新建：`src/agentcli/prompts/system_prompt.txt`
- 新建：`tests/test_runtime.py`

- [ ] **步骤 1：先写一个失败的 Runtime 测试**

```python
from pathlib import Path

from agentcli.runtime import build_runtime


def test_build_runtime_loads_repo_and_prompt(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# demo\n", encoding="utf-8")
    runtime = build_runtime(tmp_path)
    assert runtime.repo_root == tmp_path
    assert "read code" in runtime.system_prompt.lower()
    assert set(runtime.tools) == {"search_files", "grep_text", "read_file", "save_note"}
```

- [ ] **步骤 2：运行测试，确认它先失败**

运行：`pytest tests/test_runtime.py::test_build_runtime_loads_repo_and_prompt -v`
预期：FAIL，并报 `build_runtime` 导入失败

- [ ] **步骤 3：实现 Runtime 数据模型**

`src/agentcli/models.py`

```python
from pathlib import Path

from pydantic import BaseModel, Field


class ToolSpec(BaseModel):
    name: str
    description: str


class RuntimeConfig(BaseModel):
    repo_root: Path
    max_steps: int = Field(default=6, ge=1, le=20)
    read_max_lines: int = Field(default=160, ge=20, le=400)


class RuntimeState(BaseModel):
    repo_root: Path
    system_prompt: str
    tools: dict[str, ToolSpec]
```

`src/agentcli/prompts/__init__.py`

```python
from importlib.resources import files


def load_system_prompt() -> str:
    return files("agentcli.prompts").joinpath("system_prompt.txt").read_text(encoding="utf-8")
```

`src/agentcli/prompts/system_prompt.txt`

```text
You are a source-reading assistant.
Your job is to help the user understand an unfamiliar repository.
Always cite concrete file paths, explain why they matter, and recommend a reading order.
Prefer using tools before making assumptions.
```

`src/agentcli/runtime.py`

```python
from pathlib import Path

from agentcli.models import RuntimeConfig, RuntimeState, ToolSpec
from agentcli.prompts import load_system_prompt


def build_runtime(repo_root: Path) -> RuntimeState:
    resolved = repo_root.resolve()
    config = RuntimeConfig(repo_root=resolved)
    tools = {
        "search_files": ToolSpec(name="search_files", description="Search files by glob-like pattern."),
        "grep_text": ToolSpec(name="grep_text", description="Search for text in repository files."),
        "read_file": ToolSpec(name="read_file", description="Read a file snippet with line numbers."),
        "save_note": ToolSpec(name="save_note", description="Save the final answer as a Markdown note."),
    }
    return RuntimeState(repo_root=config.repo_root, system_prompt=load_system_prompt(), tools=tools)
```

- [ ] **步骤 4：再次运行 Runtime 测试**

运行：`pytest tests/test_runtime.py::test_build_runtime_loads_repo_and_prompt -v`
预期：PASS

- [ ] **步骤 5：提交 Runtime 装配部分**

```bash
git add src/agentcli/models.py src/agentcli/runtime.py src/agentcli/prompts/__init__.py src/agentcli/prompts/system_prompt.txt tests/test_runtime.py
git commit -m "feat: add runtime assembly and system prompt loading"
```

## 任务 3：构建本地工具协议与文件工具

**文件：**
- 新建：`src/agentcli/tools/base.py`
- 新建：`src/agentcli/tools/search_files.py`
- 新建：`src/agentcli/tools/grep_text.py`
- 新建：`src/agentcli/tools/read_file.py`
- 新建：`src/agentcli/tools/save_note.py`
- 新建：`src/agentcli/tools/__init__.py`
- 新建：`tests/tools/test_search_files.py`
- 新建：`tests/tools/test_grep_text.py`
- 新建：`tests/tools/test_read_file.py`
- 新建：`tests/tools/test_save_note.py`

- [ ] **步骤 1：先写失败的工具测试**

```python
from pathlib import Path

from agentcli.tools.search_files import search_files


def test_search_files_returns_matching_paths(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    results = search_files(tmp_path, "main.py")
    assert results == ["src/main.py"]
```

```python
from pathlib import Path

from agentcli.tools.grep_text import grep_text


def test_grep_text_returns_line_matches(tmp_path: Path) -> None:
    target = tmp_path / "auth.py"
    target.write_text("def login():\n    return True\n", encoding="utf-8")
    results = grep_text(tmp_path, "login")
    assert results == [{"path": "auth.py", "line": 1, "text": "def login():"}]
```

```python
from pathlib import Path

from agentcli.tools.read_file import read_file


def test_read_file_includes_line_numbers(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text("one\ntwo\nthree\n", encoding="utf-8")
    content = read_file(target, start=2, end=3)
    assert "2: two" in content
    assert "3: three" in content
```

```python
from pathlib import Path

from agentcli.tools.save_note import save_note


def test_save_note_writes_markdown(tmp_path: Path) -> None:
    output = save_note(tmp_path, "repo-map", "# Repo Map\n")
    assert output.name == "repo-map.md"
    assert output.read_text(encoding="utf-8") == "# Repo Map\n"
```

- [ ] **步骤 2：运行工具测试，确认它们先失败**

运行：`pytest tests/tools -v`
预期：FAIL，并因缺少工具模块而导入失败

- [ ] **步骤 3：实现工具协议与文件类工具**

`src/agentcli/tools/base.py`

```python
from dataclasses import dataclass


@dataclass(slots=True)
class ToolResult:
    name: str
    payload: object
```

`src/agentcli/tools/search_files.py`

```python
from pathlib import Path


def search_files(repo_root: Path, pattern: str) -> list[str]:
    matches: list[str] = []
    for path in repo_root.rglob("*"):
        if path.is_file() and pattern.lower() in path.name.lower():
            matches.append(path.relative_to(repo_root).as_posix())
    return sorted(matches)[:20]
```

`src/agentcli/tools/grep_text.py`

```python
from pathlib import Path


def grep_text(repo_root: Path, needle: str) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for index, line in enumerate(lines, start=1):
            if needle.lower() in line.lower():
                results.append(
                    {
                        "path": path.relative_to(repo_root).as_posix(),
                        "line": index,
                        "text": line.strip(),
                    }
                )
                if len(results) >= 30:
                    return results
    return results
```

`src/agentcli/tools/read_file.py`

```python
from pathlib import Path


def read_file(path: Path, start: int = 1, end: int = 80) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    start_index = max(start, 1)
    end_index = max(end, start_index)
    excerpt = []
    for line_no in range(start_index, min(end_index, len(lines)) + 1):
        excerpt.append(f"{line_no}: {lines[line_no - 1]}")
    return "\n".join(excerpt)
```

`src/agentcli/tools/save_note.py`

```python
from pathlib import Path
import re


def save_note(output_dir: Path, slug: str, content: str) -> Path:
    clean_slug = re.sub(r"[^a-z0-9-]+", "-", slug.lower()).strip("-") or "note"
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{clean_slug}.md"
    destination.write_text(content, encoding="utf-8")
    return destination
```

`src/agentcli/tools/__init__.py`

```python
from agentcli.tools.grep_text import grep_text
from agentcli.tools.read_file import read_file
from agentcli.tools.save_note import save_note
from agentcli.tools.search_files import search_files

__all__ = ["grep_text", "read_file", "save_note", "search_files"]
```

- [ ] **步骤 4：再次运行工具测试**

运行：`pytest tests/tools -v`
预期：PASS

- [ ] **步骤 5：提交文件工具层**

```bash
git add src/agentcli/tools tests/tools
git commit -m "feat: add local repository reading tools"
```

## 任务 4：实现最小 LLM 适配层与 Agent 主循环

**文件：**
- 新建：`src/agentcli/llm/__init__.py`
- 新建：`src/agentcli/llm/adapter.py`
- 新建：`src/agentcli/agent_loop.py`
- 新建：`tests/test_agent_loop.py`

- [ ] **步骤 1：先写失败的主循环测试**

```python
from pathlib import Path

from agentcli.agent_loop import AgentLoop
from agentcli.runtime import build_runtime


class FakeAdapter:
    def __init__(self) -> None:
        self.calls = 0

    def respond(self, messages, tools):
        self.calls += 1
        if self.calls == 1:
            return {
                "type": "tool_call",
                "tool_name": "search_files",
                "arguments": {"pattern": "main.py"},
            }
        return {
            "type": "final",
            "content": "Conclusion\n- main entry is src/main.py",
        }


def test_agent_loop_executes_tool_then_returns_answer(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    runtime = build_runtime(tmp_path)
    loop = AgentLoop(runtime=runtime, adapter=FakeAdapter())
    answer = loop.run("Where is the entry point?")
    assert "src/main.py" in answer
```

- [ ] **步骤 2：运行主循环测试，确认它先失败**

运行：`pytest tests/test_agent_loop.py::test_agent_loop_executes_tool_then_returns_answer -v`
预期：FAIL，并因缺少 `AgentLoop` 导入失败

- [ ] **步骤 3：实现适配器协议和主循环**

`src/agentcli/llm/__init__.py`

```python
from agentcli.llm.adapter import LLMAdapter

__all__ = ["LLMAdapter"]
```

`src/agentcli/llm/adapter.py`

```python
from typing import Protocol


class LLMAdapter(Protocol):
    def respond(self, messages: list[dict[str, str]], tools: list[dict[str, str]]) -> dict[str, object]:
        ...
```

`src/agentcli/agent_loop.py`

```python
from agentcli.tools import grep_text, read_file, save_note, search_files


class AgentLoop:
    def __init__(self, runtime, adapter) -> None:
        self.runtime = runtime
        self.adapter = adapter

    def _tool_defs(self) -> list[dict[str, str]]:
        return [{"name": spec.name, "description": spec.description} for spec in self.runtime.tools.values()]

    def _execute_tool(self, tool_name: str, arguments: dict[str, object]) -> object:
        if tool_name == "search_files":
            return search_files(self.runtime.repo_root, str(arguments["pattern"]))
        if tool_name == "grep_text":
            return grep_text(self.runtime.repo_root, str(arguments["needle"]))
        if tool_name == "read_file":
            path = self.runtime.repo_root / str(arguments["path"])
            start = int(arguments.get("start", 1))
            end = int(arguments.get("end", 80))
            return read_file(path, start=start, end=end)
        if tool_name == "save_note":
            output_dir = self.runtime.repo_root / "notes"
            return str(save_note(output_dir, str(arguments["slug"]), str(arguments["content"])))
        raise ValueError(f"Unknown tool: {tool_name}")

    def run(self, question: str) -> str:
        messages = [
            {"role": "system", "content": self.runtime.system_prompt},
            {"role": "user", "content": question},
        ]
        for _ in range(6):
            response = self.adapter.respond(messages, self._tool_defs())
            if response["type"] == "final":
                return str(response["content"])
            if response["type"] != "tool_call":
                raise ValueError(f"Unsupported response type: {response['type']}")
            result = self._execute_tool(str(response["tool_name"]), dict(response["arguments"]))
            messages.append(
                {
                    "role": "tool",
                    "content": f"{response['tool_name']} => {result}",
                }
            )
        raise RuntimeError("Agent loop exceeded maximum step count")
```

- [ ] **步骤 4：再次运行主循环测试**

运行：`pytest tests/test_agent_loop.py::test_agent_loop_executes_tool_then_returns_answer -v`
预期：PASS

- [ ] **步骤 5：提交主循环**

```bash
git add src/agentcli/llm src/agentcli/agent_loop.py tests/test_agent_loop.py
git commit -m "feat: add minimal agent loop and llm adapter contract"
```

## 任务 5：接通 CLI 命令与笔记格式化

**文件：**
- 修改：`src/agentcli/cli.py`
- 新建：`src/agentcli/notes/__init__.py`
- 新建：`src/agentcli/notes/formatter.py`
- 修改：`tests/test_cli.py`

- [ ] **步骤 1：补充失败中的 CLI 行为测试**

```python
from pathlib import Path

from typer.testing import CliRunner

from agentcli.cli import app


def test_ask_requires_question() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["ask"])
    assert result.exit_code != 0


def test_note_saves_markdown_with_repo_option(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    class FakeLoop:
        def __init__(self, runtime, adapter) -> None:
            self.runtime = runtime

        def run(self, question: str) -> str:
            return "## Conclusion\nEntry point is src/main.py"

    monkeypatch.setattr("agentcli.cli.AgentLoop", FakeLoop)
    monkeypatch.setattr("agentcli.cli.build_adapter", lambda: object())

    runner = CliRunner()
    result = runner.invoke(app, ["note", "--repo", str(repo), "Find entrypoint"])
    assert result.exit_code == 0
    assert "notes/find-entrypoint.md" in result.stdout
```

- [ ] **步骤 2：运行 CLI 测试，确认它先失败**

运行：`pytest tests/test_cli.py -v`
预期：FAIL，因为 CLI 命令仍然抛出 `NotImplementedError`

- [ ] **步骤 3：实现笔记格式化并接线命令**

`src/agentcli/notes/__init__.py`

```python
from agentcli.notes.formatter import make_note_slug, render_note

__all__ = ["make_note_slug", "render_note"]
```

`src/agentcli/notes/formatter.py`

```python
import re


def make_note_slug(question: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", question.lower()).strip("-")
    return slug or "source-note"


def render_note(question: str, answer: str) -> str:
    return f"# {question}\n\n{answer}\n"
```

`src/agentcli/cli.py`

```python
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
```

- [ ] **步骤 4：再次运行 CLI 测试**

运行：`pytest tests/test_cli.py -v`
预期：PASS

- [ ] **步骤 5：提交 CLI 接线部分**

```bash
git add src/agentcli/cli.py src/agentcli/notes tests/test_cli.py
git commit -m "feat: connect cli commands to runtime and note output"
```

## 任务 6：加入本地演示用的确定性适配器，并完成端到端验证

**文件：**
- 修改：`src/agentcli/llm/adapter.py`
- 修改：`src/agentcli/cli.py`
- 修改：`README.md`
- 修改：`tests/test_agent_loop.py`

- [ ] **步骤 1：先写失败的本地演示测试**

```python
from pathlib import Path

from agentcli.agent_loop import AgentLoop
from agentcli.llm.adapter import DemoAdapter
from agentcli.runtime import build_runtime


def test_demo_adapter_returns_final_answer_after_tool_result(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def main():\n    pass\n", encoding="utf-8")
    runtime = build_runtime(tmp_path)
    loop = AgentLoop(runtime=runtime, adapter=DemoAdapter())
    answer = loop.run("Where is the entry point?")
    assert "Conclusion" in answer
```

- [ ] **步骤 2：运行定向测试，确认它先失败**

运行：`pytest tests/test_agent_loop.py::test_demo_adapter_returns_final_answer_after_tool_result -v`
预期：FAIL，并因缺少 `DemoAdapter` 导入失败

- [ ] **步骤 3：实现一个确定性的 Demo 适配器**

`src/agentcli/llm/adapter.py`

```python
from typing import Protocol


class LLMAdapter(Protocol):
    def respond(self, messages: list[dict[str, str]], tools: list[dict[str, str]]) -> dict[str, object]:
        ...


class DemoAdapter:
    def respond(self, messages: list[dict[str, str]], tools: list[dict[str, str]]) -> dict[str, object]:
        last_message = messages[-1]["content"]
        if "search_files =>" not in last_message:
            return {
                "type": "tool_call",
                "tool_name": "search_files",
                "arguments": {"pattern": "main.py"},
            }
        return {
            "type": "final",
            "content": "## Conclusion\nLikely entry point: src/main.py\n\n## Reading Path\n1. Read src/main.py\n2. Follow imports from the entry module",
        }
```

`src/agentcli/cli.py`

```python
from agentcli.llm.adapter import DemoAdapter


def build_adapter():
    return DemoAdapter()
```

`README.md`

```md
# agentCli

Source-reading agent CLI for repository understanding and note generation.

## Local demo

```bash
pip install -e ".[dev]"
agentcli ask --repo /path/to/repo "Where is the entry point?"
agentcli note --repo /path/to/repo "Explain the auth flow"
```
```

- [ ] **步骤 4：运行定向测试和完整测试集**

运行：`pytest tests/test_agent_loop.py::test_demo_adapter_returns_final_answer_after_tool_result -v`
预期：PASS

运行：`pytest -v`
预期：PASS

- [ ] **步骤 5：提交 Demo 流程**

```bash
git add src/agentcli/llm/adapter.py src/agentcli/cli.py README.md tests/test_agent_loop.py
git commit -m "feat: add deterministic demo adapter for end-to-end cli flow"
```

## 验证清单

- [ ] 运行：`pytest -v`
预期：所有测试通过

- [ ] 运行：`python -m agentcli.cli --help`
预期：帮助信息中列出 `ask` 和 `note`

- [ ] 运行：`agentcli ask --repo . "Where is the entry point?"`
预期：终端打印带有结论和阅读路径的结构化回答

- [ ] 运行：`agentcli note --repo . "Explain the project layout"`
预期：在 `notes/` 目录下生成 Markdown 文件

## 自检说明

- 规格覆盖：已覆盖 CLI 入口、Runtime 装配、本地工具、Agent 主循环、笔记保存和 Demo 验证。
- 占位检查：没有残留 `TBD`、`TODO` 或“后续补测试”这类空泛描述。
- 类型一致性：工具名在 Runtime、主循环、测试和 CLI 接线中保持一致。
