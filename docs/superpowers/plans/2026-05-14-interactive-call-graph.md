# 交互式调用链/依赖图 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 agentCli Web 工作台中把现有 CallGraph JSON dump 替换为可交互的 Python 静态调用图，支持全局骨架加载、按节点展开、节点详情和双击打开源码。

**Architecture:** 后端新增 `src/agentcli/analysis/graph.py` 生成稳定唯一节点 ID（`path::qualname`），并通过 `server.py` 暴露 skeleton/expand/node 三个 API。`create_app` 内维护一个轻量图缓存，避免每次请求重复扫描仓库。前端新增 `web/src/graph/*` 模块，使用 Cytoscape.js + dagre 渲染调用图，并通过 `App.tsx` 的适配函数跳转 Monaco。

**Tech Stack:** Python 3.12+ AST, FastAPI, Pydantic v2, pytest, React 18, TypeScript strict mode, Cytoscape.js, cytoscape-dagre, Vite

---

## File Structure

- Create: `src/agentcli/analysis/graph.py` — 静态调用图索引、skeleton、expand、node detail。
- Modify: `src/agentcli/analysis/__init__.py` — 导出图分析函数。
- Modify: `src/agentcli/api/schemas.py` — 添加图 API 响应模型。
- Modify: `src/agentcli/api/server.py` — 添加图缓存和 `/api/graph/*` 端点。
- Create: `tests/test_graph.py` — 后端图索引和 BFS 展开测试。
- Modify: `tests/test_api_server.py` — 图 API 集成测试。
- Modify: `web/package.json` and `web/package-lock.json` — 添加 Cytoscape 依赖。
- Create: `web/src/graph/types.ts` — 前端图类型。
- Modify: `web/src/api/client.ts` — 添加图 API 客户端函数。
- Create: `web/src/graph/styles.ts` — Cytoscape 样式。
- Create: `web/src/graph/interactions.ts` — 图事件处理。
- Create: `web/src/graph/useCallGraph.ts` — 图加载、展开、详情和布局状态。
- Modify: `web/src/components/CallGraph.tsx` — 替换 JSON dump 为图面板。
- Modify: `web/src/App.tsx` — 使用 `openGraphNode` 适配 Monaco 打开文件签名。

---

### Task 1: Add Graph API Schemas

**Files:**
- Modify: `src/agentcli/api/schemas.py`

- [ ] **Step 1: Add graph response models**

Append this code after `TourResponse`:

```python
class GraphNode(BaseModel):
    id: str
    label: str
    path: str
    line: int
    kind: str
    degree: int = 0


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relation: str = "calls"
    is_cycle: bool = False


class SkeletonResponse(BaseModel):
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    warning: str | None = None
    skipped_files: list[str] = []


class ExpandResponse(BaseModel):
    root: str
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []


class NodeDetailResponse(BaseModel):
    node: GraphNode | None = None
    incoming: list[GraphEdge] = []
    outgoing: list[GraphEdge] = []
```

- [ ] **Step 2: Verify schemas import**

Run: `python -c "from agentcli.api.schemas import GraphNode, GraphEdge, SkeletonResponse, ExpandResponse, NodeDetailResponse; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/agentcli/api/schemas.py
git commit -m "feat: add graph API schemas"
```

---

### Task 2: Build Static Graph Index

**Files:**
- Create: `src/agentcli/analysis/graph.py`
- Create: `tests/test_graph.py`

- [ ] **Step 1: Write failing graph index tests**

Create `tests/test_graph.py`:

