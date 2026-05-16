from __future__ import annotations

import hashlib
import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentcli.analysis.cache import NarrativeCache, make_cache_key
from agentcli.analysis.graph import build_graph_index, GraphIndex
from agentcli.prompts.storyline import (
    STAGE1_DOMAIN_ANALYSIS,
    STAGE2_PATH_PLANNING,
    STAGE3_PROGRESSIVE_NARRATIVE,
    FALLBACK_STAGE1_DOMAINS,
)


@dataclass
class NodeNarrative:
    summary: str
    design_notes: str
    warnings: str | None
    next_teaser: str | None = None


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
    next_teaser: str | None = None


@dataclass
class Storyline:
    id: str
    title: str
    description: str
    theme: str = ""
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


# ── Domain analysis ──────────────────────────────────────────────────


def _scan_dir_tree(repo_root: Path) -> dict[str, list[str]]:
    """Scan repo directory structure, return {dir_name: [relative_file_paths]}."""
    groups: dict[str, list[str]] = {}
    src = repo_root / "src"
    scan_root = src if src.is_dir() else repo_root
    for entry in sorted(scan_root.rglob("*.py")):
        if entry.name.startswith("__"):
            continue
        rel = str(entry.relative_to(repo_root)).replace("\\", "/")
        parent = entry.parent.relative_to(scan_root if src.is_dir() else repo_root)
        key = str(parent.parts[0]) if parent.parts else "root"
        # Also add standalone files at top level
        if not parent.parts:
            key = entry.stem
        groups.setdefault(key, []).append(rel)
    return groups


def _fallback_domains(repo_root: Path) -> list[dict[str, object]]:
    """Rule-based domain grouping using predefined mapping."""
    dir_tree = _scan_dir_tree(repo_root)
    domains: list[dict[str, object]] = []
    seen_files: set[str] = set()

    for domain_id, info in FALLBACK_STAGE1_DOMAINS.items():
        files: list[str] = []
        for d in info["dirs"]:  # type: ignore[union-attr]
            if d in dir_tree:
                for f in dir_tree[d]:
                    if f not in seen_files:
                        files.append(f)
                        seen_files.add(f)
            # Also check if d is a file pattern (e.g. "cli.py")
            elif "." in d:
                for group_files in dir_tree.values():
                    for f in group_files:
                        if f.endswith(d) and f not in seen_files:
                            files.append(f)
                            seen_files.add(f)
        if files:
            domains.append({
                "id": domain_id,
                "name": str(info["name"]),
                "description": str(info["description"]),
                "files": files,
            })

    # Catch-all: any uncovered files go to "other"
    other_files: list[str] = []
    for group_files in dir_tree.values():
        for f in group_files:
            if f not in seen_files:
                other_files.append(f)
    if other_files:
        domains.append({
            "id": "other",
            "name": "其他模块",
            "description": "未归组的代码文件",
            "files": other_files,
        })

    return domains


def _analyze_project_domains(
    repo_root: Path,
    adapter: Any = None,
) -> list[dict[str, object]]:
    """Stage 1: scan directory tree, optionally refine with LLM."""
    dir_tree = _scan_dir_tree(repo_root)
    if not dir_tree:
        return []

    if adapter is None:
        return _fallback_domains(repo_root)

    # Build a compact tree representation
    tree_lines = []
    for group, files in sorted(dir_tree.items()):
        tree_lines.append(f"{group}/")
        for f in sorted(files)[:8]:
            tree_lines.append(f"  {f}")
        if len(files) > 8:
            tree_lines.append(f"  ... (+{len(files) - 8} more)")
    dir_tree_str = "\n".join(tree_lines)

    prompt = STAGE1_DOMAIN_ANALYSIS.format(dir_tree=dir_tree_str)
    try:
        raw = adapter.chat_sync(prompt)
        data = json.loads(raw.strip())
        return list(data.get("domains", []))
    except Exception:
        return _fallback_domains(repo_root)


# ── Path planning ────────────────────────────────────────────────────


