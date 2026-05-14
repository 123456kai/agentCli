from __future__ import annotations

import ast
from collections import deque
from pathlib import Path
from typing import Any

from agentcli.repo_guard import enumerate_repo_files

GraphIndex = dict[str, Any]


class _GraphVisitor(ast.NodeVisitor):
    def __init__(self, rel_path: str) -> None:
        self.rel_path = rel_path
        self.nodes: dict[str, dict[str, object]] = {}
        self.raw_calls: dict[str, list[str]] = {}
        self._class_stack: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._class_stack.append(node.name)
        class_label = ".".join(self._class_stack)
        self._add_node(class_label, node.lineno, "class")
        for child in node.body:
            self.visit(child)
        self._class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        label = ".".join([*self._class_stack, node.name]) if self._class_stack else node.name
        kind = "method" if self._class_stack else "function"
        self._add_node(label, node.lineno, kind)
        self.raw_calls[label] = self._collect_calls(node)

    def _add_node(self, label: str, line: int, kind: str) -> None:
        node_id = make_node_id(self.rel_path, label)
        self.nodes[node_id] = {
            "id": node_id,
            "label": label,
            "path": self.rel_path,
            "line": line,
            "kind": kind,
            "degree": 0,
        }

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
            if isinstance(func.value, ast.Name) and func.value.id in {"self", "cls"}:
                return func.attr
            return func.attr
        return None


def make_node_id(path: str, label: str) -> str:
    return f"{path}::{label}"


def build_graph_index(repo_root: Path) -> GraphIndex:
    py_files = [rel_path for rel_path in enumerate_repo_files(repo_root) if rel_path.endswith(".py")]
    nodes_by_id: dict[str, dict[str, object]] = {}
    raw_calls_by_id: dict[str, list[str]] = {}
    label_to_ids: dict[str, list[str]] = {}
    skipped_files: list[str] = []

    for rel_path in py_files:
        path = repo_root / rel_path
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            skipped_files.append(rel_path)
            continue

        visitor = _GraphVisitor(rel_path)
        visitor.visit(tree)
        nodes_by_id.update(visitor.nodes)
        for node_id, node in visitor.nodes.items():
            label = str(node["label"])
            label_to_ids.setdefault(label, []).append(node_id)
        for label, calls in visitor.raw_calls.items():
            raw_calls_by_id[make_node_id(rel_path, label)] = calls

    edges = _resolve_edges(nodes_by_id, raw_calls_by_id, label_to_ids)
    for node in nodes_by_id.values():
        node_id = str(node["id"])
        node["degree"] = sum(1 for edge in edges if edge["source"] == node_id or edge["target"] == node_id)

    return {
        "nodes_by_id": nodes_by_id,
        "edges": edges,
        "skipped_files": skipped_files,
        "warning": "no_python_files" if not py_files else None,
    }


def _resolve_edges(
    nodes_by_id: dict[str, dict[str, object]],
    raw_calls_by_id: dict[str, list[str]],
    label_to_ids: dict[str, list[str]],
) -> list[dict[str, object]]:
    edges: list[dict[str, object]] = []
    seen_edges: set[str] = set()

    for source_id, calls in raw_calls_by_id.items():
        source_path = source_id.split("::", 1)[0]
        source_label = str(nodes_by_id[source_id]["label"])
        source_class = source_label.rsplit(".", 1)[0] if "." in source_label else None
        for call in calls:
            target_id = _resolve_call_target(call, source_path, source_class, label_to_ids)
            if not target_id:
                target_id = f"external::{call}"
                nodes_by_id.setdefault(
                    target_id,
                    {
                        "id": target_id,
                        "label": call,
                        "path": "",
                        "line": 0,
                        "kind": "external",
                        "degree": 0,
                    },
                )
            edge_id = f"{source_id}->{target_id}"
            if edge_id in seen_edges:
                continue
            seen_edges.add(edge_id)
            edges.append(
                {
                    "id": edge_id,
                    "source": source_id,
                    "target": target_id,
                    "relation": "calls",
                    "is_cycle": target_id == source_id,
                }
            )
    return edges


def _resolve_call_target(
    call: str,
    source_path: str,
    source_class: str | None,
    label_to_ids: dict[str, list[str]],
) -> str | None:
    candidates: list[str] = []
    if source_class and "." not in call:
        candidates.append(f"{source_class}.{call}")
    candidates.append(call)

    for label in candidates:
        ids = label_to_ids.get(label, [])
        same_file = [node_id for node_id in ids if node_id.startswith(f"{source_path}::")]
        if len(same_file) == 1:
            return same_file[0]
        if len(ids) == 1:
            return ids[0]
    return None


def build_skeleton_graph(repo_root: Path) -> dict[str, object]:
    index = build_graph_index(repo_root)
    return {
        "nodes": list(index["nodes_by_id"].values()),
        "edges": index["edges"],
        "warning": index["warning"],
        "skipped_files": index["skipped_files"],
    }


def expand_call_node(repo_root: Path, node_id: str, depth: int = 3) -> dict[str, object]:
    depth = max(1, min(depth, 5))
    index = build_graph_index(repo_root)
    nodes_by_id: dict[str, dict[str, object]] = index["nodes_by_id"]
    if node_id not in nodes_by_id or str(nodes_by_id[node_id]["kind"]) == "external":
        return {"root": node_id, "nodes": [], "edges": []}

    outgoing: dict[str, list[dict[str, object]]] = {}
    for edge in index["edges"]:
        outgoing.setdefault(str(edge["source"]), []).append(edge)

    included_nodes: set[str] = {node_id}
    included_edges: list[dict[str, object]] = []
    included_edge_ids: set[str] = set()
    queued: set[str] = {node_id}
    queue: deque[tuple[str, int]] = deque([(node_id, 0)])

    while queue:
        current, current_depth = queue.popleft()
        if current_depth >= depth:
            continue
        for edge in outgoing.get(current, []):
            edge_id = str(edge["id"])
            target = str(edge["target"])
            if edge_id not in included_edge_ids:
                included_edges.append(edge)
                included_edge_ids.add(edge_id)
            included_nodes.add(target)
            if target in nodes_by_id and str(nodes_by_id[target]["kind"]) != "external" and target not in queued:
                queued.add(target)
                queue.append((target, current_depth + 1))

    return {
        "root": node_id,
        "nodes": [nodes_by_id[node] for node in sorted(included_nodes)],
        "edges": included_edges,
    }


def get_node_detail(repo_root: Path, node_id: str) -> dict[str, object]:
    index = build_graph_index(repo_root)
    nodes_by_id: dict[str, dict[str, object]] = index["nodes_by_id"]
    node = nodes_by_id.get(node_id)
    if not node:
        return {"node": None, "incoming": [], "outgoing": []}

    incoming = [edge for edge in index["edges"] if edge["target"] == node_id]
    outgoing = [edge for edge in index["edges"] if edge["source"] == node_id]
    return {"node": node, "incoming": incoming, "outgoing": outgoing}