```python
from pathlib import Path

from agentcli.analysis.graph import build_graph_index, build_skeleton_graph


def test_build_skeleton_graph_returns_unique_nodes_and_edges(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text(
        """
def helper():
    return "a"


def main():
    return helper()
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "pkg" / "b.py").write_text(
        """
def helper():
    return "b"
""".strip(),
        encoding="utf-8",
    )

    result = build_skeleton_graph(tmp_path)

    ids = {node["id"] for node in result["nodes"]}
    assert "pkg/a.py::main" in ids
    assert "pkg/a.py::helper" in ids
    assert "pkg/b.py::helper" in ids
    assert any(
        edge["source"] == "pkg/a.py::main" and edge["target"] == "pkg/a.py::helper"
        for edge in result["edges"]
    )


def test_build_skeleton_graph_empty_repo(tmp_path: Path) -> None:
    result = build_skeleton_graph(tmp_path)

    assert result["nodes"] == []
    assert result["edges"] == []
    assert result["warning"] == "no_python_files"


def test_build_graph_index_reports_skipped_syntax_error_files(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def func(:\n    pass\n", encoding="utf-8")
    (tmp_path / "ok.py").write_text("def ok():\n    pass\n", encoding="utf-8")

    index = build_graph_index(tmp_path)

    assert "broken.py" in index["skipped_files"]
    assert "ok.py::ok" in index["nodes_by_id"]


def test_build_skeleton_graph_methods_use_class_qualified_labels(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        """
class Worker:
    def run(self):
        self.save()

    def save(self):
        pass
""".strip(),
        encoding="utf-8",
    )

    result = build_skeleton_graph(tmp_path)

    labels = {node["label"] for node in result["nodes"]}
    assert "Worker.run" in labels
    assert "Worker.save" in labels
    assert any(
        edge["source"] == "app.py::Worker.run" and edge["target"] == "app.py::Worker.save"
        for edge in result["edges"]
    )
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_graph.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'agentcli.analysis.graph'`

- [ ] **Step 3: Implement graph index and skeleton**

Create `src/agentcli/analysis/graph.py`:

```python
from __future__ import annotations

import ast
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
        self._current_symbol: str | None = None

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
        label = f"{self._class_stack[-1]}.{node.name}" if self._class_stack else node.name
        kind = "method" if self._class_stack else "function"
        previous = self._current_symbol
        self._current_symbol = label
        self._add_node(label, node.lineno, kind)
        self.raw_calls[label] = self._collect_calls(node)
        self._current_symbol = previous

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
```

- [ ] **Step 4: Run graph tests**

Run: `python -m pytest tests/test_graph.py -v`

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/agentcli/analysis/graph.py tests/test_graph.py
git commit -m "feat: build static call graph index"
```

---

### Task 3: Add Expand and Node Detail

**Files:**
- Modify: `src/agentcli/analysis/graph.py`
- Modify: `tests/test_graph.py`

- [ ] **Step 1: Add failing expand/detail tests**

Append to `tests/test_graph.py`:

```python
from agentcli.analysis.graph import expand_call_node, get_node_detail


def test_expand_call_node_returns_bfs_subgraph(tmp_path: Path) -> None:
    (tmp_path / "chain.py").write_text(
        """
def a():
    return b()


def b():
    return c()


def c():
    return "done"
""".strip(),
        encoding="utf-8",
    )

    result = expand_call_node(tmp_path, "chain.py::a", depth=2)

    ids = {node["id"] for node in result["nodes"]}
    assert result["root"] == "chain.py::a"
    assert "chain.py::a" in ids
    assert "chain.py::b" in ids
    assert "chain.py::c" in ids
    assert any(edge["source"] == "chain.py::b" and edge["target"] == "chain.py::c" for edge in result["edges"])


def test_expand_call_node_respects_depth(tmp_path: Path) -> None:
    (tmp_path / "chain.py").write_text(
        """
def a():
    return b()


def b():
    return c()


def c():
    return "done"
""".strip(),
        encoding="utf-8",
    )

    result = expand_call_node(tmp_path, "chain.py::a", depth=1)

    ids = {node["id"] for node in result["nodes"]}
    assert "chain.py::b" in ids
    assert "chain.py::c" not in ids


def test_expand_call_node_unknown_or_external_node(tmp_path: Path) -> None:
    result = expand_call_node(tmp_path, "missing.py::ghost", depth=3)

    assert result == {"root": "missing.py::ghost", "nodes": [], "edges": []}


