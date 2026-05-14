from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from collections import deque
from pathlib import Path
from typing import Any

from agentcli.analysis.graph import build_graph_index, GraphIndex


@dataclass
class StorylineNode:
    order: int
    title: str
    file_path: str
    line_start: int
    line_end: int
    graph_node_id: str
    summary: str | None = None
    design_notes: str | None = None
    warnings: str | None = None


@dataclass
class Storyline:
    id: str
    title: str
    description: str
    nodes: list[StorylineNode] = field(default_factory=list)

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def estimated_minutes(self) -> int:
        return max(1, self.node_count)

    @property
    def file_count(self) -> int:
        return len({n.file_path for n in self.nodes})


def _entry_candidates(index: GraphIndex) -> list[str]:
    """Find entry-point nodes: CLI main, FastAPI routes, __main__ files, and
    cross-module boundary functions called from other files."""
    nodes_by_id = index["nodes_by_id"]
    edges = index["edges"]
    entries: list[str] = []

    # 1. Explicit entry points by name / path pattern
    for node_id, node in nodes_by_id.items():
        label = str(node["label"])
        path = str(node["path"])
        if label in ("main", "cli", "create_app", "app"):
            entries.append(node_id)
        elif "__main__" in path:
            entries.append(node_id)
        elif path.endswith("server.py") and label == "create_app":
            entries.append(node_id)

    # 2. Cross-module boundary: functions called from a *different* file
    callers_by_target: dict[str, set[str]] = {}
    for edge in edges:
        target = str(edge["target"])
        source = str(edge["source"])
        callers_by_target.setdefault(target, set()).add(source)

    for node_id, node in nodes_by_id.items():
        if str(node["kind"]) == "external":
            continue
        if node_id in entries:
            continue
        callers = callers_by_target.get(node_id, set())
        caller_files = {c.split("::", 1)[0] for c in callers}
        node_file = str(node["path"])
        if caller_files - {node_file}:
            entries.append(node_id)

    return entries


def _bfs_path(
    index: GraphIndex,
    start_node_id: str,
    min_nodes: int = 3,
    max_nodes: int = 12,
) -> list[str] | None:
    """BFS from start_node_id to find a meaningful path through the graph."""
    nodes_by_id = index["nodes_by_id"]
    edges = index["edges"]
    outgoing: dict[str, list[str]] = {}
    for edge in edges:
        outgoing.setdefault(str(edge["source"]), []).append(str(edge["target"]))

    visited: set[str] = {start_node_id}
    path: list[str] = [start_node_id]
    queue: deque[str] = deque([start_node_id])

    while queue and len(path) < max_nodes:
        current = queue.popleft()
        neighbors = outgoing.get(current, [])
        internal = [n for n in neighbors if n in nodes_by_id and str(nodes_by_id[n]["kind"]) != "external"]
        if internal:
            nxt = internal[0]
            if nxt not in visited:
                visited.add(nxt)
                path.append(nxt)
                queue.append(nxt)
        elif neighbors:
            for n in neighbors:
                if n not in visited:
                    visited.add(n)
                    path.append(n)
                    queue.append(n)
                    break

    return path if len(path) >= min_nodes else None


def discover_storylines(
    repo_root: Path,
    index: GraphIndex | None = None,
    min_nodes: int = 3,
    max_nodes: int = 12,
) -> list[Storyline]:
    """Auto-discover reading storylines from the call graph."""
    if index is None:
        index = build_graph_index(repo_root)

    nodes_by_id = index["nodes_by_id"]
    entries = _entry_candidates(index)
    storylines: list[Storyline] = []

    for entry_id in entries:
        path = _bfs_path(index, entry_id, min_nodes=min_nodes, max_nodes=max_nodes)
        if path is None:
            continue
        nodes_data = [nodes_by_id[nid] for nid in path if nid in nodes_by_id]
        labels = [str(n["label"]) for n in nodes_data]
        title = " → ".join(labels[:3]) + " 调用链"
        description = " → ".join(labels[:5])
        storyline = Storyline(
            id=hashlib.sha256(entry_id.encode()).hexdigest()[:12],
            title=title,
            description=description,
            nodes=[
                StorylineNode(
                    order=i,
                    title=str(node["label"]),
                    file_path=str(node["path"]),
                    line_start=int(node["line"]),
                    line_end=int(node["line"]),
                    graph_node_id=str(node["id"]),
                )
                for i, node in enumerate(nodes_data)
            ],
        )
        storylines.append(storyline)

    return storylines


def resolve_storyline_nodes(
    repo_root: Path,
    index: GraphIndex,
    storyline: Storyline,
) -> list[StorylineNode]:
    """Fill in line_end for each node by reading the source file."""
    nodes_by_id = index["nodes_by_id"]
    for node in storyline.nodes:
        graph_node = nodes_by_id.get(node.graph_node_id)
        if graph_node:
            node.line_start = int(graph_node["line"])
            node.line_end = int(graph_node["line"])
    return storyline.nodes
