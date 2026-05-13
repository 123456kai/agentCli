# 交互式调用链/依赖图 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 agentCli Web 工作台中增加交互式调用链图面板，后端 AST 分析 + 前端 Cytoscape.js 层次树渲染，支持节点展开/折叠和 Monaco 双向联动。

**Architecture:** 后端新增 `analysis/graph.py` 复用 `trace.py` 的 AST 扫描，提供 skeleton/expand/node 三个函数；`server.py` 新增三个 GET 端点。前端重写 `CallGraph.tsx` 为 Cytoscape.js 容器，拆出 `useCallGraph` / `styles` / `interactions` 三个模块。

**Tech Stack:** Python 3.12+ AST, FastAPI, Cytoscape.js + dagre 布局, React 18, TypeScript

---

### Task 1: 新增图数据模型

**Files:**
- Modify: `src/agentcli/api/schemas.py`

- [ ] **Step 1: 在 schemas.py 末尾添加 GraphNode, GraphEdge, SkeletonResponse, ExpandResponse, NodeDetailResponse**

```python
class GraphNode(BaseModel):
    id: str
    path: str
    line: int
    kind: str  # "function" | "method" | "class" | "external"
    degree: int = 0


class GraphEdge(BaseModel):
    source: str
    target: str
    relation: str = "calls"


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
    symbol: str
    path: str
    line: int
    kind: str
    incoming: list[str] = []
    outgoing: list[str] = []
    docstring: str | None = None
```

- [ ] **Step 2: 运行测试确认模型可导入**

Run: `cd d:/pythonProject/agentCli/agentCli && python -c "from agentcli.api.schemas import GraphNode, GraphEdge, SkeletonResponse, ExpandResponse, NodeDetailResponse; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/agentcli/api/schemas.py
git commit -m "feat: add graph data models (GraphNode, GraphEdge, API responses)"
```

---

### Task 2: 实现 graph.py — build_skeleton_graph

**Files:**
- Create: `src/agentcli/analysis/graph.py`

- [ ] **Step 1: 编写失败的测试**

Create: `tests/test_graph.py`

```python
from pathlib import Path
from agentcli.analysis.graph import build_skeleton_graph


def test_build_skeleton_graph_returns_nodes_and_edges(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        """
def helper():
    return "ok"

def main():
    result = helper()
    print(result)
""".strip(),
        encoding="utf-8",
    )

    result = build_skeleton_graph(tmp_path)

    assert result["nodes"], "expected at least one node"
    symbols = [n["id"] for n in result["nodes"]]
    assert "main" in symbols
    assert "helper" in symbols

    edges = result["edges"]
    assert any(e["source"] == "main" and e["target"] == "helper" for e in edges)


def test_build_skeleton_graph_empty_repo(tmp_path: Path) -> None:
    result = build_skeleton_graph(tmp_path)
    assert result["nodes"] == []
    assert result["edges"] == []
    assert result["warning"] == "no_python_files"


def test_build_skeleton_graph_skips_syntax_error(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def func(:\n    pass\n", encoding="utf-8")
    (tmp_path / "ok.py").write_text("def ok():\n    pass\n", encoding="utf-8")

    result = build_skeleton_graph(tmp_path)

    assert "ok" in [n["id"] for n in result["nodes"]]
    assert "broken.py" in result["skipped_files"]


def test_build_skeleton_graph_methods_use_class_prefix(tmp_path: Path) -> None:
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

    symbols = [n["id"] for n in result["nodes"]]
    assert "Worker.run" in symbols
    assert "Worker.save" in symbols
    edges = result["edges"]
    assert any(e["source"] == "Worker.run" and e["target"] == "Worker.save" for e in edges)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd d:/pythonProject/agentCli/agentCli && python -m pytest tests/test_graph.py -v`