def test_get_node_detail_returns_incoming_and_outgoing_edges(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        """
def setup():
    pass


def main():
    setup()
""".strip(),
        encoding="utf-8",
    )

    result = get_node_detail(tmp_path, "app.py::setup")

    assert result["node"]["id"] == "app.py::setup"
    assert [edge["source"] for edge in result["incoming"]] == ["app.py::main"]
    assert result["outgoing"] == []
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_graph.py -v`

Expected: FAIL because `expand_call_node` and `get_node_detail` are not defined.

- [ ] **Step 3: Implement expand and detail**

Append to `src/agentcli/analysis/graph.py`:

```python
from collections import deque


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
    queued: set[str] = {node_id}
    queue: deque[tuple[str, int]] = deque([(node_id, 0)])

    while queue:
        current, current_depth = queue.popleft()
        if current_depth >= depth:
            continue
        for edge in outgoing.get(current, []):
            target = str(edge["target"])
            included_edges.append(edge)
            if target not in included_nodes:
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
```

- [ ] **Step 4: Run graph tests**

Run: `python -m pytest tests/test_graph.py -v`

Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/agentcli/analysis/graph.py tests/test_graph.py
git commit -m "feat: add graph expansion and node detail"
```

---

### Task 4: Export Graph Analysis Functions

**Files:**
- Modify: `src/agentcli/analysis/__init__.py`

- [ ] **Step 1: Add imports and `__all__` entries**

Add this import near the other analysis imports:

```python
from agentcli.analysis.graph import build_graph_index, build_skeleton_graph, expand_call_node, get_node_detail
```

Add these strings to `__all__`:

```python
    "build_graph_index",
    "build_skeleton_graph",
    "expand_call_node",
    "get_node_detail",
```

- [ ] **Step 2: Verify package-level import**

Run: `python -c "from agentcli.analysis import build_skeleton_graph, expand_call_node, get_node_detail; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/agentcli/analysis/__init__.py
git commit -m "feat: export graph analysis functions"
```

---

### Task 5: Add Graph API Endpoints With Cache

**Files:**
- Modify: `src/agentcli/api/server.py`
- Modify: `tests/test_api_server.py`

- [ ] **Step 1: Add API integration tests**

Append to `tests/test_api_server.py`:

```python
def test_graph_skeleton_endpoint_returns_nodes_edges_and_skipped_files(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("def main():\n    helper()\n\ndef helper():\n    pass\n", encoding="utf-8")
    (tmp_path / "broken.py").write_text("def broken(:\n    pass\n", encoding="utf-8")
    client = TestClient(create_app(tmp_path, adapter_factory=lambda: FakeAdapter()))

    response = client.get("/api/graph/skeleton")

    assert response.status_code == 200
    payload = response.json()
    assert any(node["id"] == "main.py::main" for node in payload["nodes"])
    assert any(edge["source"] == "main.py::main" and edge["target"] == "main.py::helper" for edge in payload["edges"])
    assert payload["skipped_files"] == ["broken.py"]


def test_graph_expand_endpoint_returns_subgraph(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("def main():\n    helper()\n\ndef helper():\n    pass\n", encoding="utf-8")
    client = TestClient(create_app(tmp_path, adapter_factory=lambda: FakeAdapter()))

    response = client.get("/api/graph/expand", params={"node_id": "main.py::main", "depth": 2})

    assert response.status_code == 200
    payload = response.json()
    assert payload["root"] == "main.py::main"
    assert any(node["id"] == "main.py::helper" for node in payload["nodes"])


def test_graph_node_endpoint_returns_detail(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("def main():\n    helper()\n\ndef helper():\n    pass\n", encoding="utf-8")
    client = TestClient(create_app(tmp_path, adapter_factory=lambda: FakeAdapter()))

    response = client.get("/api/graph/node", params={"node_id": "main.py::helper"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["node"]["id"] == "main.py::helper"
    assert payload["incoming"][0]["source"] == "main.py::main"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_api_server.py -v -k "graph_"`

Expected: FAIL with 404 responses for `/api/graph/*`.

- [ ] **Step 3: Add imports**

In `src/agentcli/api/server.py`, add schemas to the existing `from agentcli.api.schemas import (...)` block:

```python
    ExpandResponse,
    GraphEdge,
    GraphNode,
    NodeDetailResponse,
    SkeletonResponse,
```

Add graph function imports:

```python
from agentcli.analysis.graph import build_graph_index, build_skeleton_graph, expand_call_node, get_node_detail
```

- [ ] **Step 4: Add cache helpers inside `create_app`**

Inside `create_app`, after `runs` is created, add:

```python
    graph_cache: dict[str, object] = {"signature": None, "index": None}

    def _repo_graph_signature() -> tuple[tuple[str, int, int], ...]:
        signature: list[tuple[str, int, int]] = []
        for rel_path in enumerate_repo_files(resolved_repo):
            if not rel_path.endswith(".py"):
                continue
            path = resolved_repo / rel_path
            try:
                stat = path.stat()
            except OSError:
                continue
            signature.append((rel_path, int(stat.st_mtime_ns), int(stat.st_size)))
        return tuple(signature)

    def _get_graph_index() -> dict[str, object]:
        signature = _repo_graph_signature()
        if graph_cache["signature"] != signature:
            graph_cache["signature"] = signature
            graph_cache["index"] = build_graph_index(resolved_repo)
        return graph_cache["index"]  # type: ignore[return-value]
```

- [ ] **Step 5: Add graph endpoints before `/api/tour`**

Insert before `_TOUR_PROMPT`:

```python
    @app.get("/api/graph/skeleton", response_model=SkeletonResponse)
    def get_graph_skeleton() -> SkeletonResponse:
        index = _get_graph_index()
        return SkeletonResponse(
            nodes=[GraphNode(**node) for node in index["nodes_by_id"].values()],
            edges=[GraphEdge(**edge) for edge in index["edges"]],
            warning=index.get("warning"),
            skipped_files=list(index.get("skipped_files", [])),
        )

    @app.get("/api/graph/expand", response_model=ExpandResponse)
    def get_graph_expand(node_id: str = Query(...), depth: int = Query(3, ge=1, le=5)) -> ExpandResponse:
        result = expand_call_node(resolved_repo, node_id, depth)
        return ExpandResponse(
            root=str(result["root"]),
            nodes=[GraphNode(**node) for node in result["nodes"]],
            edges=[GraphEdge(**edge) for edge in result["edges"]],
        )

    @app.get("/api/graph/node", response_model=NodeDetailResponse)
    def get_graph_node(node_id: str = Query(...)) -> NodeDetailResponse:
        result = get_node_detail(resolved_repo, node_id)
        node = result["node"]
        return NodeDetailResponse(
            node=GraphNode(**node) if node else None,
            incoming=[GraphEdge(**edge) for edge in result["incoming"]],
            outgoing=[GraphEdge(**edge) for edge in result["outgoing"]],
        )
```

Note: this uses cached index for skeleton, while expand/detail rebuild through `graph.py`. If this becomes slow, update `expand_call_node` and `get_node_detail` to accept a prebuilt index in a follow-up. Do not expand this task beyond the MVP.

- [ ] **Step 6: Run API graph tests**

Run: `python -m pytest tests/test_api_server.py -v -k "graph_"`

Expected: 3 passed

- [ ] **Step 7: Commit**

```bash
git add src/agentcli/api/server.py tests/test_api_server.py
git commit -m "feat: add graph API endpoints"
```

---

### Task 6: Install Frontend Graph Dependencies

**Files:**
- Modify: `web/package.json`
- Modify: `web/package-lock.json`

- [ ] **Step 1: Install runtime dependencies**

Run: `cd web && npm install cytoscape cytoscape-dagre`

Expected: `web/package.json` and `web/package-lock.json` include the new packages.

- [ ] **Step 2: Install Cytoscape type definitions**

Run: `cd web && npm install --save-dev @types/cytoscape`

Expected: `@types/cytoscape` is in `devDependencies`.

- [ ] **Step 3: Verify dependency import**

Run: `cd web && node -e "import('cytoscape').then(() => console.log('OK'))"`

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add web/package.json web/package-lock.json
git commit -m "chore: add cytoscape dependencies"
```

---

### Task 7: Add Frontend Types and API Client

**Files:**
- Create: `web/src/graph/types.ts`
- Modify: `web/src/api/client.ts`

- [ ] **Step 1: Create graph TypeScript types**

Create `web/src/graph/types.ts`:

```typescript
export type GraphNodeData = {
  id: string;
  label: string;
  path: string;
  line: number;
  kind: "function" | "method" | "class" | "external";
  degree: number;
};