def _build_entry_summary(index: GraphIndex, max_per_domain: int = 15) -> list[dict[str, object]]:
    """Extract key entry points from the graph, grouped roughly by file path."""
    nodes_by_id = index["nodes_by_id"]
    entries: list[dict[str, object]] = []

    # Priority labels
    priority_labels = {"main", "cli", "create_app", "app", "run_turn", "run"}
    priority_nodes: list[dict[str, object]] = []
    other_nodes: list[dict[str, object]] = []

    for node_id, node in nodes_by_id.items():
        if str(node["kind"]) == "external":
            continue
        label = str(node["label"])
        path = str(node["path"])
        info = {
            "node_id": node_id,
            "label": label,
            "path": path,
            "kind": str(node["kind"]),
        }
        if label in priority_labels or "__main__" in path:
            priority_nodes.append(info)
        else:
            other_nodes.append(info)

    entries.extend(priority_nodes)
    # Add a diverse sample from other nodes
    seen_dirs: set[str] = set()
    for info in other_nodes:
        dir_key = str(info["path"]).split("/")[0] if "/" in str(info["path"]) else str(info["path"])
        if dir_key not in seen_dirs or len([e for e in entries if str(e["path"]).startswith(dir_key)]) < max_per_domain:
            entries.append(info)
            seen_dirs.add(dir_key)
        if len(entries) >= max_per_domain * 6:
            break

    return entries[:60]


def _fallback_paths(
    domains: list[dict[str, object]],
    index: GraphIndex,
) -> list[Storyline]:
    """Fallback: BFS from domain entry points to generate skeleton storylines."""
    nodes_by_id = index["nodes_by_id"]
    edges = index["edges"]
    outgoing: dict[str, list[str]] = {}
    for edge in edges:
        outgoing.setdefault(str(edge["source"]), []).append(str(edge["target"]))

    storylines: list[Storyline] = []

    for domain in domains:
        domain_id = str(domain["id"])
        domain_name = str(domain["name"])
        domain_desc = str(domain["description"])
        domain_files = [str(f) for f in domain.get("files", [])]

        # Find entry nodes in this domain's files
        domain_nodes: list[str] = []
        for node_id, node in nodes_by_id.items():
            if str(node["kind"]) == "external":
                continue
            if str(node["path"]) in domain_files:
                domain_nodes.append(node_id)

        if not domain_nodes:
            continue

        # Sort by out-degree descending so entry points (more outgoing)
        # are tried first, yielding longer, more meaningful paths.
        domain_nodes.sort(key=lambda nid: len(outgoing.get(nid, [])), reverse=True)

        # BFS from the first few nodes to find a path
        for entry_id in domain_nodes[:3]:
            path = _bfs_path(index, entry_id, outgoing, min_nodes=3, max_nodes=10)
            if path is None or len(path) < 3:
                continue

            path_nodes = [nodes_by_id[nid] for nid in path if nid in nodes_by_id]
            if len(path_nodes) < 3:
                continue

            # Build storyline
            storyline = Storyline(
                id=_hash_id(f"{domain_id}:{entry_id}"),
                title=f"{domain_name}代码路径",
                description=f"探索 {domain_name} 模块的关键代码路径：{domain_desc}",
                theme=domain_id,
                nodes=[
                    StorylineNode(
                        order=i,
                        title=f"{str(n['label'])}（{str(n['path'])}）",
                        file_path=str(n["path"]),
                        line_start=int(n["line"]),
                        line_end=int(n["line"]),
                        graph_node_id=str(n["id"]),
                    )
                    for i, n in enumerate(path_nodes)
                ],
            )
            storylines.append(storyline)
            break  # One storyline per domain in fallback mode

    # Deduplicate
    return _deduplicate(storylines)


