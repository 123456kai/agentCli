# 代码研读：叙事型主线引导阅读 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 CallGraph 从静态调用图升级为对话引导式代码研读体验——用户选主线、逐节点读源码+AI 解释、可追问、确认后推进。

**Architecture:** 后端新增 storyline.py（AST 路径发现 + LLM 叙事生成）和 cache.py（解释缓存），前端新增 CodeReadingPanel（发现/阅读/完成三态切换），复用现有 Monaco 编辑器和调用图组件。

**Tech Stack:** Python (FastAPI, AST), TypeScript (React 18, Monaco, Cytoscape), LLM (DeepSeek adapter)

---

## 文件分工

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/agentcli/analysis/cache.py` | 新建 | JSON 文件缓存，以 `(path, hash, range)` 为 key |
| `src/agentcli/analysis/storyline.py` | 新建 | 主线骨架生成 + LLM 叙事生成 |
| `src/agentcli/api/schemas.py` | 修改 | 新增 Storyline 相关 Pydantic schema |
| `src/agentcli/api/server.py` | 修改 | 新增 5 个 API 端点 |
| `tests/test_cache.py` | 新建 | 缓存模块测试 |
| `tests/test_storyline.py` | 新建 | 主线生成测试 |
| `tests/test_storyline_api.py` | 新建 | API 端点测试 |
| `web/src/components/coderead/types.ts` | 新建 | TypeScript 类型定义 |
| `web/src/components/coderead/CodeReadingPanel.tsx` | 新建 | 状态机容器组件 |
| `web/src/components/coderead/StorylineDiscovery.tsx` | 新建 | 发现页 |
| `web/src/components/coderead/StorylineReader.tsx` | 新建 | 阅读页（70/30 分栏） |
| `web/src/components/coderead/NarrativeCards.tsx` | 新建 | AI 解释卡片 |
| `web/src/components/coderead/NodeQA.tsx` | 新建 | 追问输入 |
| `web/src/components/coderead/StorylineComplete.tsx` | 新建 | 完成页 |
| `web/src/api/client.ts` | 修改 | 新增 API 客户端函数 |
| `web/src/App.tsx` | 修改 | 新增"研读"Tab |

---

### Task 1: 缓存模块 `cache.py`

**Files:**
- Create: `src/agentcli/analysis/cache.py`
- Create: `tests/test_cache.py`

- [ ] **Step 1: 写缓存模块的失败测试**

```python
# tests/test_cache.py
import json
from pathlib import Path
import tempfile

from agentcli.analysis.cache import NarrativeCache


def test_cache_set_and_get():
    cache_dir = Path(tempfile.mkdtemp())
    cache = NarrativeCache(cache_dir)

    cache.set("src/a.py:abc123:10-20", {"summary": "does X", "design_notes": "because Y", "warnings": None})

    entry = cache.get("src/a.py:abc123:10-20")
    assert entry is not None
    assert entry["summary"] == "does X"
    assert entry["design_notes"] == "because Y"
    assert entry["warnings"] is None


def test_cache_miss_returns_none():
    cache_dir = Path(tempfile.mkdtemp())
    cache = NarrativeCache(cache_dir)

    assert cache.get("nonexistent:hash:1-5") is None


def test_cache_overwrite():
    cache_dir = Path(tempfile.mkdtemp())
    cache = NarrativeCache(cache_dir)

    cache.set("key:hash:1-5", {"summary": "old"})
    cache.set("key:hash:1-5", {"summary": "new"})

    assert cache.get("key:hash:1-5")["summary"] == "new"


def test_cache_file_hash_changes_invalidates():
    cache_dir = Path(tempfile.mkdtemp())
    cache = NarrativeCache(cache_dir)

    cache.set("src/a.py:oldhash:10-20", {"summary": "stale"})
    # 用新 hash 查询同一文件位置，应 miss
    assert cache.get("src/a.py:newhash:10-20") is None


def test_make_cache_key():
    from agentcli.analysis.cache import make_cache_key

    key = make_cache_key("src/a.py", "abc123def", 42, 68)
    assert key == "src/a.py:abc123def:42-68"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd d:/pythonProject/agentCli/agentCli && python -m pytest tests/test_cache.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'agentcli.analysis.cache'`

- [ ] **Step 3: 实现缓存模块最小代码**

```python
# src/agentcli/analysis/cache.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def make_cache_key(file_path: str, content_hash: str, line_start: int, line_end: int) -> str:
    return f"{file_path}:{content_hash}:{line_start}-{line_end}"