export type GraphEdgeData = {
  id: string;
  source: string;
  target: string;
  relation: "calls";
  is_cycle: boolean;
};

export type SkeletonData = {
  nodes: GraphNodeData[];
  edges: GraphEdgeData[];
  warning?: string | null;
  skipped_files: string[];
};

export type ExpandData = {
  root: string;
  nodes: GraphNodeData[];
  edges: GraphEdgeData[];
};

export type NodeDetailData = {
  node: GraphNodeData | null;
  incoming: GraphEdgeData[];
  outgoing: GraphEdgeData[];
};
```

- [ ] **Step 2: Add graph API client functions**

Append to `web/src/api/client.ts`:

```typescript
import type { ExpandData, NodeDetailData, SkeletonData } from "../graph/types";

async function readJsonResponse<T>(response: Response, fallbackMessage: string): Promise<T> {
  if (!response.ok) {
    throw new Error(`${fallbackMessage}: ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function fetchGraphSkeleton(signal?: AbortSignal): Promise<SkeletonData> {
  const response = await fetch("/api/graph/skeleton", { signal });
  return readJsonResponse<SkeletonData>(response, "Failed to load graph skeleton");
}

export async function fetchGraphExpand(nodeId: string, depth = 3, signal?: AbortSignal): Promise<ExpandData> {
  const params = new URLSearchParams({ node_id: nodeId, depth: String(depth) });
  const response = await fetch(`/api/graph/expand?${params.toString()}`, { signal });
  return readJsonResponse<ExpandData>(response, "Failed to expand graph node");
}

export async function fetchGraphNode(nodeId: string, signal?: AbortSignal): Promise<NodeDetailData> {
  const params = new URLSearchParams({ node_id: nodeId });
  const response = await fetch(`/api/graph/node?${params.toString()}`, { signal });
  return readJsonResponse<NodeDetailData>(response, "Failed to load graph node");
}
```

- [ ] **Step 3: Verify TypeScript**

Run: `cd web && npx tsc --noEmit`

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add web/src/graph/types.ts web/src/api/client.ts
git commit -m "feat: add graph frontend API types"
```

---

### Task 8: Add Cytoscape Styles and Interactions

**Files:**
- Create: `web/src/graph/styles.ts`
- Create: `web/src/graph/interactions.ts`

- [ ] **Step 1: Create Cytoscape styles**

Create `web/src/graph/styles.ts`:

```typescript
import type { Stylesheet } from "cytoscape";

export const CALL_GRAPH_STYLES: Stylesheet[] = [
  {
    selector: "node",
    style: {
      "background-color": "#4a7d2d",
      label: "data(label)",
      "font-size": "11px",
      color: "#d8dee9",
      "text-valign": "bottom",
      "text-halign": "center",
      "text-margin-y": 6,
      width: 16,
      height: 16,
      "border-width": 1,
      "border-color": "#263238",
      shape: "round-rectangle",
    },
  },
  {
    selector: "node[kind='method']",
    style: { "background-color": "#2d6da4", "border-color": "#1a3a5c" },
  },
  {
    selector: "node[kind='class']",
    style: { "background-color": "#8b6d2d", "border-color": "#4a3d1a" },
  },
  {
    selector: "node[kind='external']",
    style: {
      "background-color": "#6d2d6d",
      "border-color": "#3d1a3d",
      shape: "ellipse",
      width: 12,
      height: 12,
    },
  },
  {
    selector: "node:selected",
    style: {
      "border-width": 3,
      "border-color": "#f0c674",
    },
  },
  {
    selector: "edge",
    style: {
      width: 1.5,
      "line-color": "#596275",
      "target-arrow-color": "#596275",
      "target-arrow-shape": "triangle",
      "curve-style": "bezier",
    },
  },
  {
    selector: "edge[is_cycle]",
    style: {
      "line-style": "dashed",
      "line-color": "#d08770",
      "target-arrow-color": "#d08770",
    },
  },
];
```

- [ ] **Step 2: Create interaction helpers**

Create `web/src/graph/interactions.ts`:

```typescript
import type { Core, EventObject } from "cytoscape";

export type OpenFileHandler = (path: string, line?: number) => void;
export type ExpandHandler = (nodeId: string) => void;
export type SelectHandler = (nodeId: string) => void;

export function setupGraphInteractions(
  cy: Core,
  onOpenFile: OpenFileHandler,
  onExpand: ExpandHandler,
  onSelect: SelectHandler,
): () => void {
  const openNode = (evt: EventObject) => {
    const node = evt.target;
    const path = String(node.data("path") ?? "");
    const line = Number(node.data("line") ?? 0);
    if (path) onOpenFile(path, line > 0 ? line : undefined);
  };

  const expandNode = (evt: EventObject) => {
    const node = evt.target;
    if (node.data("kind") !== "external") {
      onExpand(String(node.data("id")));
    }
  };

  const selectNode = (evt: EventObject) => {
    onSelect(String(evt.target.data("id")));
  };

  cy.on("dbltap", "node", openNode);
  cy.on("cxttap", "node", expandNode);
  cy.on("tap", "node", selectNode);

  return () => {
    cy.off("dbltap", "node", openNode);
    cy.off("cxttap", "node", expandNode);
    cy.off("tap", "node", selectNode);
  };
}
```

- [ ] **Step 3: Verify TypeScript**

Run: `cd web && npx tsc --noEmit`

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add web/src/graph/styles.ts web/src/graph/interactions.ts
git commit -m "feat: add graph styles and interactions"
```

---

### Task 9: Add `useCallGraph` Hook

**Files:**
- Create: `web/src/graph/useCallGraph.ts`

- [ ] **Step 1: Implement graph state hook**

Create `web/src/graph/useCallGraph.ts`:

```typescript
import { useCallback, useEffect, useRef, useState } from "react";
import cytoscape, { Core, ElementDefinition } from "cytoscape";
import dagre from "cytoscape-dagre";

import { fetchGraphExpand, fetchGraphNode, fetchGraphSkeleton } from "../api/client";
import { setupGraphInteractions } from "./interactions";
import { CALL_GRAPH_STYLES } from "./styles";
import type { GraphEdgeData, GraphNodeData, NodeDetailData } from "./types";

cytoscape.use(dagre);

export type CallGraphState = {
  isLoading: boolean;
  error: string | null;
  warning: string | null;
  skippedFiles: string[];
  nodeCount: number;
  edgeCount: number;
  selectedNode: NodeDetailData | null;
};

function toElements(nodes: GraphNodeData[], edges: GraphEdgeData[]): ElementDefinition[] {
  return [
    ...nodes.map((node) => ({
      data: {
        id: node.id,
        label: node.label,
        path: node.path,
        line: node.line,
        kind: node.kind,
        degree: node.degree,
      },
    })),
    ...edges.map((edge) => ({
      data: {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        relation: edge.relation,
        is_cycle: edge.is_cycle,
      },
    })),
  ];
}

function runLayout(cy: Core): void {
  cy.layout({
    name: "dagre",
    rankDir: "TB",
    spacingFactor: 1.25,
    animate: true,
    animationDuration: 250,
  } as cytoscape.LayoutOptions).run();
}

export function useCallGraph(
  containerRef: React.RefObject<HTMLDivElement>,
  onOpenFile: (path: string, line?: number) => void,
) {
  const cyRef = useRef<Core | null>(null);
  const [state, setState] = useState<CallGraphState>({
    isLoading: true,
    error: null,
    warning: null,
    skippedFiles: [],
    nodeCount: 0,
    edgeCount: 0,
    selectedNode: null,
  });

  const loadSkeleton = useCallback(async () => {
    setState((current) => ({ ...current, isLoading: true, error: null }));
    const controller = new AbortController();
    try {
      const data = await fetchGraphSkeleton(controller.signal);
      const cy = cyRef.current;
      if (!cy) return;

      cy.elements().remove();
      cy.add(toElements(data.nodes, data.edges));
      runLayout(cy);
      cy.fit(undefined, 24);

      setState((current) => ({
        ...current,
        isLoading: false,
        warning: data.warning ?? null,
        skippedFiles: data.skipped_files,
        nodeCount: data.nodes.length,
        edgeCount: data.edges.length,
        selectedNode: null,
      }));
    } catch (err) {
      setState((current) => ({
        ...current,
        isLoading: false,
        error: err instanceof Error ? err.message : "Failed to load graph",
      }));
    }
  }, []);

  const expandNode = useCallback(async (nodeId: string) => {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 5000);
    try {
      const data = await fetchGraphExpand(nodeId, 3, controller.signal);
      window.clearTimeout(timeoutId);

      const cy = cyRef.current;
      if (!cy) return;

      cy.add(toElements(
        data.nodes.filter((node) => cy.getElementById(node.id).empty()),
        data.edges.filter((edge) => cy.getElementById(edge.id).empty()),
      ));
      runLayout(cy);
      setState((current) => ({
        ...current,
        error: null,
        nodeCount: cy.nodes().length,
        edgeCount: cy.edges().length,
      }));
    } catch (err) {
      window.clearTimeout(timeoutId);
      const message = err instanceof DOMException && err.name === "AbortError"
        ? "Expand timeout. Please retry."
        : err instanceof Error ? err.message : "Failed to expand node";
      setState((current) => ({ ...current, error: message }));
    }
  }, []);

  const selectNode = useCallback(async (nodeId: string) => {
    try {
      const detail = await fetchGraphNode(nodeId);
      setState((current) => ({ ...current, selectedNode: detail, error: null }));
    } catch (err) {
      setState((current) => ({
        ...current,
        error: err instanceof Error ? err.message : "Failed to load node detail",
      }));
    }
  }, []);

  const fit = useCallback(() => {
    cyRef.current?.fit(undefined, 24);
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;

    const cy = cytoscape({
      container: containerRef.current,
      style: CALL_GRAPH_STYLES,
      wheelSensitivity: 0.25,
      minZoom: 0.15,
      maxZoom: 3,
    });
    cyRef.current = cy;
    const cleanupInteractions = setupGraphInteractions(cy, onOpenFile, expandNode, selectNode);
    loadSkeleton();

    return () => {
      cleanupInteractions();
      cy.destroy();
      cyRef.current = null;
    };
  }, [containerRef, expandNode, loadSkeleton, onOpenFile, selectNode]);

  return { state, loadSkeleton, expandNode, fit };
}
```

- [ ] **Step 2: Verify TypeScript**

Run: `cd web && npx tsc --noEmit`

Expected: no errors. If TypeScript reports missing `cytoscape-dagre` types, add a local declaration file in this same task:

```typescript
declare module "cytoscape-dagre";
```

Save it as `web/src/graph/cytoscape-dagre.d.ts`, then rerun TypeScript.

- [ ] **Step 3: Commit**

```bash
git add web/src/graph/useCallGraph.ts web/src/graph/cytoscape-dagre.d.ts
git commit -m "feat: add call graph state hook"
```

---

### Task 10: Rewrite CallGraph Component

**Files:**
- Modify: `web/src/components/CallGraph.tsx`

- [ ] **Step 1: Replace JSON dump component**

Replace `web/src/components/CallGraph.tsx` with:

```tsx
import { useRef } from "react";

import { useCallGraph } from "../graph/useCallGraph";

type CallGraphProps = {
  onOpenFile: (path: string, line?: number) => void;
};

export function CallGraph({ onOpenFile }: CallGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { state, loadSkeleton, fit } = useCallGraph(containerRef, onOpenFile);
  const selected = state.selectedNode?.node;

  return (
    <div className="panel" style={{ display: "flex", flexDirection: "column", minHeight: 360 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <h3 style={{ margin: 0 }}>Call Graph</h3>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span className="muted" style={{ fontSize: 11 }}>
            {state.nodeCount} nodes / {state.edgeCount} edges
          </span>
          <button className="toolbar-btn" onClick={fit} type="button">
            Fit
          </button>
          <button className="toolbar-btn" disabled={state.isLoading} onClick={loadSkeleton} type="button">
            Refresh
          </button>
        </div>
      </div>

      {state.warning ? (
        <p className="muted" style={{ marginBottom: 0 }}>
          {state.warning}
        </p>
      ) : null}

      {state.skippedFiles.length > 0 ? (
        <p className="muted" style={{ marginBottom: 0 }}>
          Skipped {state.skippedFiles.length} file(s) with syntax or encoding errors.
        </p>
      ) : null}

      {state.error ? (
        <div style={{ marginTop: 8, color: "#f0a0a0", fontSize: 12 }}>
          {state.error}
        </div>
      ) : null}

      <div
        ref={containerRef}
        style={{
          flex: "1 1 260px",
          minHeight: 260,
          marginTop: 10,
          border: "1px solid var(--border)",
          borderRadius: 8,
          background: "#0b1020",
        }}
      />

      <div className="muted" style={{ marginTop: 8, fontSize: 11 }}>
        Double-click opens source. Right-click expands a node. Click selects details.
      </div>

      {selected ? (
        <div style={{ marginTop: 8, fontSize: 12 }}>
          <strong>{selected.label}</strong>
          <div className="muted">
            {selected.path}:{selected.line} · in {state.selectedNode?.incoming.length ?? 0} / out{" "}
            {state.selectedNode?.outgoing.length ?? 0}
          </div>
        </div>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript**

Run: `cd web && npx tsc --noEmit`

Expected: FAIL because `App.tsx` still passes `events`.

- [ ] **Step 3: Commit after App wiring task, not now**

Do not commit this task alone because the app is temporarily not type-correct. Continue directly to Task 11.

---

### Task 11: Wire CallGraph Into App

**Files:**
- Modify: `web/src/App.tsx`

- [ ] **Step 1: Add graph open-file adapter**

In `web/src/App.tsx`, after `openFileByKeyLines`, add:

```tsx
  function openGraphNode(path: string, line?: number) {
    openFile(path, line ? { path, startLine: line, endLine: line } : undefined);
  }
```

- [ ] **Step 2: Replace CallGraph usage**

Replace:

```tsx
<CallGraph events={events} />
```

with:

```tsx
<CallGraph onOpenFile={openGraphNode} />
```

- [ ] **Step 3: Verify TypeScript**

Run: `cd web && npx tsc --noEmit`

Expected: no errors.

- [ ] **Step 4: Commit component and app wiring**

```bash
git add web/src/components/CallGraph.tsx web/src/App.tsx
git commit -m "feat: render interactive call graph panel"
```

---

### Task 12: Full Verification

**Files:**
- None unless fixes are required.

- [ ] **Step 1: Run backend tests**

Run: `python -m pytest tests/ -v`

Expected: all tests pass.

- [ ] **Step 2: Build frontend**

Run: `cd web && npm run build`

Expected: build succeeds.

- [ ] **Step 3: Start the web app manually**

Run: `python -m agentcli web --repo .`

Expected: server starts and prints the local URL.

- [ ] **Step 4: Manual browser verification**

Open the local URL and verify:

- The right inspector "分析" tab shows the Call Graph panel.
- The graph loads nodes for Python files in the current repository.
- Double-clicking a non-external node opens the source file near the function line.
- Right-clicking a non-external node expands its outgoing calls.
- Clicking a node shows basic detail below the graph.
- Refresh reloads the skeleton and Fit recenters the graph.

- [ ] **Step 5: Commit fixes from verification**

If verification required changes:

```bash
git add <changed-files>
git commit -m "fix: address call graph verification issues"
```

If no changes were required, do not create an empty commit.

---

## Self-Review Notes

- Spec coverage: This plan covers MVP skeleton loading, BFS expand, node detail, Monaco open-file integration, skipped syntax files, unique IDs, API errors, and frontend build verification.
- Intentional deferrals: node folding, search, layout switching, PNG/SVG export, Monaco-to-graph reverse navigation, virtualization, and multi-language analysis remain non-goals for this plan.
- Known trade-off: API skeleton uses the `create_app` cache; expand/detail rebuild via analysis functions for simpler implementation. If performance is poor, update graph functions to accept a prebuilt index in a follow-up task.
