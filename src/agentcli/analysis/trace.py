import ast
from collections import deque
from pathlib import Path

from agentcli.analysis.models import CallChain, CallChainStep
from agentcli.repo_guard import enumerate_repo_files


class _DefinitionVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.definitions: dict[str, int] = {}
        self.calls: dict[str, list[str]] = {}
        self._class_stack: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        symbol = f"{self._class_stack[-1]}.{node.name}" if self._class_stack else node.name
        self.definitions[symbol] = node.lineno
        self.calls[symbol] = self._collect_calls(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.definitions[node.name] = node.lineno
        self._class_stack.append(node.name)
        for child in node.body:
            self.visit(child)
        self._class_stack.pop()

    def _collect_calls(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
        var_types: dict[str, str] = {}
        calls: list[str] = []

        for child in ast.walk(node):
            if isinstance(child, ast.Assign) and isinstance(child.value, ast.Call):
                resolved = self._resolve_call_symbol(child.value.func, var_types)
                if resolved:
                    for target in child.targets:
                        if isinstance(target, ast.Name):
                            var_types[target.id] = resolved.split(".")[0]
            elif isinstance(child, ast.Call):
                resolved = self._resolve_call_symbol(child.func, var_types)
                if resolved and resolved not in calls:
                    calls.append(resolved)
        return calls

    @staticmethod
    def _resolve_call_symbol(func: ast.expr, var_types: dict[str, str]) -> str | None:
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            if isinstance(func.value, ast.Name) and func.value.id in var_types:
                return f"{var_types[func.value.id]}.{func.attr}"
            return func.attr
        return None


def _build_definition_index(repo_root: Path) -> dict[str, tuple[str, int, list[str]]]:
    index: dict[str, tuple[str, int, list[str]]] = {}

    for rel_path in enumerate_repo_files(repo_root):
        if not rel_path.endswith(".py"):
            continue
        path = repo_root / rel_path
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue

        visitor = _DefinitionVisitor()
        visitor.visit(tree)
        for symbol, line in visitor.definitions.items():
            index[symbol] = (rel_path, line, visitor.calls.get(symbol, []))
    return index


def _resolve_start_symbol(index: dict[str, tuple[str, int, list[str]]], symbol: str, path: str | None) -> str | None:
    if path:
        for name, (candidate_path, _, _) in index.items():
            if candidate_path == path and (name == symbol or name.endswith(f".{symbol}")):
                return name
    if symbol in index:
        return symbol
    matches = [name for name in index if name == symbol or name.endswith(f".{symbol}")]
    if len(matches) == 1:
        return matches[0]
    return None


def _resolve_next_symbol(index: dict[str, tuple[str, int, list[str]]], symbol: str) -> str | None:
    if symbol in index:
        return symbol
    matches = [name for name in index if name == symbol or name.endswith(f".{symbol}")]
    if len(matches) == 1:
        return matches[0]
    return None


def trace_python_flow(repo_root: Path, symbol: str, path: str | None = None, max_depth: int = 4) -> dict[str, object]:
    index = _build_definition_index(repo_root)
    start_symbol = _resolve_start_symbol(index, symbol, path)
    if not start_symbol:
        return {"kind": "call_chain", "symbol": symbol, "steps": [], "error": "symbol_not_found"}

    chain = CallChain(symbol=symbol)
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(start_symbol, 0)])

    while queue:
        current_symbol, depth = queue.popleft()
        if current_symbol in visited or depth > max_depth:
            continue
        visited.add(current_symbol)

        rel_path, line, calls = index[current_symbol]
        chain.steps.append(
            CallChainStep(
                symbol=current_symbol,
                path=rel_path,
                line=line,
                confidence="high" if depth == 0 else "medium",
            )
        )

        for called_symbol in calls:
            resolved = _resolve_next_symbol(index, called_symbol)
            if resolved and resolved not in visited:
                queue.append((resolved, depth + 1))

    return {
        "kind": "call_chain",
        "symbol": symbol,
        "steps": [step.model_dump() for step in chain.steps],
    }
