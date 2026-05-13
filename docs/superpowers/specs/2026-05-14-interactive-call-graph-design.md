# 交互式调用链/依赖图 — 设计规格

## 概述

为 agentCli Web 工作台增加交互式调用链/依赖图可视化面板。后端基于现有 AST 分析引擎扩展，前端采用 Cytoscape.js 实现层次树图，支持节点展开/折叠、源码双向联动。

## 设计决策

| 维度 | 选择 | 原因 |
|------|------|------|
| 语言 | Python 优先，架构可插拔 | 复用现有 `trace.py` 的 AST 分析，预留 `LanguageAnalyzer` 接口 |
| 交互 | 可展开图 | 节点可展开/折叠子调用，支持正向+反向追踪 |
| 数据加载 | 混合模式 | 骨架预扫 <500ms，深层展开按需 BFS |
| 布局 | 层次树 (Top-Down) | 调用层级最直观，dagre 算法内置 |
| 图形库 | Cytoscape.js | 内置展开/折叠、dagre 布局、Canvas 渲染，开发周期最短 |

## 架构

### 后端新增 — `agentcli/analysis/graph.py`

三个函数，复用 `trace.py` 的 `_build_definition_index` 和 `trace_python_flow`：

- `build_skeleton_graph(repo_root)` → 全量扫描，返回所有函数节点 + 一层直接调用边
- `expand_call_node(repo_root, symbol, depth)` → BFS 追踪指定函数的深层调用子图
- `get_node_detail(repo_root, symbol)` → 返回单节点元数据（入度/出度/文件/行号）

### API 新增 — `server.py` 三个端点

```
GET /api/graph/skeleton
  → { nodes: [...], edges: [...] }

GET /api/graph/expand?symbol=xxx&depth=3
  → { root, nodes: [...], edges: [...] }

GET /api/graph/node?symbol=xxx
  → { symbol, path, line, kind, incoming: [...], outgoing: [...] }
```

### 前端重构 — `CallGraph.tsx` 完整重写

```
web/src/
├── components/
│   └── CallGraph.tsx          # Cytoscape 容器，替换现有 JSON dump
├── graph/
│   ├── useCallGraph.ts        # 图状态管理（skeleton加载 → 增量expand → merge）
│   ├── styles.ts              # 节点/边 Cytoscape 样式定义
│   └── interactions.ts        # 点击展开/折叠、右键菜单、Monaco联动
```

### 节点颜色编码

- 蓝色矩形：method
- 绿色矩形：function
- 黄色矩形：class
- 紫色圆形：external（第三方库，不可展开）
- 虚线边：循环调用

### 工具栏

搜索节点 | 适应画布 | 力导向布局切换 | 导出 PNG/SVG

## 数据流

1. 页面加载 → `GET /api/graph/skeleton` → 渲染全量骨架图（折叠态，一层可见）
2. 用户点击节点 ⊕ → `GET /api/graph/expand` → 增量 merge，dagre 布局动画
3. 用户双击节点 → `openFile(path, {startLine})` → Monaco 跳转函数定义行
4. 用户右键节点 → 上下文菜单：Open in Editor / 查看详情 / 从此节点追踪

## 边界情况

| 场景 | 处理 |
|------|------|
| 无 Python 文件 | 返回空图 + warning 提示 |
| 1000+ 函数 | 过滤孤立函数，前端 500 节点以上虚拟化渲染 |
| 语法错误文件 | 静默跳过，附带 `skipped_files` 列表 |
| 循环调用 (A→B→A) | visited 集合终止，虚线表示 |
| 第三方库调用 | 标记为 external 叶子节点，不展开 |
| 图为空 | 引导提示 "点击 Run Analysis 开始分析" |
| expand 超时 | 5 秒超时，显示重试提示 |

## 与竞品对比

| 维度 | agentCli | Cursor | Claude Code | Codex |
|------|----------|--------|-------------|-------|
| 分析方式 | AST 静态解析，确定性 | LLM 推断 | LLM 推断 | LLM 推断 |
| 可视化 | 交互式层次树图 | 内联引用弹窗 | 无 GUI | 无 GUI |
| 精确度 | 行级精确 | 依赖模型 | 依赖模型 | 依赖模型 |
| 全局视角 | 全项目函数调用网络 | 仅当前文件 | 仅 grep 输出 | 仅当前文件 |
| 离线 | AST 分析不消耗 API | 需 API | 需 API | 需 API |

## 不包含（非目标）

- 非 Python 语言支持（架构预留，本次不实现）
- 运行时调用图（仅静态分析）
- Git 历史变更影响分析
- 自动生成文档/架构图导出为文档