def _plan_storyline_paths(
    domains: list[dict[str, object]],
    index: GraphIndex,
    adapter: Any = None,
) -> list[Storyline]:
    """Stage 2: plan reading paths, optionally with LLM."""
    if adapter is None:
        return _fallback_paths(domains, index)

    entry_nodes = _build_entry_summary(index)
    domains_json = json.dumps(domains, ensure_ascii=False, indent=2)
    entries_json = json.dumps(entry_nodes, ensure_ascii=False, indent=2)

    prompt = STAGE2_PATH_PLANNING.format(
        domains_json=domains_json,
        entry_nodes=entries_json,
    )
    try:
        raw = adapter.chat_sync(prompt)
        data = json.loads(raw.strip())
        llm_storylines = data.get("storylines", [])
    except Exception:
        return _fallback_paths(domains, index)

    nodes_by_id = index["nodes_by_id"]
    storylines: list[Storyline] = []

    for s in llm_storylines:
        nodes: list[StorylineNode] = []
        for ns in s.get("node_sequence", []):
            gid = str(ns.get("graph_node_id", ""))
            graph_node = nodes_by_id.get(gid, {})
            nodes.append(StorylineNode(
                order=int(ns.get("order", len(nodes))),
                title=str(ns.get("role_title", graph_node.get("label", ""))),
                file_path=str(ns.get("file_path", graph_node.get("path", ""))),
                line_start=int(graph_node.get("line", 0)),
                line_end=int(graph_node.get("line", 0)),
                graph_node_id=gid,
            ))

        if len(nodes) >= 2:
            storylines.append(Storyline(
                id=_hash_id(str(s.get("title", ""))),
                title=str(s.get("title", "")),
                description=str(s.get("description", "")),
                theme=str(s.get("theme", "")),
                nodes=nodes,
            ))

    if not storylines:
        return _fallback_paths(domains, index)
    return _deduplicate(storylines)


def _bfs_path(
    index: GraphIndex,
    start_node_id: str,
    outgoing: dict[str, list[str]],
    min_nodes: int = 3,
    max_nodes: int = 10,
) -> list[str] | None:
    """BFS to find a meaningful path through the graph."""
    nodes_by_id = index["nodes_by_id"]
    path_labels: set[str] = set()
    visited: set[str] = {start_node_id}
    path: list[str] = [start_node_id]
    start_node = nodes_by_id.get(start_node_id, {})
    path_labels.add(str(start_node.get("label", "")))
    queue: deque[str] = deque([start_node_id])

    while queue and len(path) < max_nodes:
        current = queue.popleft()
        neighbors = outgoing.get(current, [])
        internal = [
            n for n in neighbors
            if n in nodes_by_id
            and str(nodes_by_id[n]["kind"]) != "external"
            and n not in visited
            and str(nodes_by_id[n]["label"]) not in path_labels
        ]
        if internal:
            nxt = internal[0]
            visited.add(nxt)
            path_labels.add(str(nodes_by_id[nxt]["label"]))
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


def _deduplicate(storylines: list[Storyline]) -> list[Storyline]:
    """Remove near-duplicate storylines, keep diverse ones first."""
    if len(storylines) <= 1:
        return storylines

    def _key(s: Storyline) -> str:
        return "|".join(n.graph_node_id for n in s.nodes[:6])

    seen: set[str] = set()
    result: list[Storyline] = []
    for s in storylines:
        k = _key(s)
        if k not in seen:
            seen.add(k)
            result.append(s)

    # Sort: storylines with more nodes (up to 8) and more files first
    result.sort(key=lambda s: (min(s.node_count, 8) + s.file_count), reverse=True)
    return result


# ── Public entry point ───────────────────────────────────────────────


def discover_storylines(
    repo_root: Path,
    index: GraphIndex | None = None,
    min_nodes: int = 3,
    max_nodes: int = 12,
    adapter_factory: Any = None,
) -> list[Storyline]:
    """Auto-discover reading storylines using domain analysis + path planning.

    When adapter_factory is provided, uses LLM-enhanced stages 1+2.
    Falls back to rule-based BFS when LLM is unavailable or fails.
    """
    if index is None:
        index = build_graph_index(repo_root)

    adapter = None
    if adapter_factory is not None:
        try:
            adapter = adapter_factory()
        except Exception:
            adapter = None

    # Stage 1: Domain analysis
    domains = _analyze_project_domains(repo_root, adapter)

    if not domains:
        return []

    # Stage 2: Path planning
    storylines = _plan_storyline_paths(domains, index, adapter)

    return storylines


