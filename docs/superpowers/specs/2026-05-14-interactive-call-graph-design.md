# 交互式调用链/依赖图 — 设计规格

## 概述

为 agentCli Web 工作台增加一个可交互的 Python 静态调用图面板。后端复用现有 `trace.py` 的 AST 分析能力，输出稳定的图数据；前端使用 Cytoscape.js + dagre 布局渲染层次图，支持加载全局骨架、按节点展开子调用、双击跳转源码、右键打开节点操作菜单。

本次目标是做一个可靠的 MVP：把现有 JSON dump 替换成可视化图，并保证后端数据模型、API、前端类型和 Monaco 打开文件能力一致。搜索、折叠、导出、源码反向联动等增强能力留到后续迭代。

## 设计决策

| 维度 | 选择 | 原因 |
|------|------|------|
| 语言 | Python 优先 | 当前分析能力集中在 `trace.py`，先复用已有 AST 解析，避免扩展多语言接口导致范围过大 |
| 图数据 | 稳定唯一节点 ID + 短标签 | 全项目中可能存在同名函数，节点 ID 使用 `path::qualname`，前端展示 `label` |
| 交互 | MVP 支持展开、选中、双击打开 | 覆盖最核心的理解代码路径场景，折叠和搜索后续再做 |
| 数据加载 | Skeleton + expand 按需加载 | Skeleton 返回定义和直接边；expand 从指定节点按 BFS 深度返回子图 |
| 缓存 | `create_app` 内存缓存 | 避免每个 API 请求重复扫描整个仓库；按文件路径、mtime、size 生成轻量签名失效 |
| 布局 | dagre Top-Down | 调用层级最直观，Cytoscape 与 `cytoscape-dagre` 易集成 |
| 错误处理 | 返回 warning/skipped_files，不中断页面 | 语法错误文件和空仓库都应可展示降级状态 |

## MVP 架构

### 后端新增 — `src/agentcli/analysis/graph.py`

新增独立图分析模块，不改动 `trace_python_flow` 的外部行为。模块可以复用 `_build_definition_index` 的思路，但需要解决两个问题：

- `trace.py` 当前索引以短 symbol 为 key，可能覆盖同名函数；图模块应生成唯一节点 ID。
- `trace.py` 当前静默跳过语法错误文件；图模块应返回 `skipped_files` 供 UI 提示。

核心函数：

- `build_graph_index(repo_root)`：扫描 Python 文件，返回节点、边、跳过文件列表和辅助索引。
- `build_skeleton_graph(repo_root)`：返回全项目节点和直接调用边。
- `expand_call_node(repo_root, node_id, depth)`：从唯一节点 ID 出发 BFS 展开，深度限制为 1-5。
- `get_node_detail(repo_root, node_id)`：返回单节点元数据、入边和出边。

节点数据：

```json
{
  "id": "src/agentcli/cli.py::main",
  "label": "main",
  "path": "src/agentcli/cli.py",
  "line": 42,
  "kind": "function",
  "degree": 3
}
```

边数据：

```json
{
  "id": "src/a.py::main->src/b.py::helper",
  "source": "src/a.py::main",
  "target": "src/b.py::helper",
  "relation": "calls",
  "is_cycle": false
}
```

### API 新增 — `src/agentcli/api/server.py`

在 `create_app(repo_root)` 内新增一个小型缓存对象，供三个图 API 共用：

```text
GET /api/graph/skeleton
  -> { nodes, edges, warning, skipped_files }

GET /api/graph/expand?node_id=...&depth=3
  -> { root, nodes, edges }

GET /api/graph/node?node_id=...
  -> { node, incoming, outgoing }
```

API 参数使用 `node_id`，避免与旧的短 symbol 解析混淆。为了前端 URL 安全，调用方必须 `encodeURIComponent(nodeId)`。

### 前端新增/修改

```text
web/src/
├── components/
│   └── CallGraph.tsx          # Cytoscape 容器和工具栏
├── graph/
│   ├── types.ts               # 与后端 schema 对齐的 TS 类型
│   ├── useCallGraph.ts        # 加载 skeleton、expand merge、fit/refresh 状态
│   ├── styles.ts              # Cytoscape 样式
│   └── interactions.ts        # tap、dbltap、right-click 菜单
└── api/
    └── client.ts              # graph API 客户端函数
```

`App.tsx` 不直接把当前 `openFile(path, range?)` 传给图组件。新增适配函数：

```ts
function openGraphNode(path: string, line?: number) {
  openFile(path, line ? { path, startLine: line, endLine: line } : undefined);
}
```

### 节点颜色编码

- 蓝色矩形：method
- 绿色矩形：function
- 黄色矩形：class
- 紫色圆形：external（不可展开）
- 虚线边：循环调用

## 数据流

1. 页面加载 → `GET /api/graph/skeleton` → 渲染全局骨架图。
2. 用户右键节点选择 Expand → `GET /api/graph/expand?node_id=...&depth=3` → 增量 merge 节点和边。
3. 用户双击节点 → `onOpenFile(path, line)` → `App.tsx` 转换为 Monaco 高亮范围。
4. 用户点击节点 → `GET /api/graph/node?node_id=...` → 显示简要详情。
5. 用户点击 Refresh → 清空 Cytoscape 元素并重新加载 skeleton。

## 边界情况

| 场景 | 处理 |
|------|------|
| 无 Python 文件 | 返回空图 + `warning: "no_python_files"` |
| 语法错误文件 | 跳过该文件，`skipped_files` 返回相对路径 |
| 同名函数 | 节点 ID 使用 `path::qualname`，展示 label 保持简洁 |
| 未解析调用 | 标记为 `external` 叶子节点，不支持 expand |
| 循环调用 | BFS visited 集合终止，边标记 `is_cycle: true` |
| 节点过多 | Skeleton 首版仍返回全部节点；前端显示节点/边数量，后续再做过滤或搜索 |
| expand 超时 | 前端 5 秒 abort，显示可重试错误 |
| API 错误 | 客户端检查 `response.ok`，显示错误提示 |

## 本次非目标

- 非 Python 语言支持。
- 运行时调用图。
- Git 历史变更影响分析。
- 节点折叠/隐藏子树。
- 搜索节点、布局切换、导出 PNG/SVG。
- Monaco 当前光标/文件反向定位图节点。
- 500+ 节点虚拟化或智能过滤。

## 后续增强

- 搜索节点并居中高亮。
- Fit、布局切换、导出 PNG/SVG。
- 折叠/展开子树状态。
- 从当前 Monaco 文件或光标反向定位图节点。
- 多语言 `LanguageAnalyzer` 插件接口。