class NarrativeCache:
    """JSON-file-backed cache for AI-generated code narratives.

    Key: ``file_path:content_hash:line_start-line_end``
    Value: ``{"summary": str, "design_notes": str, "warnings": str | None, "generated_at": str}``
    """

    def __init__(self, cache_dir: Path) -> None:
        self._dir = cache_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._store_path = self._dir / "narratives.json"
        self._data: dict[str, dict[str, object]] = self._load()

    def _load(self) -> dict[str, dict[str, object]]:
        if self._store_path.exists():
            try:
                return json.loads(self._store_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save(self) -> None:
        self._store_path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get(self, key: str) -> dict[str, object] | None:
        return self._data.get(key)

    def set(self, key: str, value: dict[str, object]) -> None:
        self._data[key] = value
        self._save()

    def get_by_prefix(self, file_path: str, content_hash: str) -> list[tuple[str, dict[str, object]]]:
        prefix = f"{file_path}:{content_hash}:"
        return [(k, v) for k, v in self._data.items() if k.startswith(prefix)]
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd d:/pythonProject/agentCli/agentCli && python -m pytest tests/test_cache.py -v
```
Expected: PASS (5 tests)

- [ ] **Step 5: 提交**

```bash
cd d:/pythonProject/agentCli/agentCli && git add src/agentcli/analysis/cache.py tests/test_cache.py && git commit -m "feat: add NarrativeCache for AI explanation caching"
```

---

### Task 2: 主线骨架生成（AST 路径发现）

**Files:**
- Create: `src/agentcli/analysis/storyline.py`（骨架部分）
- Create: `tests/test_storyline.py`

- [ ] **Step 1: 写骨架生成的失败测试**

```python
# tests/test_storyline.py
import tempfile
from pathlib import Path

from agentcli.analysis.storyline import (
    StorylineNode,
    discover_storylines,
    resolve_storyline_nodes,
)
from agentcli.analysis.graph import build_graph_index


def _make_repo(files: dict[str, str]) -> Path:
    root = Path(tempfile.mkdtemp())
    for rel, content in files.items():
        abs_path = root / rel
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(content, encoding="utf-8")
    return root


SAMPLE_FILES = {
    "src/main.py": '''
from src.auth import login

def main():
    user = login("test", "pass")
    print(user)

if __name__ == "__main__":
    main()
''',
    "src/auth.py": '''
from src.db import find_user

def login(username: str, password: str):
    user = find_user(username)
    if user and user.get("password") == password:
        return user
    return None
''',
    "src/db.py": '''
_users = [{"username": "admin", "password": "admin123"}]

def find_user(username: str):
    for u in _users:
        if u["username"] == username:
            return u
    return None
''',
}


def test_discover_storylines_finds_entry_based_paths():
    repo_root = _make_repo(SAMPLE_FILES)
    index = build_graph_index(repo_root)

    storylines = discover_storylines(repo_root, index)

    assert len(storylines) >= 1
    auth_storyline = [s for s in storylines if "login" in s.title.lower() or "auth" in s.title.lower()]
    assert len(auth_storyline) >= 1


def test_resolve_storyline_nodes_maps_to_source():
    repo_root = _make_repo(SAMPLE_FILES)
    index = build_graph_index(repo_root)

    storyline = discover_storylines(repo_root, index)[0]
    resolved = resolve_storyline_nodes(repo_root, index, storyline)

    for node in resolved:
        assert isinstance(node, StorylineNode)
        assert node.file_path
        assert node.line_start > 0
        assert node.graph_node_id
        assert node.order >= 0


def test_discover_storylines_skips_too_short_paths():
    repo_root = _make_repo(SAMPLE_FILES)
    index = build_graph_index(repo_root)

    storylines = discover_storylines(repo_root, index, min_nodes=3, max_nodes=10)

    for s in storylines:
        assert s.node_count >= 3
        assert s.node_count <= 10
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd d:/pythonProject/agentCli/agentCli && python -m pytest tests/test_storyline.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'agentcli.analysis.storyline'`

- [ ] **Step 3: 实现骨架生成**

```python
# src/agentcli/analysis/storyline.py
from __future__ import annotations

import json
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
    """Find entry-point nodes: CLI main, FastAPI routes, __main__ files."""
    nodes_by_id = index["nodes_by_id"]
    entries: list[str] = []
    for node_id, node in nodes_by_id.items():
        label = str(node["label"])
        path = str(node["path"])
        if label in ("main", "cli", "create_app", "app"):
            entries.append(node_id)
        elif "__main__" in path:
            entries.append(node_id)
        elif path.endswith("server.py") and label == "create_app":
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
        first_label = str(nodes_data[0]["label"])
        title = f"{first_label} 调用链"
        description = " → ".join(str(n["label"]) for n in nodes_data[:5])
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
    """Fill in line_end for each node by reading the source file.

    line_end is estimated as line_start for simplicity in the skeleton phase.
    The AI narrative phase reads the actual function body and determines the real range.
    """
    nodes_by_id = index["nodes_by_id"]
    for node in storyline.nodes:
        graph_node = nodes_by_id.get(node.graph_node_id)
        if graph_node:
            node.line_start = int(graph_node["line"])
            node.line_end = int(graph_node["line"])
    return storyline.nodes
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd d:/pythonProject/agentCli/agentCli && python -m pytest tests/test_storyline.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 5: 提交**

```bash
cd d:/pythonProject/agentCli/agentCli && git add src/agentcli/analysis/storyline.py tests/test_storyline.py && git commit -m "feat: add storyline skeleton discovery from call graph"
```

---

### Task 3: AI 叙事生成（LLM 节点解释）

**Files:**
- Modify: `src/agentcli/analysis/storyline.py`（新增 LLM 叙事函数）
- Modify: `src/agentcli/analysis/cache.py`（扩展 `get_by_prefix` 已实现）

- [ ] **Step 1: 写叙事生成的测试**

```python
# 追加到 tests/test_storyline.py

from agentcli.analysis.storyline import (
    generate_node_narrative,
    NodeNarrative,
)
from agentcli.analysis.cache import NarrativeCache


def _adapter_factory_mock():
    class MockAdapter:
        async def chat(self, messages, **kwargs):
            return json.dumps({
                "summary": "从请求头提取 Bearer Token 并验证 JWT",
                "design_notes": "使用中间件模式解耦认证和业务逻辑",
                "warnings": "HS256 是对称加密，生产建议 RS256",
            })
    return MockAdapter()


def test_generate_node_narrative_returns_structured_result():
    repo_root = _make_repo(SAMPLE_FILES)
    index = build_graph_index(repo_root)
    import tempfile
    cache_dir = Path(tempfile.mkdtemp())
    cache = NarrativeCache(cache_dir)

    node_id = next(nid for nid, n in index["nodes_by_id"].items() if str(n["label"]) == "login")

    # 用同步方式测试——实际函数是异步的
    import asyncio
    narrative = asyncio.run(
        generate_node_narrative(
            repo_root=repo_root,
            node_id=node_id,
            index=index,
            cache=cache,
            adapter_factory=_adapter_factory_mock,
        )
    )

    assert isinstance(narrative, NodeNarrative)
    assert narrative.summary
    assert narrative.design_notes
    assert narrative.warnings
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd d:/pythonProject/agentCli/agentCli && python -m pytest tests/test_storyline.py::test_generate_node_narrative_returns_structured_result -v
```
Expected: FAIL — `ImportError: cannot import name 'generate_node_narrative'`

- [ ] **Step 3: 实现叙事生成**

```python
# 追加到 src/agentcli/analysis/storyline.py

import asyncio
from dataclasses import dataclass


@dataclass
class NodeNarrative:
    summary: str
    design_notes: str
    warnings: str | None


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
    try:
        return hashlib.sha256(file_path.read_bytes()).hexdigest()[:16]
    except OSError:
        return "unknown"


def _read_node_source(repo_root: Path, node: dict[str, object]) -> str:
    file_path = repo_root / str(node["path"])
    line_start = int(node["line"])
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
        # 读从 line_start 开始的 50 行（覆盖大多数函数）
        start_idx = max(0, line_start - 1)
        end_idx = min(len(lines), start_idx + 50)
        return "\n".join(lines[start_idx:end_idx])
    except OSError:
        return ""


async def generate_node_narrative(
    repo_root: Path,
    node_id: str,
    index: GraphIndex,
    cache: "NarrativeCache | None" = None,
    adapter_factory=None,
) -> NodeNarrative:
    """Generate AI explanation for a single graph node. Uses cache if available."""
    from agentcli.analysis.cache import NarrativeCache, make_cache_key

    nodes_by_id = index["nodes_by_id"]
    node = nodes_by_id.get(node_id)
    if not node:
        return NodeNarrative(summary="(节点不存在)", design_notes="", warnings=None)

    file_path = repo_root / str(node["path"])
    if file_path.exists():
        content_hash = _file_content_hash(file_path)
    else:
        content_hash = "external"

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
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd d:/pythonProject/agentCli/agentCli && python -m pytest tests/test_storyline.py::test_generate_node_narrative_returns_structured_result -v
```
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd d:/pythonProject/agentCli/agentCli && git add src/agentcli/analysis/storyline.py tests/test_storyline.py && git commit -m "feat: add AI narrative generation for storyline nodes"
```

---

### Task 4: API 数据模型扩展

**Files:**
- Modify: `src/agentcli/api/schemas.py`

- [ ] **Step 1: 扩展 schemas.py**

在现有 schema 类后面追加：

```python
# 新增到 src/agentcli/api/schemas.py

class StorylineNodeSchema(BaseModel):
    order: int
    title: str
    file_path: str
    line_start: int
    line_end: int
    graph_node_id: str
    summary: str | None = None
    design_notes: str | None = None
    warnings: str | None = None


class StorylineSchema(BaseModel):
    id: str
    title: str
    description: str
    nodes: list[StorylineNodeSchema] = []
    node_count: int = 0
    estimated_minutes: int = 1
    file_count: int = 0


class StorylineListResponse(BaseModel):
    storylines: list[StorylineSchema]


class StorylineDetailResponse(BaseModel):
    """主线详情，节点不含叙事内容（叙事按需加载）"""
    id: str
    title: str
    description: str
    nodes: list[StorylineNodeSchema]
    node_count: int
    estimated_minutes: int
    file_count: int


class StorylineNodeResponse(BaseModel):
    node: StorylineNodeSchema
    source_code: str
    narrative: dict[str, str | None] | None  # {summary, design_notes, warnings} | null


class StorylineGenerateRequest(BaseModel):
    description: str


class StorylineGenerateResponse(BaseModel):
    storyline: StorylineSchema
    status: str  # "ready" | "generating"


class NodeAskRequest(BaseModel):
    question: str
    history: list[dict[str, str]] = []


class NodeAskResponse(BaseModel):
    answer: str
    source_refs: list[dict[str, str]] = []
```

- [ ] **Step 2: 运行类型检查确认无语法错误**

```bash
cd d:/pythonProject/agentCli/agentCli && python -c "from agentcli.api.schemas import StorylineSchema, StorylineListResponse, StorylineNodeResponse; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: 提交**

```bash
cd d:/pythonProject/agentCli/agentCli && git add src/agentcli/api/schemas.py && git commit -m "feat: add storyline Pydantic schemas"
```

---

### Task 5: API 端点

**Files:**
- Modify: `src/agentcli/api/server.py`
- Create: `tests/test_storyline_api.py`

- [ ] **Step 1: 写 API 端点测试**

```python
# tests/test_storyline_api.py
from fastapi.testclient import TestClient

from agentcli.api.server import create_app
from pathlib import Path
import tempfile


def _sample_repo() -> Path:
    root = Path(tempfile.mkdtemp())
    (root / "src").mkdir(parents=True)
    (root / "src" / "__init__.py").write_text("")
    (root / "src" / "main.py").write_text('''
from src.auth import login

def main():
    user = login("test", "pass")
    print(user)
''')
    (root / "src" / "auth.py").write_text('''
from src.db import find_user

def login(username: str, password: str) -> dict | None:
    user = find_user(username)
    if user and user["password"] == password:
        return user
    return None
''')
    return root


def test_get_storylines_returns_list():
    repo = _sample_repo()
    app = create_app(repo)
    client = TestClient(app)

    resp = client.get("/api/storylines")
    assert resp.status_code == 200
    data = resp.json()
    assert "storylines" in data
    assert isinstance(data["storylines"], list)


def test_get_storyline_detail():
    repo = _sample_repo()
    app = create_app(repo)
    client = TestClient(app)

    # 先获取主线列表
    list_resp = client.get("/api/storylines")
    storylines = list_resp.json()["storylines"]
    if not storylines:
        return  # 没有足够节点生成主线
    sid = storylines[0]["id"]

    resp = client.get(f"/api/storylines/{sid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == sid
    assert len(data["nodes"]) > 0


def test_get_storyline_node():
    repo = _sample_repo()
    app = create_app(repo)
    client = TestClient(app)

    list_resp = client.get("/api/storylines")
    storylines = list_resp.json()["storylines"]
    if not storylines:
        return
    sid = storylines[0]["id"]

    detail = client.get(f"/api/storylines/{sid}")
    nodes = detail.json()["nodes"]
    nid = nodes[0]["graph_node_id"]

    resp = client.get(f"/api/storylines/{sid}/nodes/{nid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["node"]["graph_node_id"] == nid
    assert "source_code" in data


def test_storyline_node_404_for_bad_storyline():
    repo = _sample_repo()
    app = create_app(repo)
    client = TestClient(app)

    resp = client.get("/api/storylines/nonexistentid")
    assert resp.status_code == 404
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd d:/pythonProject/agentCli/agentCli && python -m pytest tests/test_storyline_api.py::test_get_storylines_returns_list -v
```
Expected: FAIL — 端点尚未添加

- [ ] **Step 3: 在 server.py 中添加端点**

在 `create_app` 函数内的 `get_graph_node` 后面追加：

```python
    # ---- Storyline endpoints ----

    from agentcli.analysis.storyline import (
        discover_storylines,
        generate_node_narrative,
        NodeNarrative,
    )
    from agentcli.analysis.cache import NarrativeCache

    _narrative_cache = NarrativeCache(resolved_repo / ".agentcli" / "storyline-cache")

    def _storylines_from_index(index: dict[str, object]) -> list[dict[str, object]]:
        raw = discover_storylines(resolved_repo, index)
        result: list[dict[str, object]] = []
        for s in raw:
            result.append({
                "id": s.id,
                "title": s.title,
                "description": s.description,
                "nodes": [
                    {
                        "order": n.order,
                        "title": n.title,
                        "file_path": n.file_path,
                        "line_start": n.line_start,
                        "line_end": n.line_end,
                        "graph_node_id": n.graph_node_id,
                        "summary": n.summary,
                        "design_notes": n.design_notes,
                        "warnings": n.warnings,
                    }
                    for n in s.nodes
                ],
                "node_count": s.node_count,
                "estimated_minutes": s.estimated_minutes,
                "file_count": s.file_count,
            })
        return result

    @app.get("/api/storylines", response_model=StorylineListResponse)
    def list_storylines() -> StorylineListResponse:
        index = _get_graph_index()
        raw = _storylines_from_index(index)
        return StorylineListResponse(
            storylines=[StorylineSchema(**s) for s in raw]
        )

    @app.get("/api/storylines/{storyline_id}", response_model=StorylineDetailResponse)
    def get_storyline(storyline_id: str) -> StorylineDetailResponse:
        index = _get_graph_index()
        raw_list = _storylines_from_index(index)
        match = next((s for s in raw_list if s["id"] == storyline_id), None)
        if not match:
            raise HTTPException(status_code=404, detail="storyline not found")
        return StorylineDetailResponse(**match)

    @app.get("/api/storylines/{storyline_id}/nodes/{node_id}", response_model=StorylineNodeResponse)
    def get_storyline_node(storyline_id: str, node_id: str) -> StorylineNodeResponse:
        index = _get_graph_index()
        raw_list = _storylines_from_index(index)
        match = next((s for s in raw_list if s["id"] == storyline_id), None)
        if not match:
            raise HTTPException(status_code=404, detail="storyline not found")

        node_match = next((n for n in match["nodes"] if n["graph_node_id"] == node_id), None)
        if not node_match:
            raise HTTPException(status_code=404, detail="node not found in storyline")

        nodes_by_id = index["nodes_by_id"]
        graph_node = nodes_by_id.get(node_id)

        source_code = ""
        if graph_node:
            file_path = resolved_repo / str(graph_node["path"])
            if file_path.exists():
                try:
                    lines = file_path.read_text(encoding="utf-8").splitlines()
                    start = max(0, int(graph_node["line"]) - 1)
                    end = min(len(lines), start + 50)
                    source_code = "\n".join(lines[start:end])
                except OSError:
                    source_code = f"# Cannot read: {graph_node['path']}"

        # Check cache for narrative
        narrative: dict[str, str | None] | None = None
        if graph_node:
            from agentcli.analysis.cache import make_cache_key
            from agentcli.analysis.storyline import _file_content_hash
            fpath = resolved_repo / str(graph_node["path"])
            content_hash = _file_content_hash(fpath) if fpath.exists() else "external"
            cache_key = make_cache_key(str(graph_node["path"]), content_hash, int(graph_node["line"]), int(graph_node["line"]))
            cached = _narrative_cache.get(cache_key)
            if cached:
                narrative = {
                    "summary": str(cached.get("summary", "")),
                    "design_notes": str(cached.get("design_notes", "")),
                    "warnings": cached.get("warnings") if cached.get("warnings") else None,
                }

        return StorylineNodeResponse(
            node=StorylineNodeSchema(**node_match),
            source_code=source_code,
            narrative=narrative,
        )

    @app.post("/api/storylines/generate", response_model=StorylineGenerateResponse)
    def generate_storyline(request: StorylineGenerateRequest) -> StorylineGenerateResponse:
        # 自定义主线生成：先用现有骨架方案返回占位结果
        # LLM 驱动的自定义路径后续迭代增强
        index = _get_graph_index()
        raw_list = _storylines_from_index(index)
        # 返回第一条推荐主线作为降级
        if raw_list:
            first = raw_list[0]
            return StorylineGenerateResponse(
                storyline=StorylineSchema(**first),
                status="ready",
            )
        raise HTTPException(status_code=400, detail="no storylines available")

    @app.post("/api/storylines/{storyline_id}/nodes/{node_id}/ask", response_model=NodeAskResponse)
    def ask_node(storyline_id: str, node_id: str, request: NodeAskRequest) -> NodeAskResponse:
        index = _get_graph_index()
        nodes_by_id = index["nodes_by_id"]
        node = nodes_by_id.get(node_id)
        if not node:
            raise HTTPException(status_code=404, detail="node not found")

        code_snippet = _read_node_source(resolved_repo, node)  # 复用 storyline._read_node_source
        context = f"当前代码:\n```python\n{code_snippet}\n```\n\n用户问题: {request.question}"

        try:
            runtime = _build_runtime(resolved_repo)
            factory = adapter_factory or (lambda: _default_adapter_factory(runtime))
            adapter = factory()
            answer = adapter.chat_sync(context)
        except Exception:
            answer = "AI 问答暂不可用，请稍后重试。"

        return NodeAskResponse(answer=answer, source_refs=[])


def _read_node_source(repo_root: Path, node: dict[str, object]) -> str:
    """Read source code around a graph node's line."""
    file_path = repo_root / str(node["path"])
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
        start = max(0, int(node["line"]) - 1)
        end = min(len(lines), start + 50)
        return "\n".join(lines[start:end])
    except OSError:
        return ""
```

- [ ] **Step 4: 运行全部测试**

```bash
cd d:/pythonProject/agentCli/agentCli && python -m pytest tests/test_storyline_api.py -v
```
Expected: PASS (4 tests)

- [ ] **Step 5: 提交**

```bash
cd d:/pythonProject/agentCli/agentCli && git add src/agentcli/api/server.py tests/test_storyline_api.py && git commit -m "feat: add storyline API endpoints"
```

---

### Task 6: 前端类型和 API 客户端

**Files:**
- Create: `web/src/components/coderead/types.ts`
- Modify: `web/src/api/client.ts`

- [ ] **Step 1: 创建 TypeScript 类型**

```typescript
// web/src/components/coderead/types.ts

export type StorylineNode = {
  order: number;
  title: string;
  file_path: string;
  line_start: number;
  line_end: number;
  graph_node_id: string;
  summary: string | null;
  design_notes: string | null;
  warnings: string | null;
};

export type Storyline = {
  id: string;
  title: string;
  description: string;
  nodes: StorylineNode[];
  node_count: number;
  estimated_minutes: number;
  file_count: number;
};

export type StorylineListResponse = {
  storylines: Storyline[];
};

export type StorylineDetailResponse = Storyline;

export type StorylineNodeResponse = {
  node: StorylineNode;
  source_code: string;
  narrative: {
    summary: string;
    design_notes: string;
    warnings: string | null;
  } | null;
};

export type StorylineGenerateResponse = {
  storyline: Storyline;
  status: "ready" | "generating";
};

export type NodeAskResponse = {
  answer: string;
  source_refs: { path: string; line: number }[];
};

export type ReadingState = "discovery" | "reading" | "complete";
```

- [ ] **Step 2: 在 API 客户端中添加函数**

```typescript
// 追加到 web/src/api/client.ts

import type {
  StorylineListResponse,
  StorylineDetailResponse,
  StorylineNodeResponse,
  StorylineGenerateResponse,
  NodeAskResponse,
} from "../components/coderead/types";

export async function fetchStorylines(signal?: AbortSignal): Promise<StorylineListResponse> {
  const response = await fetch("/api/storylines", { signal });
  return readJsonResponse<StorylineListResponse>(response, "Failed to load storylines");
}

export async function fetchStorylineDetail(id: string, signal?: AbortSignal): Promise<StorylineDetailResponse> {
  const response = await fetch(`/api/storylines/${encodeURIComponent(id)}`, { signal });
  return readJsonResponse<StorylineDetailResponse>(response, "Failed to load storyline");
}

export async function fetchStorylineNode(
  storylineId: string,
  nodeId: string,
  signal?: AbortSignal,
): Promise<StorylineNodeResponse> {
  const url = `/api/storylines/${encodeURIComponent(storylineId)}/nodes/${encodeURIComponent(nodeId)}`;
  const response = await fetch(url, { signal });
  return readJsonResponse<StorylineNodeResponse>(response, "Failed to load node");
}

export async function generateStoryline(
  description: string,
  signal?: AbortSignal,
): Promise<StorylineGenerateResponse> {
  const response = await fetch("/api/storylines/generate", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ description }),
    signal,
  });
  return readJsonResponse<StorylineGenerateResponse>(response, "Failed to generate storyline");
}

export async function askAboutNode(
  storylineId: string,
  nodeId: string,
  question: string,
  history: { role: string; content: string }[] = [],
  signal?: AbortSignal,
): Promise<NodeAskResponse> {
  const url = `/api/storylines/${encodeURIComponent(storylineId)}/nodes/${encodeURIComponent(nodeId)}/ask`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question, history }),
    signal,
  });
  return readJsonResponse<NodeAskResponse>(response, "Failed to ask question");
}
```

- [ ] **Step 3: 验证 TypeScript 编译**

```bash
cd d:/pythonProject/agentCli/agentCli/web && npx tsc --noEmit
```
Expected: No errors.

- [ ] **Step 4: 提交**

```bash
cd d:/pythonProject/agentCli/agentCli && git add web/src/components/coderead/types.ts web/src/api/client.ts && git commit -m "feat: add frontend types and API client for storylines"
```

---

### Task 7: CodeReadingPanel 状态机容器

**Files:**
- Create: `web/src/components/coderead/CodeReadingPanel.tsx`

- [ ] **Step 1: 写容器组件**

```typescript
// web/src/components/coderead/CodeReadingPanel.tsx
import { useCallback, useEffect, useState } from "react";

import type { Storyline, StorylineNode, ReadingState } from "./types";
import { fetchStorylines } from "../../api/client";
import { StorylineDiscovery } from "./StorylineDiscovery";
import { StorylineReader } from "./StorylineReader";
import { StorylineComplete } from "./StorylineComplete";

type CodeReadingPanelProps = {
  onOpenFile: (path: string, line?: number) => void;
};

export function CodeReadingPanel({ onOpenFile }: CodeReadingPanelProps) {
  const [viewState, setViewState] = useState<ReadingState>("discovery");
  const [storylines, setStorylines] = useState<Storyline[]>([]);
  const [activeStoryline, setActiveStoryline] = useState<Storyline | null>(null);
  const [currentNodeIndex, setCurrentNodeIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    (async () => {
      setLoading(true);
      try {
        const data = await fetchStorylines(controller.signal);
        if (!cancelled) {
          setStorylines(data.storylines);
          setError(null);
        }
      } catch (err) {
        if (!cancelled && !(err instanceof DOMException && err.name === "AbortError")) {
          setError("加载主线失败");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; controller.abort(); };
  }, []);

  const startReading = useCallback((storyline: Storyline) => {
    setActiveStoryline(storyline);
    setCurrentNodeIndex(0);
    setViewState("reading");
  }, []);

  const advanceNode = useCallback(() => {
    if (!activeStoryline) return;
    const nextIdx = currentNodeIndex + 1;
    if (nextIdx >= activeStoryline.nodes.length) {
      setViewState("complete");
    } else {
      setCurrentNodeIndex(nextIdx);
    }
  }, [activeStoryline, currentNodeIndex]);

  const previousNode = useCallback(() => {
    setCurrentNodeIndex((i) => Math.max(0, i - 1));
  }, []);

  const goToNode = useCallback((index: number) => {
    if (activeStoryline && index >= 0 && index < activeStoryline.nodes.length) {
      setCurrentNodeIndex(index);
    }
  }, [activeStoryline]);

  const backToDiscovery = useCallback(() => {
    setViewState("discovery");
    setActiveStoryline(null);
    setCurrentNodeIndex(0);
  }, []);

  const startNewStoryline = useCallback(() => {
    setViewState("discovery");
    setActiveStoryline(null);
    setCurrentNodeIndex(0);
  }, []);

  if (viewState === "discovery") {
    return (
      <StorylineDiscovery
        storylines={storylines}
        loading={loading}
        error={error}
        onSelect={startReading}
        onRefresh={() => {
          setLoading(true);
          setError(null);
          fetchStorylines().then((d) => {
            setStorylines(d.storylines);
            setLoading(false);
          }).catch(() => {
            setError("刷新失败");
            setLoading(false);
          });
        }}
      />
    );
  }

  if (viewState === "reading" && activeStoryline) {
    const currentNode = activeStoryline.nodes[currentNodeIndex];
    return (
      <StorylineReader
        storyline={activeStoryline}
        currentNode={currentNode}
        currentNodeIndex={currentNodeIndex}
        totalNodes={activeStoryline.nodes.length}
        onAdvance={advanceNode}
        onPrevious={previousNode}
        onGoToNode={goToNode}
        onExit={backToDiscovery}
        onOpenFile={onOpenFile}
      />
    );
  }

  if (viewState === "complete" && activeStoryline) {
    return (
      <StorylineComplete
        storyline={activeStoryline}
        onNewStoryline={startNewStoryline}
        onReplay={() => {
          setCurrentNodeIndex(0);
          setViewState("reading");
        }}
      />
    );
  }

  return null;
}
```

- [ ] **Step 2: 提交（子组件先做桩）**

```bash
cd d:/pythonProject/agentCli/agentCli && git add web/src/components/coderead/CodeReadingPanel.tsx && git commit -m "feat: add CodeReadingPanel state machine container"
```

---

### Task 8: 发现页组件

**Files:**
- Create: `web/src/components/coderead/StorylineDiscovery.tsx`

- [ ] **Step 1: 实现发现页**

```typescript
// web/src/components/coderead/StorylineDiscovery.tsx
import type { Storyline } from "./types";

type StorylineDiscoveryProps = {
  storylines: Storyline[];
  loading: boolean;
  error: string | null;
  onSelect: (storyline: Storyline) => void;
  onRefresh: () => void;
};

export function StorylineDiscovery({
  storylines,
  loading,
  error,
  onSelect,
  onRefresh,
}: StorylineDiscoveryProps) {
  return (
    <div className="panel" style={{ display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <h3 style={{ margin: 0, fontSize: 14 }}>代码研读</h3>
        <button className="toolbar-btn" onClick={onRefresh} disabled={loading} type="button">
          {loading ? "加载中..." : "刷新"}
        </button>
      </div>

      {error ? (
        <p style={{ color: "#b91c1c", fontSize: 12 }}>{error}</p>
      ) : null}

      {loading ? (
        <p className="muted">正在发现可用主线...</p>
      ) : storylines.length === 0 ? (
        <p className="muted">暂无可读主线。项目可能需要更多 Python 文件来生成阅读路径。</p>
      ) : (
        <div style={{ display: "grid", gap: 8 }}>
          {storylines.map((s) => (
            <button
              key={s.id}
              onClick={() => onSelect(s)}
              style={{
                textAlign: "left",
                padding: "10px 12px",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-md)",
                background: "#fff",
                cursor: "pointer",
                transition: "border-color 0.15s, box-shadow 0.15s",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = "var(--accent)";
                e.currentTarget.style.boxShadow = "0 0 0 2px rgba(37,99,235,0.1)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "var(--border)";
                e.currentTarget.style.boxShadow = "none";
              }}
            >
              <div style={{ fontWeight: 600, fontSize: 13, color: "var(--text-body)" }}>
                {s.title}
              </div>
              <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
                {s.description}
              </div>
              <div style={{ display: "flex", gap: 12, marginTop: 6, fontSize: 10, color: "#9ca3af" }}>
                <span>{s.node_count} 个节点</span>
                <span>约 {s.estimated_minutes} 分钟</span>
                <span>{s.file_count} 个文件</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 提交**

```bash
cd d:/pythonProject/agentCli/agentCli && git add web/src/components/coderead/StorylineDiscovery.tsx && git commit -m "feat: add StorylineDiscovery component"
```

---

### Task 9: 阅读页 — NarrativeCards + NodeQA

**Files:**
- Create: `web/src/components/coderead/NarrativeCards.tsx`
- Create: `web/src/components/coderead/NodeQA.tsx`

- [ ] **Step 1: 实现 NarrativeCards**

```typescript
// web/src/components/coderead/NarrativeCards.tsx
type NarrativeCardsProps = {
  narrative: {
    summary: string;
    design_notes: string;
    warnings: string | null;
  } | null;
  loading: boolean;
};

export function NarrativeCards({ narrative, loading }: NarrativeCardsProps) {
  if (loading) {
    return (
      <div style={{ padding: "12px 0" }}>
        <p className="muted" style={{ fontSize: 11 }}>AI 正在分析这段代码...</p>
        <div style={{ background: "#f3f4f6", borderRadius: 4, height: 4, overflow: "hidden", marginTop: 8 }}>
          <div style={{
            background: "var(--accent)",
            height: 4,
            width: "60%",
            borderRadius: 4,
            animation: "pulse 1s ease-in-out infinite",
          }} />
        </div>
      </div>
    );
  }

  if (!narrative) {
    return <p className="muted" style={{ fontSize: 11 }}>解释暂不可用</p>;
  }

  return (
    <div style={{ display: "grid", gap: 8 }}>
      <div style={{
        borderLeft: "2px solid var(--accent)",
        paddingLeft: 10,
        fontSize: 12,
        lineHeight: 1.6,
        color: "var(--text-body)",
      }}>
        <div style={{ fontSize: 10, fontWeight: 600, color: "var(--accent)", marginBottom: 2 }}>
          做什么
        </div>
        {narrative.summary}
      </div>

      <div style={{
        borderLeft: "2px solid #f59e0b",
        paddingLeft: 10,
        fontSize: 12,
        lineHeight: 1.6,
        color: "var(--text-body)",
      }}>
        <div style={{ fontSize: 10, fontWeight: 600, color: "#b45309", marginBottom: 2 }}>
          为什么这样设计
        </div>
        {narrative.design_notes}
      </div>

      {narrative.warnings ? (
        <div style={{
          borderLeft: "2px solid #ef4444",
          paddingLeft: 10,
          fontSize: 12,
          lineHeight: 1.6,
          color: "var(--text-body)",
          background: "#fef2f2",
          padding: "8px 10px",
          borderRadius: "0 4px 4px 0",
        }}>
          <div style={{ fontSize: 10, fontWeight: 600, color: "#b91c1c", marginBottom: 2 }}>
            注意
          </div>
          {narrative.warnings}
        </div>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 2: 实现 NodeQA**

```typescript
// web/src/components/coderead/NodeQA.tsx
import { useState } from "react";

type Message = {
  role: "user" | "ai";
  content: string;
};

type NodeQAProps = {
  onAsk: (question: string) => Promise<string>;
};

export function NodeQA({ onAsk }: NodeQAProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSend() {
    const q = input.trim();
    if (!q || loading) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setLoading(true);
    try {
      const answer = await onAsk(q);
      setMessages((prev) => [...prev, { role: "ai", content: answer }]);
    } catch {
      setMessages((prev) => [...prev, { role: "ai", content: "提问失败，请重试。" }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {messages.length > 0 && (
        <div style={{ maxHeight: 160, overflowY: "auto", display: "grid", gap: 4 }}>
          {messages.map((m, i) => (
            <div
              key={i}
              style={{
                fontSize: 10,
                lineHeight: 1.5,
                padding: "4px 8px",
                borderRadius: 6,
                background: m.role === "user" ? "#f9fafb" : "#eff6ff",
                color: m.role === "user" ? "#6b7280" : "#374151",
              }}
            >
              <span style={{ fontWeight: 600, fontSize: 9 }}>
                {m.role === "user" ? "你" : "AI"}
              </span>
              <div>{m.content}</div>
            </div>
          ))}
        </div>
      )}

      <div style={{ display: "flex", gap: 4 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") handleSend(); }}
          placeholder="问这段代码..."
          className="filterInput"
          style={{ flex: 1, fontSize: 11, padding: "5px 8px" }}
          disabled={loading}
        />
        <button
          className="toolbar-btn"
          onClick={handleSend}
          disabled={loading}
          style={{ fontSize: 11, whiteSpace: "nowrap" }}
          type="button"
        >
          {loading ? "..." : "发送"}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: 提交**

```bash
cd d:/pythonProject/agentCli/agentCli && git add web/src/components/coderead/NarrativeCards.tsx web/src/components/coderead/NodeQA.tsx && git commit -m "feat: add NarrativeCards and NodeQA components"
```

---

### Task 10: 阅读页主组件

**Files:**
- Create: `web/src/components/coderead/StorylineReader.tsx`

- [ ] **Step 1: 实现 StorylineReader**

```typescript
// web/src/components/coderead/StorylineReader.tsx
import { useCallback, useEffect, useState } from "react";

import type { Storyline, StorylineNode } from "./types";
import type { StorylineNodeResponse } from "./types";
import { fetchStorylineNode, askAboutNode } from "../../api/client";
import { NarrativeCards } from "./NarrativeCards";
import { NodeQA } from "./NodeQA";

type StorylineReaderProps = {
  storyline: Storyline;
  currentNode: StorylineNode;
  currentNodeIndex: number;
  totalNodes: number;
  onAdvance: () => void;
  onPrevious: () => void;
  onGoToNode: (index: number) => void;
  onExit: () => void;
  onOpenFile: (path: string, line?: number) => void;
};

export function StorylineReader({
  storyline,
  currentNode,
  currentNodeIndex,
  totalNodes,
  onAdvance,
  onPrevious,
  onGoToNode,
  onExit,
  onOpenFile,
}: StorylineReaderProps) {
  const [nodeData, setNodeData] = useState<StorylineNodeResponse | null>(null);
  const [loadingNode, setLoadingNode] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadNode = useCallback(async () => {
    setLoadingNode(true);
    setError(null);
    try {
      const data = await fetchStorylineNode(storyline.id, currentNode.graph_node_id);
      setNodeData(data);
      if (data.node.file_path) {
        onOpenFile(data.node.file_path, data.node.line_start);
      }
    } catch {
      setError("加载节点失败");
    } finally {
      setLoadingNode(false);
    }
  }, [storyline.id, currentNode.graph_node_id, onOpenFile]);

  useEffect(() => {
    loadNode();
  }, [loadNode]);

  async function handleAsk(question: string): Promise<string> {
    const resp = await askAboutNode(storyline.id, currentNode.graph_node_id, question);
    return resp.answer;
  }

  const progressPct = ((currentNodeIndex + 1) / totalNodes) * 100;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      {/* Progress bar */}
      <div style={{ background: "var(--border)", height: 3, flexShrink: 0 }}>
        <div style={{
          background: "var(--accent)",
          height: 3,
          width: `${progressPct}%`,
          transition: "width 0.3s",
        }} />
      </div>

      {/* Header */}
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "6px 12px",
        background: "var(--surface)",
        borderBottom: "1px solid var(--border)",
        fontSize: 11,
        flexShrink: 0,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontWeight: 600 }}>{storyline.title}</span>
          <span style={{ color: "var(--text-muted)" }}>
            {currentNodeIndex + 1}/{totalNodes}
          </span>
        </div>
        <button className="toolbar-btn" onClick={onExit} type="button" style={{ fontSize: 10 }}>
          退出
        </button>
      </div>

      {/* Main: 70/30 split */}
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        {/* 70% Source code */}
        <div style={{ flex: 7, minHeight: 0, display: "flex", flexDirection: "column", borderRight: "1px solid var(--border)" }}>
          <div style={{
            padding: "4px 10px",
            background: "#fafbfc",
            borderBottom: "1px solid var(--border)",
            fontSize: 10,
            color: "var(--text-muted)",
            flexShrink: 0,
          }}>
            {currentNode.file_path}
          </div>
          <div style={{
            flex: 1,
            overflow: "auto",
            background: "#1e1e2e",
            padding: 10,
            fontFamily: "'Cascadia Code', 'Fira Code', monospace",
            fontSize: 11,
            lineHeight: 1.6,
            color: "#d4d4d4",
          }}>
            {loadingNode ? (
              <span style={{ color: "#888" }}>Loading...</span>
            ) : error ? (
              <span style={{ color: "#f0a0a0" }}>{error}</span>
            ) : nodeData ? (
              <pre style={{ margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                {nodeData.source_code}
              </pre>
            ) : null}
          </div>
        </div>

        {/* 30% Explanation + Q&A */}
        <div style={{
          flex: 3,
          display: "flex",
          flexDirection: "column",
          padding: 10,
          overflow: "auto",
          gap: 10,
          minHeight: 0,
        }}>
          {/* Narrative cards */}
          <NarrativeCards
            narrative={nodeData?.narrative ?? null}
            loading={loadingNode}
          />

          {/* Separator */}
          <div style={{ borderTop: "1px solid var(--border)" }} />

          {/* Q&A */}
          <NodeQA onAsk={handleAsk} />
        </div>
      </div>

      {/* Footer controls */}
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "8px 12px",
        borderTop: "1px solid var(--border)",
        background: "var(--surface)",
        flexShrink: 0,
      }}>
        <div style={{ display: "flex", gap: 6 }}>
          <button
            className="toolbar-btn"
            onClick={onPrevious}
            disabled={currentNodeIndex === 0}
            type="button"
          >
            上一步
          </button>
          <button
            className="toolbar-btn"
            onClick={() => onGoToNode(currentNodeIndex - 1)}
            disabled={currentNodeIndex === 0}
            type="button"
          >
            回看已读
          </button>
        </div>

        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          {/* Node timeline dots */}
          <div style={{ display: "flex", gap: 3, marginRight: 8 }}>
            {Array.from({ length: totalNodes }).map((_, i) => (
              <button
                key={i}
                onClick={() => onGoToNode(i)}
                style={{
                  width: 18,
                  height: 18,
                  borderRadius: "99px",
                  border: "2px solid",
                  borderColor: i < currentNodeIndex ? "#22c55e" : i === currentNodeIndex ? "var(--accent)" : "var(--border)",
                  background: i <= currentNodeIndex ? (i === currentNodeIndex ? "#eff6ff" : "#22c55e") : "transparent",
                  color: i < currentNodeIndex ? "#fff" : i === currentNodeIndex ? "var(--accent)" : "var(--text-muted)",
                  fontSize: 9,
                  fontWeight: 700,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  padding: 0,
                  transition: "all 0.2s",
                }}
                type="button"
              >
                {i < currentNodeIndex ? "✓" : i + 1}
              </button>
            ))}
          </div>

          <button
            className="primaryButton"
            onClick={onAdvance}
            style={{
              fontSize: 12,
              padding: "6px 16px",
              flex: "0 0 auto",
              minWidth: 100,
            }}
            type="button"
          >
            {currentNodeIndex + 1 >= totalNodes ? "完成主线" : "理解了 ✓"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 提交**

```bash
cd d:/pythonProject/agentCli/agentCli && git add web/src/components/coderead/StorylineReader.tsx && git commit -m "feat: add StorylineReader with 70/30 split layout"
```

---

### Task 11: 完成页组件

**Files:**
- Create: `web/src/components/coderead/StorylineComplete.tsx`

- [ ] **Step 1: 实现完成页**

```typescript
// web/src/components/coderead/StorylineComplete.tsx
import type { Storyline } from "./types";

type StorylineCompleteProps = {
  storyline: Storyline;
  onNewStoryline: () => void;
  onReplay: () => void;
};

export function StorylineComplete({ storyline, onNewStoryline, onReplay }: StorylineCompleteProps) {
  return (
    <div className="panel" style={{ textAlign: "center", padding: "24px 16px" }}>
      <div style={{ fontSize: 36, marginBottom: 12 }}>
        {/* eslint-disable-next-line */}
        🎉
      </div>
      <h3 style={{ margin: "0 0 4px 0", fontSize: 16 }}>
        {storyline.title} — 完成
      </h3>
      <p className="muted" style={{ marginBottom: 16 }}>
        {storyline.node_count}/{storyline.node_count} 个节点已读 · 约 {storyline.estimated_minutes} 分钟
      </p>

      <div style={{ display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap" }}>
        <button
          className="toolbar-btn"
          onClick={async () => {
            const lines = storyline.nodes.map(
              (n) => `- [${n.order === 0 ? "x" : " "}] **${n.title}** — \`${n.file_path}:${n.line_start}\``,
            );
            const markdown = `# ${storyline.title}\n\n${storyline.description}\n\n${lines.join("\n")}\n`;
            try {
              await fetch("/api/notes", {
                method: "POST",
                headers: { "content-type": "application/json" },
                body: JSON.stringify({ title: storyline.title, answer: markdown }),
              });
            } catch {
              // Silently fail for export
            }
          }}
          type="button"
        >
          导出笔记
        </button>
        <button className="toolbar-btn" onClick={onReplay} type="button">
          重走一遍
        </button>
        <button
          className="primaryButton"
          onClick={onNewStoryline}
          style={{ fontSize: 12, flex: "0 0 auto" }}
          type="button"
        >
          下一条主线
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 提交**

```bash
cd d:/pythonProject/agentCli/agentCli && git add web/src/components/coderead/StorylineComplete.tsx && git commit -m "feat: add StorylineComplete component"
```

---

### Task 12: 集成到 App.tsx

**Files:**
- Modify: `web/src/App.tsx`

- [ ] **Step 1: 在 App.tsx 中新增"研读"Tab**

定位到 `InspectorTab` 类型定义（约第 28 行），将：

```typescript
type InspectorTab = "analysis" | "tour";
```

改为：

```typescript
type InspectorTab = "analysis" | "tour" | "coderead";
```

定位到 inspector tab 按钮区（约第 262 行的导览 Tab 按钮后），追加：

```tsx
        <button
          className={`inspectorTab ${activeTab === "coderead" ? "inspectorTabActive" : ""}`}
          onClick={() => setActiveTab("coderead")}
        >
          研读
        </button>
```

定位到 `inspectorContent` 的三元表达式（约第 271 行的 `activeTab === "analysis"` 分支），在导览分支后面追加：

```tsx
        ) : activeTab === "coderead" ? (
          <div className="tabsPane">
            <CodeReadingPanel onOpenFile={openGraphNode} />
          </div>
```

- [ ] **Step 2: 验证 TypeScript 编译**

```bash
cd d:/pythonProject/agentCli/agentCli/web && npx tsc --noEmit
```
Expected: No errors.

- [ ] **Step 3: 提交**

```bash
cd d:/pythonProject/agentCli/agentCli && git add web/src/App.tsx && git commit -m "feat: integrate CodeReadingPanel as 研读 tab in inspector"
```

---

### Task 13: 端到端验证

- [ ] **Step 1: 运行全部后端测试**

```bash
cd d:/pythonProject/agentCli/agentCli && python -m pytest tests/ -v
```
Expected: All tests pass.

- [ ] **Step 2: 构建前端**

```bash
cd d:/pythonProject/agentCli/agentCli/web && npm run build
```
Expected: Build succeeds without errors.

- [ ] **Step 3: 启动 dev server 手动验证**

```bash
# Terminal 1: backend
cd d:/pythonProject/agentCli/agentCli && python -m uvicorn agentcli.api.server:create_app --factory --reload

# Terminal 2: frontend
cd d:/pythonProject/agentCli/agentCli/web && npm run dev
```

手动验证：
1. 打开 http://localhost:5173
2. 点击 Inspector 右侧面板的"研读"Tab
3. 确认显示主线列表
4. 点击一条主线，确认进入阅读模式（70/30 布局）
5. 确认代码显示在左侧
6. 确认 AI 解释卡片出现在右侧
7. 在底部输入框提问，确认 AI 回答
8. 点击"理解了"推进到下一步
9. 走完全部节点后确认完成页

- [ ] **Step 4: 最终提交**

```bash
cd d:/pythonProject/agentCli/agentCli && git add -A && git commit -m "chore: finalize code reading storyline feature"
```