# ── Line resolution ──────────────────────────────────────────────────


def _resolve_line_end(file_path: Path, line_start: int) -> int:
    """Find the actual end line of a function/class definition."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return line_start

    lines = content.splitlines()
    if line_start > len(lines):
        return line_start

    for i in range(line_start, len(lines)):
        stripped = lines[i].lstrip()
        if stripped.startswith(("def ", "class ", "async def ")):
            return i
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


# ── Narrative generation ─────────────────────────────────────────────


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


def _generate_progressive_narrative(
    repo_root: Path,
    node_id: str,
    index: GraphIndex,
    storyline_title: str,
    prev_nodes: list[dict[str, str]] | None = None,
    cache: NarrativeCache | None = None,
    adapter: Any = None,
) -> NodeNarrative:
    """Stage 3: generate per-node teaching narrative with context."""
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
                next_teaser=cached.get("next_teaser") if cached.get("next_teaser") else None,
            )

    code_snippet = _read_node_source(repo_root, node)

    if adapter is None:
        return _fallback_narrative(node)

    # Build prev_nodes context
    prev_ctx = "（这是第一个节点，没有前序节点）"
    if prev_nodes:
        lines = []
        for pn in prev_nodes:
            lines.append(f"- [{pn.get('role', pn.get('label', '?'))}]: {pn.get('summary', '')[:200]}")
        prev_ctx = "\n".join(lines)

    prompt = STAGE3_PROGRESSIVE_NARRATIVE.format(
        storyline_title=storyline_title,
        previous_nodes_context=prev_ctx,
        node_role_title=str(node.get("label", "")),
        file_path=str(node["path"]),
        code_snippet=code_snippet,
    )

    try:
        raw = adapter.chat_sync(prompt)
        data = json.loads(raw.strip())
    except Exception:
        return _fallback_narrative(node)

    narrative = NodeNarrative(
        summary=str(data.get("summary", "")),
        design_notes=str(data.get("design_notes", "")),
        warnings=data.get("warnings") if data.get("warnings") else None,
        next_teaser=data.get("next_teaser") if data.get("next_teaser") else None,
    )

    if cache is not None:
        cache.set(cache_key, {
            "summary": narrative.summary,
            "design_notes": narrative.design_notes,
            "warnings": narrative.warnings,
            "next_teaser": narrative.next_teaser,
        })

    return narrative


async def generate_node_narrative(
    repo_root: Path,
    node_id: str,
    index: GraphIndex,
    cache: NarrativeCache | None = None,
    adapter_factory: Any = None,
    storyline_title: str = "",
    prev_nodes: list[dict[str, str]] | None = None,
) -> NodeNarrative:
    """Generate AI explanation for a single graph node. Uses progressive narrative."""
    nodes_by_id = index["nodes_by_id"]
    node = nodes_by_id.get(node_id)
    if not node:
        return NodeNarrative(summary="(节点不存在)", design_notes="", warnings=None)

    adapter = None
    if adapter_factory is not None:
        try:
            adapter = adapter_factory()
        except Exception:
            adapter = None

    return _generate_progressive_narrative(
        repo_root, node_id, index,
        storyline_title=storyline_title,
        prev_nodes=prev_nodes,
        cache=cache,
        adapter=adapter,
    )


def _fallback_narrative(node: dict[str, object]) -> NodeNarrative:
    label = str(node["label"])
    kind = str(node["kind"])
    path = str(node["path"])
    return NodeNarrative(
        summary=f"{label} — {kind}，位于 {path}",
        design_notes="AI 解释暂不可用。这里是关键代码段，请结合上下文理解其职责。",
        warnings=None,
    )


def _hash_id(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()[:12]