Expected: FAIL — ModuleNotFoundError (graph module doesn't exist yet)

- [ ] **Step 3: 实现 build_skeleton_graph**

Create `src/agentcli/analysis/graph.py`:

```python
from __future__ import annotations

from pathlib import Path

from agentcli.analysis.trace import _build_definition_index
from agentcli.analysis.trace import _build_definition_index
from agentcli.repo_guard import enumerate_repo_files


def _collect_class_names(repo_root: Path) -> set[str]:
    import ast
    class_names: set[str] = set()
    for rel_path in enumerate_repo_files(repo_root):
        if not rel_path.endswith(".py"):
            continue
        path = repo_root / rel_path
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_names.add(node.name)
    return class_names


def build_skeleton_graph(repo_root: Path) -> dict:
    py_files = [f for f in enumerate_repo_files(repo_root) if f.endswith(".py")]
    if not py_files:
        return {"nodes": [], "edges": [], "warning": "no_python_files", "skipped_files": []}

    index = _build_definition_index(repo_root)
    class_names = _collect_class_names(repo_root)

    nodes: list[dict] = []
    edges: list[dict] = []
    seen_ids: set[str] = set()

    for symbol, (rel_path, line, calls) in index.items():
        if symbol in seen_ids:
            continue
        seen_ids.add(symbol)

        if symbol in class_names:
            kind = "class"
        elif "." in symbol:
            parts = symbol.split(".")
            if len(parts) >= 2 and parts[-2][0].isupper():
                kind = "method"
            else:
                kind = "function"
        else:
            kind = "function"

        nodes.append({
            "id": symbol,
            "path": rel_path,
            "line": line,
            "kind": kind,
            "degree": len(calls),
        })

        for called in calls:
            resolved = called
            if called not in index:
                matches = [name for name in index if name == called or name.endswith(f".{called}")]
                resolved = matches[0] if len(matches) == 1 else called

            target_kind = "function"
            if resolved in index:
                target_kind = "method" if "." in resolved else "function"

            edges.append({
                "source": symbol,
                "target": resolved,
                "relation": "calls",
            })

            if resolved not in seen_ids and resolved not in index:
                nodes.append({
                    "id": resolved,
                    "path": "",
                    "line": 0,
                    "kind": "external",
                    "degree": 0,
                })
                seen_ids.add(resolved)

    return {"nodes": nodes, "edges": edges, "skipped_files": []}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd d:/pythonProject/agentCli/agentCli && python -m pytest tests/test_graph.py -v`

Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/agentcli/analysis/graph.py tests/test_graph.py
git commit -m "feat: add build_skeleton_graph for full-repo AST scan"
```

---

### Task 3: 实现 expand_call_node

**Files:**
- Modify: `src/agentcli/analysis/graph.py`

- [ ] **Step 1: 编写测试**

Append to `tests/test_graph.py`:

```python
from agentcli.analysis.graph import expand_call_node


def test_expand_call_node_returns_subtree(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        """
def helper():
    return util()

def util():
    return "ok"

def main():
    result = helper()
    print(result)
""".strip(),
        encoding="utf-8",
    )

    result = expand_call_node(tmp_path, "main", depth=2)

    assert result["root"] == "main"
    symbols = [n["id"] for n in result["nodes"]]
    assert "helper" in symbols
    assert "util" in symbols
    edges = result["edges"]
    assert any(e["source"] == "main" and e["target"] == "helper" for e in edges)
    assert any(e["source"] == "helper" and e["target"] == "util" for e in edges)


def test_expand_call_node_respects_depth(tmp_path: Path) -> None:
    (tmp_path / "chain.py").write_text(
        """
def a():
    return b()

def b():
    return c()

def c():
    return d()

def d():
    return "deep"
""".strip(),
        encoding="utf-8",
    )

    result_shallow = expand_call_node(tmp_path, "a", depth=1)
    shallow_symbols = [n["id"] for n in result_shallow["nodes"]]
    assert "b" in shallow_symbols
    assert "c" not in shallow_symbols

    result_deep = expand_call_node(tmp_path, "a", depth=3)
    deep_symbols = [n["id"] for n in result_deep["nodes"]]
    assert "c" in deep_symbols
    assert "d" in deep_symbols


def test_expand_call_node_unknown_symbol(tmp_path: Path) -> None:
    result = expand_call_node(tmp_path, "nonexistent", depth=2)
    assert result["nodes"] == []
    assert result["edges"] == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd d:/pythonProject/agentCli/agentCli && python -m pytest tests/test_graph.py::test_expand_call_node_returns_subtree -v`

Expected: FAIL — expand_call_node not defined

- [ ] **Step 3: 实现 expand_call_node**

Append to `src/agentcli/analysis/graph.py`:

```python
from collections import deque


def expand_call_node(repo_root: Path, symbol: str, depth: int = 3) -> dict:
    index = _build_definition_index(repo_root)

    resolved = symbol
    if symbol not in index:
        matches = [name for name in index if name == symbol or name.endswith(f".{symbol}")]
        if len(matches) == 1:
            resolved = matches[0]
        else:
            return {"root": symbol, "nodes": [], "edges": []}

    nodes: list[dict] = []
    edges: list[dict] = []
    seen: set[str] = {resolved}
    queue: deque[tuple[str, int]] = deque([(resolved, 0)])

    while queue:
        current, current_depth = queue.popleft()
        if current_depth >= depth:
            continue

        if current not in index:
            continue

        _, _, calls = index[current]
        for called in calls:
            resolved_call = called
            if called not in index:
                matches = [name for name in index if name == called or name.endswith(f".{called}")]
                resolved_call = matches[0] if len(matches) == 1 else called

            if resolved_call not in seen:
                seen.add(resolved_call)
                if resolved_call in index:
                    rel_path, line, _ = index[resolved_call]
                    kind = "method" if "." in resolved_call else "function"
                else:
                    rel_path, line, kind = "", 0, "external"

                nodes.append({
                    "id": resolved_call,
                    "path": rel_path,
                    "line": line,
                    "kind": kind,
                    "degree": len(index.get(resolved_call, ("", 0, []))[2]),
                })

            edges.append({
                "source": current,
                "target": resolved_call,
                "relation": "calls",
            })

            if resolved_call in index and resolved_call not in seen:
                queue.append((resolved_call, current_depth + 1))

    return {"root": symbol, "nodes": nodes, "edges": edges}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd d:/pythonProject/agentCli/agentCli && python -m pytest tests/test_graph.py -v`

Expected: 7 PASS

- [ ] **Step 5: Commit**

```bash
git add src/agentcli/analysis/graph.py tests/test_graph.py
git commit -m "feat: add expand_call_node for BFS subtree expansion"
```

---

### Task 4: 实现 get_node_detail

**Files:**
- Modify: `src/agentcli/analysis/graph.py`

- [ ] **Step 1: 编写测试**

Append to `tests/test_graph.py`:

```python
from agentcli.analysis.graph import get_node_detail


def test_get_node_detail_returns_metadata(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        """
def setup() -> None:
    '''Initialize the application.'''
    pass

def main() -> None:
    setup()
""".strip(),
        encoding="utf-8",
    )

    result = get_node_detail(tmp_path, "main")

    assert result["symbol"] == "main"
    assert "app.py" in result["path"]
    assert result["kind"] == "function"
    assert "setup" in result["outgoing"]


def test_get_node_detail_unknown_symbol(tmp_path: Path) -> None:
    result = get_node_detail(tmp_path, "ghost")
    assert result["symbol"] == "ghost"
    assert result["path"] == ""
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd d:/pythonProject/agentCli/agentCli && python -m pytest tests/test_graph.py::test_get_node_detail_returns_metadata -v`

Expected: FAIL

- [ ] **Step 3: 实现 get_node_detail**

Append to `src/agentcli/analysis/graph.py`:

```python
def get_node_detail(repo_root: Path, symbol: str) -> dict:
    index = _build_definition_index(repo_root)

    resolved = symbol
    if symbol not in index:
        matches = [name for name in index if name == symbol or name.endswith(f".{symbol}")]
        if len(matches) == 1:
            resolved = matches[0]
        else:
            return {
                "symbol": symbol,
                "path": "",
                "line": 0,
                "kind": "unknown",
                "incoming": [],
                "outgoing": [],
                "docstring": None,
            }

    rel_path, line, calls = index[resolved]
    kind = "method" if "." in resolved else "function"

    incoming: list[str] = []
    for other_symbol, (_, _, other_calls) in index.items():
        if resolved in other_calls or any(
            c == resolved or c.endswith(f".{resolved}") for c in other_calls
        ):
            incoming.append(other_symbol)

    return {
        "symbol": resolved,
        "path": rel_path,
        "line": line,
        "kind": kind,
        "incoming": incoming,
        "outgoing": calls,
        "docstring": None,
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd d:/pythonProject/agentCli/agentCli && python -m pytest tests/test_graph.py -v`

Expected: 9 PASS

- [ ] **Step 5: Commit**

```bash
git add src/agentcli/analysis/graph.py tests/test_graph.py
git commit -m "feat: add get_node_detail for single-node metadata lookup"
```

---

### Task 5: 导出 graph 模块并注册到 __init__.py

**Files:**
- Modify: `src/agentcli/analysis/__init__.py`

- [ ] **Step 1: 添加 graph 函数到 __init__.py**

Edit `src/agentcli/analysis/__init__.py`: add import and __all__ entries:

```python
from agentcli.analysis.graph import build_skeleton_graph, expand_call_node, get_node_detail
```

And append to `__all__`:
```python
    "build_skeleton_graph",
    "expand_call_node",
    "get_node_detail",
```

- [ ] **Step 2: 验证导入**

Run: `cd d:/pythonProject/agentCli/agentCli && python -c "from agentcli.analysis import build_skeleton_graph, expand_call_node, get_node_detail; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/agentcli/analysis/__init__.py
git commit -m "feat: export graph functions from analysis package"
```

---

### Task 6: 添加 API 端点

**Files:**
- Modify: `src/agentcli/api/server.py`

- [ ] **Step 1: 更新 server.py 的 import 和 Schemas**

Add to imports at top of `server.py`:

```python
from agentcli.api.schemas import (
    # ... existing imports ...
    ExpandResponse,
    GraphEdge,
    GraphNode,
    NodeDetailResponse,
    SkeletonResponse,
)
from agentcli.analysis.graph import build_skeleton_graph, expand_call_node, get_node_detail
```

- [ ] **Step 2: 添加 /api/graph/skeleton 端点**

Insert before the tour endpoint in `server.py`:

```python
@app.get("/api/graph/skeleton", response_model=SkeletonResponse)
def get_graph_skeleton() -> SkeletonResponse:
    result = build_skeleton_graph(resolved_repo)
    return SkeletonResponse(
        nodes=[GraphNode(**n) for n in result["nodes"]],
        edges=[GraphEdge(**e) for e in result["edges"]],
        warning=result.get("warning"),
        skipped_files=result.get("skipped_files", []),
    )
```

- [ ] **Step 3: 添加 /api/graph/expand 端点**

```python
@app.get("/api/graph/expand", response_model=ExpandResponse)
def get_graph_expand(symbol: str, depth: int = 3) -> ExpandResponse:
    result = expand_call_node(resolved_repo, symbol, depth)
    return ExpandResponse(
        root=result["root"],
        nodes=[GraphNode(**n) for n in result["nodes"]],
        edges=[GraphEdge(**e) for e in result["edges"]],
    )
```

- [ ] **Step 4: 添加 /api/graph/node 端点**

```python
@app.get("/api/graph/node", response_model=NodeDetailResponse)
def get_graph_node(symbol: str) -> NodeDetailResponse:
    result = get_node_detail(resolved_repo, symbol)
    return NodeDetailResponse(**result)
```

- [ ] **Step 5: 编写 API 集成测试**

Append to `tests/test_api_server.py`:

```python
from fastapi.testclient import TestClient


def test_get_graph_skeleton_returns_nodes_and_edges(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        "def main():\n    helper()\n\ndef helper():\n    pass\n",
        encoding="utf-8",
    )
    app = create_app(tmp_path)
    client = TestClient(app)

    resp = client.get("/api/graph/skeleton")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["nodes"]) >= 2
    assert len(data["edges"]) >= 1


def test_get_graph_skeleton_empty_repo(tmp_path: Path) -> None:
    app = create_app(tmp_path)
    client = TestClient(app)

    resp = client.get("/api/graph/skeleton")

    assert resp.status_code == 200
    data = resp.json()
    assert data["warning"] == "no_python_files"


def test_get_graph_expand_returns_subtree(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        "def main():\n    return helper()\n\ndef helper():\n    return 'ok'\n",
        encoding="utf-8",
    )
    app = create_app(tmp_path)
    client = TestClient(app)

    resp = client.get("/api/graph/expand?symbol=main&depth=2")

    assert resp.status_code == 200
    data = resp.json()
    assert data["root"] == "main"
    assert any(n["id"] == "helper" for n in data["nodes"])


def test_get_graph_node_returns_detail(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "def main():\n    helper()\n\ndef helper():\n    pass\n",
        encoding="utf-8",
    )
    app = create_app(tmp_path)
    client = TestClient(app)

    resp = client.get("/api/graph/node?symbol=main")

    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "main"
    assert "helper" in data["outgoing"]
```

Note: also add `from pathlib import Path` at top if not already present.

- [ ] **Step 6: 运行 API 测试**

Run: `cd d:/pythonProject/agentCli/agentCli && python -m pytest tests/test_api_server.py -v -k "graph"`

Expected: 4 PASS

- [ ] **Step 7: Commit**

```bash
git add src/agentcli/api/server.py tests/test_api_server.py
git commit -m "feat: add /api/graph/* endpoints for call graph data"
```

---

### Task 7: 安装 Cytoscape.js 依赖

**Files:**
- Modify: `web/package.json`

- [ ] **Step 1: 安装 cytoscape 和 cytoscape-dagre**

Run: `cd d:/pythonProject/agentCli/agentCli/web && npm install cytoscape cytoscape-dagre`

- [ ] **Step 2: 安装类型定义**

Run: `cd d:/pythonProject/agentCli/agentCli/web && npm install --save-dev @types/cytoscape`

- [ ] **Step 3: 验证安装**

Run: `cd d:/pythonProject/agentCli/agentCli/web && node -e "require('cytoscape'); console.log('OK')"`

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add web/package.json web/package-lock.json
git commit -m "chore: add cytoscape and cytoscape-dagre dependencies"
```

---

### Task 8: 前端 — 图数据类型定义

**Files:**
- Create: `web/src/graph/types.ts`

- [ ] **Step 1: 定义前端类型**

```typescript
export type GraphNodeData = {
  id: string;
  path: string;
  line: number;
  kind: "function" | "method" | "class" | "external";
  degree: number;
};

export type GraphEdgeData = {
  source: string;
  target: string;
  relation: string;
};

export type SkeletonData = {
  nodes: GraphNodeData[];
  edges: GraphEdgeData[];
  warning?: string;
};

export type ExpandData = {
  root: string;
  nodes: GraphNodeData[];
  edges: GraphEdgeData[];
};

export type NodeDetailData = {
  symbol: string;
  path: string;
  line: number;
  kind: string;
  incoming: string[];
  outgoing: string[];
};
```

- [ ] **Step 2: 确认 TypeScript 编译**

Run: `cd d:/pythonProject/agentCli/agentCli/web && npx tsc --noEmit`

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add web/src/graph/types.ts
git commit -m "feat: add graph TypeScript types"
```

---

### Task 9: 前端 — API 客户端扩展

**Files:**
- Modify: `web/src/api/client.ts`

- [ ] **Step 1: 添加 graph API 函数**

Append to `web/src/api/client.ts`:

```typescript
import type { ExpandData, NodeDetailData, SkeletonData } from "../graph/types";

export async function fetchGraphSkeleton(): Promise<SkeletonData> {
  const response = await fetch("/api/graph/skeleton");
  return response.json();
}

export async function fetchGraphExpand(symbol: string, depth = 3): Promise<ExpandData> {
  const response = await fetch(
    `/api/graph/expand?symbol=${encodeURIComponent(symbol)}&depth=${depth}`,
  );
  return response.json();
}

export async function fetchGraphNode(symbol: string): Promise<NodeDetailData> {
  const response = await fetch(`/api/graph/node?symbol=${encodeURIComponent(symbol)}`);
  return response.json();
}
```

- [ ] **Step 2: 确认 TypeScript 编译**

Run: `cd d:/pythonProject/agentCli/agentCli/web && npx tsc --noEmit`

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add web/src/api/client.ts
git commit -m "feat: add graph API client functions"
```

---

### Task 10: 前端 — Cytoscape 样式定义

**Files:**
- Create: `web/src/graph/styles.ts`

- [ ] **Step 1: 定义节点和边的样式**

```typescript
import type { Stylesheet } from "cytoscape";

export const CALL_GRAPH_STYLES: Stylesheet[] = [
  {
    selector: "node",
    style: {
      "background-color": "#2d6da4",
      label: "data(id)",
      "font-size": "11px",
      "text-valign": "bottom",
      "text-halign": "center",
      color: "#ccc",
      "text-margin-y": 6,
      width: 14,
      height: 14,
      "border-width": 1,
      "border-color": "#1a3a5c",
      shape: "round-rectangle",
    },
  },
  {
    selector: "node[kind='function']",
    style: { "background-color": "#4a7d2d", "border-color": "#2d4a1a" },
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
    selector: "edge",
    style: {
      width: 1.5,
      "line-color": "#555",
      "target-arrow-color": "#555",
      "target-arrow-shape": "triangle",
      "curve-style": "bezier",
    },
  },
  {
    selector: "edge[relation='calls']",
    style: { "line-style": "solid" },
  },
];
```

- [ ] **Step 2: Commit**

```bash
git add web/src/graph/styles.ts
git commit -m "feat: add cytoscape graph styles"
```

---

### Task 11: 前端 — 交互处理器

**Files:**
- Create: `web/src/graph/interactions.ts`

- [ ] **Step 1: 定义交互处理函数**

```typescript
import type { Core, EventObject } from "cytoscape";

export type OpenFileHandler = (path: string, startLine?: number) => void;
export type ExpandHandler = (symbol: string) => void;

export function setupGraphInteractions(
  cy: Core,
  onOpenFile: OpenFileHandler,
  onExpand: ExpandHandler,
  onNodeSelect: (symbol: string) => void,
): void {
  cy.on("dbltap", "node", (evt: EventObject) => {
    const node = evt.target;
    const path = node.data("path") as string;
    const line = node.data("line") as number;
    if (path) {
      onOpenFile(path, line > 0 ? line : undefined);
    }
  });

  cy.on("cxttap", "node", (evt: EventObject) => {
    const node = evt.target;
    const symbol = node.data("id") as string;

    // Remove existing context menu
    const existing = document.querySelector(".cy-context-menu");
    if (existing) existing.remove();

    const menu = document.createElement("div");
    menu.className = "cy-context-menu";
    menu.style.cssText = `
      position: absolute;
      left: ${evt.originalEvent.clientX}px;
      top: ${evt.originalEvent.clientY}px;
      background: #1e1e2e;
      border: 1px solid #444;
      border-radius: 6px;
      padding: 4px 0;
      z-index: 10000;
      min-width: 180px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    `;

    const items = [
      {
        label: "Open in Editor",
        action: () => {
          const p = node.data("path") as string;
          const l = node.data("line") as number;
          if (p) onOpenFile(p, l > 0 ? l : undefined);
        },
      },
      {
        label: "Expand",
        action: () => onExpand(symbol),
      },
    ];

    for (const item of items) {
      const el = document.createElement("div");
      el.textContent = item.label;
      el.style.cssText =
        "padding:6px 16px;cursor:pointer;font-size:12px;color:#ccc;";
      el.onmouseenter = () => (el.style.background = "#333");
      el.onmouseleave = () => (el.style.background = "transparent");
      el.onclick = () => {
        item.action();
        menu.remove();
      };
      menu.appendChild(el);
    }

    document.body.appendChild(menu);

    const closeMenu = () => {
      menu.remove();
      document.removeEventListener("click", closeMenu);
    };
    setTimeout(() => document.addEventListener("click", closeMenu), 0);
  });

  cy.on("tap", "node", (evt: EventObject) => {
    const node = evt.target;
    onNodeSelect(node.data("id") as string);
  });
}
```

- [ ] **Step 2: Commit**

```bash
git add web/src/graph/interactions.ts
git commit -m "feat: add graph interaction handlers (dblclick, right-click menu, tap)"
```

---

### Task 12: 前端 — useCallGraph Hook

**Files:**
- Create: `web/src/graph/useCallGraph.ts`

- [ ] **Step 1: 实现图状态管理 hook**

```typescript
import { useCallback, useEffect, useRef, useState } from "react";
import cytoscape, { Core } from "cytoscape";
import dagre from "cytoscape-dagre";
import { fetchGraphExpand, fetchGraphSkeleton } from "../api/client";
import { CALL_GRAPH_STYLES } from "./styles";
import { setupGraphInteractions } from "./interactions";
import type { GraphEdgeData, GraphNodeData, NodeDetailData } from "./types";

cytoscape.use(dagre);

export type CallGraphState = {
  isLoading: boolean;
  warning: string | null;
  nodeCount: number;
  edgeCount: number;
  selectedNode: NodeDetailData | null;
  error: string | null;
};

export function useCallGraph(
  containerRef: React.RefObject<HTMLDivElement | null>,
  onOpenFile: (path: string, startLine?: number) => void,
) {
  const cyRef = useRef<Core | null>(null);
  const [state, setState] = useState<CallGraphState>({
    isLoading: true,
    warning: null,
    nodeCount: 0,
    edgeCount: 0,
    selectedNode: null,
    error: null,
  });

  const loadSkeleton = useCallback(async () => {
    setState((s) => ({ ...s, isLoading: true, error: null }));
    try {
      const data = await fetchGraphSkeleton();
      if (!cyRef.current) return;

      const cy = cyRef.current;
      cy.elements().remove();

      const elements: cytoscape.ElementDefinition[] = [
        ...data.nodes.map((n: GraphNodeData) => ({
          data: { id: n.id, path: n.path, line: n.line, kind: n.kind, degree: n.degree },
        })),
        ...data.edges.map((e: GraphEdgeData) => ({
          data: { source: e.source, target: e.target, relation: e.relation },
        })),
      ];

      cy.add(elements);

      cy.layout({
        name: "dagre",
        rankDir: "TB",
        spacingFactor: 1.3,
        animate: true,
        animationDuration: 400,
      } as cytoscape.LayoutOptions).run();

      setState((s) => ({
        ...s,
        isLoading: false,
        warning: data.warning || null,
        nodeCount: data.nodes.length,
        edgeCount: data.edges.length,
      }));
    } catch (err) {
      setState((s) => ({
        ...s,
        isLoading: false,
        error: err instanceof Error ? err.message : "Failed to load graph",
      }));
    }
  }, []);

  const expandNode = useCallback(async (symbol: string) => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);
    try {
      const response = await fetch(
        `/api/graph/expand?symbol=${encodeURIComponent(symbol)}&depth=3`,
        { signal: controller.signal },
      );
      clearTimeout(timeoutId);
      const data = await response.json();
      if (!cyRef.current) return;

      const cy = cyRef.current;

      for (const n of data.nodes) {
        if (cy.getElementById(n.id).length === 0) {
          cy.add({
            data: { id: n.id, path: n.path, line: n.line, kind: n.kind, degree: n.degree },
          });
        }
      }
      for (const e of data.edges) {
        const edgeId = `${e.source}->${e.target}`;
        if (cy.getElementById(edgeId).length === 0) {
          cy.add({
            data: { id: edgeId, source: e.source, target: e.target, relation: e.relation },
          });
        }
      }

      cy.layout({
        name: "dagre",
        rankDir: "TB",
        spacingFactor: 1.3,
        animate: true,
        animationDuration: 300,
      } as cytoscape.LayoutOptions).run();

      setState((s) => ({
        ...s,
        nodeCount: cy.nodes().length,
        edgeCount: cy.edges().length,
      }));
    } catch (err) {
      clearTimeout(timeoutId);
      if (err instanceof DOMException && err.name === "AbortError") {
        setState((s) => ({ ...s, error: "Expand timeout — please retry" }));
      } else {
        setState((s) => ({
          ...s,
          error: err instanceof Error ? err.message : "Failed to expand node",
        }));
      }
    }
  }, []);

  const selectNode = useCallback((symbol: string) => {
    // The interactions module handles detail fetching; this updates selected state
    setState((s) => ({ ...s, selectedNode: null }));
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;

    const cy = cytoscape({
      container: containerRef.current,
      style: CALL_GRAPH_STYLES,
      wheelSensitivity: 0.3,
      minZoom: 0.2,
      maxZoom: 3,
    });

    cyRef.current = cy;
    setupGraphInteractions(cy, onOpenFile, expandNode, selectNode);
    loadSkeleton();

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [containerRef, onOpenFile, expandNode, selectNode, loadSkeleton]);

  return { state, loadSkeleton, expandNode };
}
```

- [ ] **Step 2: 确认 TypeScript 编译**

Run: `cd d:/pythonProject/agentCli/agentCli/web && npx tsc --noEmit`

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add web/src/graph/useCallGraph.ts
git commit -m "feat: add useCallGraph hook for graph state management"
```

---

### Task 13: 前端 — 重写 CallGraph.tsx

**Files:**
- Modify: `web/src/components/CallGraph.tsx`

- [ ] **Step 1: 完整重写 CallGraph 组件**

Replace entire contents of `web/src/components/CallGraph.tsx`:

```typescript
import { useRef } from "react";
import { useCallGraph } from "../graph/useCallGraph";
import type { GraphNodeData, GraphEdgeData } from "../graph/types";

type CallGraphProps = {
  onOpenFile: (path: string, startLine?: number) => void;
};

export function CallGraph({ onOpenFile }: CallGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { state, loadSkeleton, expandNode } = useCallGraph(containerRef, onOpenFile);

  return (
    <div className="panel" style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <h3 style={{ margin: 0 }}>Call Graph</h3>
        <div style={{ display: "flex", gap: 4 }}>
          <button
            className="toolbar-btn"
            title="Refresh"
            onClick={loadSkeleton}
            disabled={state.isLoading}
          >
            ↻
          </button>
          <span style={{ fontSize: 11, color: "var(--muted)" }}>
            {state.nodeCount} nodes / {state.edgeCount} edges
          </span>
        </div>
      </div>

      {state.warning && (
        <div style={{ padding: "6px 10px", background: "#3a3a1a", borderRadius: 4, fontSize: 12, marginBottom: 8 }}>
          {state.warning}
        </div>
      )}

      {state.error && (
        <div style={{ padding: "6px 10px", background: "#3a1a1a", borderRadius: 4, fontSize: 12, marginBottom: 8 }}>
          {state.error}
          <button onClick={loadSkeleton} style={{ marginLeft: 8, fontSize: 11 }}>Retry</button>
        </div>
      )}

      {state.isLoading && (
        <div style={{ padding: 12, color: "var(--muted)", fontSize: 12 }}>Loading graph...</div>
      )}

      <div
        ref={containerRef}
        style={{
          flex: 1,
          minHeight: 200,
          background: "#0d0d1a",
          borderRadius: 6,
          border: "1px solid #2a2a3a",
        }}
      />

      <div style={{ marginTop: 6, fontSize: 10, color: "var(--muted)" }}>
        Double-click node → open in editor | Right-click → menu | Tap → select
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 确认 TypeScript 编译**

Run: `cd d:/pythonProject/agentCli/agentCli/web && npx tsc --noEmit`

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add web/src/components/CallGraph.tsx
git commit -m "feat: rewrite CallGraph with Cytoscape.js interactive graph"
```

---

### Task 14: 前端 — App.tsx 连线

**Files:**
- Modify: `web/src/App.tsx`

- [ ] **Step 1: 更新 CallGraph 调用**

In `App.tsx`, find the `<CallGraph events={events} />` line (around line 271) and replace with:

```tsx
<CallGraph onOpenFile={openFile} />
```

- [ ] **Step 2: 确认 TypeScript 编译**

Run: `cd d:/pythonProject/agentCli/agentCli/web && npx tsc --noEmit`

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add web/src/App.tsx
git commit -m "feat: wire CallGraph with openFile callback"
```

---

### Task 15: 构建验证 & 端到端测试

**Files:**
- None (verification only)

- [ ] **Step 1: 运行全部后端测试**

Run: `cd d:/pythonProject/agentCli/agentCli && python -m pytest tests/ -v`

Expected: All tests pass (existing tests must not regress)

- [ ] **Step 2: 构建前端**

Run: `cd d:/pythonProject/agentCli/agentCli/web && npm run build`

Expected: Build succeeds with no errors

- [ ] **Step 3: 启动服务并手动验证**

Run: `cd d:/pythonProject/agentCli/agentCli && python -m agentcli web --repo .`

Then open `http://127.0.0.1:8765`, verify:
- Right inspector "分析" tab shows the Call Graph panel
- Graph loads and renders nodes for current project's Python files
- Double-clicking a node opens the file in the Monaco editor
- Right-click shows context menu

- [ ] **Step 4: Commit (if any fixes made during verification)**

```bash
git add -A
git commit -m "fix: address issues found during end-to-end verification"
```

---

### Task 16: 添加 .superpowers 到 .gitignore

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: 追加 .superpowers/ 到 .gitignore**

Edit `.gitignore`, append line:

```
.superpowers/
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: add .superpowers/ to gitignore"
```
