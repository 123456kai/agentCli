from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from collections import deque
from pathlib import Path
from typing import Any

from agentcli.analysis.cache import NarrativeCache, make_cache_key
from agentcli.analysis.graph import build_graph_index, GraphIndex


@dataclass
class NodeNarrative:
    summary: str
    design_notes: str
    warnings: str | None


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


def _resolve_line_end(file_path: Path, line_start: int) -> int:
    """Find the actual end line of a function/class definition.

    Scans forward from line_start to find the next top-level definition
    (no leading whitespace def/class/async def) or end of file.
    Falls back to line_start if the file cannot be read.
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return line_start

    lines = content.splitlines()
    if line_start > len(lines):
        return line_start

    # Scan from line_start to find the next top-level definition.
    # line_start is 1-based, so lines[line_start] is the first line after the
    # definition line (e.g. line_start=3 starts scanning at lines[3] = line 4).
    for i in range(line_start, len(lines)):
        stripped = lines[i].lstrip()
        if stripped.startswith(("def ", "class ", "async def ")):
            # i is the 0-based index of the next definition line.  Returning i
            # gives the 1-based line number of the line just before that next
            # definition (lines[i-1] has 1-based line number i), so line_end
            # does not bleed into the next function.
            return i

    # EOF: len(lines) equals the 1-based line number of the last line.
    return len(lines)


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
            node.line_end = _resolve_line_end(
                repo_root / node.file_path, node.line_start
            )
    return storyline.nodes


_NARRATIVE_PROMPT = """你是一位资深代码审查专家。分析以下 Python 代码段，用中文回答。

## 代码
```
{code_snippet}
```

## 要求
返回一个 JSON 对象（不要 markdown，不要额外文字）：
{{
  "summary": "这段代码做什么（1-2句话，中文）",
  "design_notes": "为什么这样设计？使用了什么模式？有哪些值得注意的决策？（2-3句话，中文）",
  "warnings": "潜在问题或注意事项，没有则为 null"
}}
"""


def _file_content_hash(file_path: Path) -> str:
    """Return a short SHA256 hash of file content for cache invalidation."""
    try:
        return hashlib.sha256(file_path.read_bytes()).hexdigest()[:16]
    except OSError:
        return "unknown"


def _read_node_source(repo_root: Path, node: dict[str, object]) -> str:
    """Read source code around a graph node's line (up to 50 lines)."""
    file_path = repo_root / str(node["path"])
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
        start = max(0, int(node["line"]) - 1)
        end = min(len(lines), start + 50)
        return "\n".join(lines[start:end])
    except (OSError, UnicodeDecodeError):
        return ""


async def generate_node_narrative(
    repo_root: Path,
    node_id: str,
    index: GraphIndex,
    cache: NarrativeCache | None = None,
    adapter_factory: Any = None,
) -> NodeNarrative:
    """Generate AI explanation for a single graph node. Uses cache if available."""
    nodes_by_id = index["nodes_by_id"]
    node = nodes_by_id.get(node_id)
    if not node:
        return NodeNarrative(summary="(节点不存在)", design_notes="", warnings=None)

    file_path = repo_root / str(node["path"])
    content_hash = _file_content_hash(file_path) if file_path.exists() else "external"

    line_start = int(node["line"])
    line_end = int(node["line"])
    cache_key = make_cache_key(str(node["path"]), content_hash, line_start, line_end)

    if cache is not None:
        cached = cache.get(cache_key)
        if cached is not None:
            return NodeNarrative(
                summary=str(cached.get("summary", "")),
                design_notes=str(cached.get("design_notes", "")),
                warnings=cached.get("warnings") if cached.get("warnings") else None,
            )

    code_snippet = _read_node_source(repo_root, node)
    prompt = _NARRATIVE_PROMPT.format(code_snippet=code_snippet)

    if adapter_factory is None:
        return _fallback_narrative(node)

    try:
        adapter = adapter_factory()
        raw = adapter.chat_sync(prompt)
        data = json.loads(raw.strip())
    except Exception:
        return _fallback_narrative(node)

    narrative = NodeNarrative(
        summary=str(data.get("summary", "")),
        design_notes=str(data.get("design_notes", "")),
        warnings=data.get("warnings") if data.get("warnings") else None,
    )

    if cache is not None:
        cache.set(cache_key, {
            "summary": narrative.summary,
            "design_notes": narrative.design_notes,
            "warnings": narrative.warnings,
        })

    return narrative


def _fallback_narrative(node: dict[str, object]) -> NodeNarrative:
    label = str(node["label"])
    kind = str(node["kind"])
    return NodeNarrative(
        summary=f"{label}（{kind}）",
        design_notes="AI 解释暂不可用，请稍后重试。",
        warnings=None,
    )
