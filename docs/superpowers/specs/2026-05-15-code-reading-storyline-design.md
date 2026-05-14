# 代码研读：叙事型主线引导阅读 — 设计规格

## 概述

将 agentCli 的代码理解能力从"静态调用图"升级为"叙事型主线引导阅读"。用户不再面对一张被动的关系图，而是选择或自定义一条"阅读主线"，AI 按步骤引导——展示源码、解释设计意图、回答追问——直到走完整条业务链路。

### 产品差异化

| 现有工具 | 定位 | 核心体验 |
|----------|------|---------|
| Cursor / Copilot | 帮你写 | 补全、生成 |
| Claude Code / Trae | 帮你做 | Agent 自动执行 |
| **agentCli 研读** | **帮你懂** | **引导式代码理解** |

### 核心体验：对话引导式

- 代码占 70% 视野（Monaco 编辑器）
- 右侧 30% 浮动解释卡片（summary / design_notes / warnings）
- 底部可随时对当前代码段提问
- 用户确认"理解了"后推进到下一步

## 设计决策

| 维度 | 选择 | 原因 |
|------|------|------|
| 叙事生成 | 混合模式：AST 骨架 + LLM 叙事 | 骨架秒出（路径确定），叙事按需生成并缓存 |
| 缓存策略 | `(file_path, content_hash, position)` 为 key | 代码未改不重新生成，用户切换主线秒开 |
| 代码展示 | 复用现有 Monaco 编辑器 | 不重复造轮子，保留语法高亮、搜索、文件跳转 |
| 调用图角色 | 降级为"探索辅助" | 主线走完后或用户主动展开时才进入全屏图模式 |
| 自定义主线 | LLM 实时生成路径 | 用户描述需求 → LLM 在图里找入口和路径 → 生成新主线 |
| 布局 | Inspector 面板 70/30 分栏 | 代码为主，解释不抢视线 |

## 用户体验流

```
发现页 → 阅读中 ⇄ 深入探索 → 完成
```

### 状态 1：发现页

- 展示 AI 预生成的 3-5 条推荐主线（按项目入口自动发现）
- 每条显示：标题、节点链摘要、节点数、预估时间、涉及文件数
- 底部输入框：用户描述想了解的流程，AI 实时生成自定义主线
- 选中的主线进入阅读状态

### 状态 2：阅读中（核心体验）

三区域布局：

**主区域（70%）：Monaco 源码编辑器**
- 显示当前节点的源文件，关键行蓝色高亮
- 顶部超细进度条（当前步骤/总步骤）
- 用户可自由浏览文件其他部分
- "理解了"按钮推进到下一步

**侧区域（30%）：AI 解释卡片**
- 三个折叠卡片：这段代码做什么 / 为什么这样设计 / 注意事项
- 预加载：用户停留在当前节点时，异步加载下一个节点的解释
- 底部追问输入框：对当前代码段提问

**底部操作栏**
- "理解了，下一步" — 主线推进
- "上一步" — 回看
- "展开调用图" — 进入深入探索模式

### 状态 3：深入探索

- 全屏调用图（复用现有 CallGraph 组件）
- 节点着色扩展：已读（灰绿）、当前位置（蓝）、下一步（蓝虚线）、未读（灰）
- 可展开/收起子节点
- "返回主线"按钮回到阅读状态

### 状态 4：完成

- 总结页面：已完成的节点列表 + 核心收获
- "导出笔记"：生成 Markdown 文件到 notes/
- "下一条主线"：回到发现页或推荐关联主线

## 后端架构

### 新增模块

```
src/agentcli/analysis/
├── graph.py          ← 已有，不改
├── storyline.py      ← 新增：主线生成引擎
└── cache.py          ← 新增：AI 解释缓存
```

### storyline.py

核心函数：

- `discover_storylines(repo_root)` → `list[Storyline]`
  从调用图中自动发现主线。策略：
  1. 识别入口函数（CLI 入口、FastAPI 路由、`main()` 函数）
  2. 从入口 BFS，按调用频度排序，生成候选路径
  3. 过滤掉过短（<3 节点）或过长（>15 节点）的路径
  4. 去重：相似的路径合并

- `generate_custom_storyline(repo_root, user_description)` → `Storyline`
  LLM 根据用户描述在图数据中定位入口节点，BFS 生成路径

- `generate_node_narrative(repo_root, node_id, position)` → `NodeNarrative`
  对单个节点调用 LLM 生成三段解释。结果写入缓存。

- `ask_about_node(repo_root, node_id, question, conversation_history)` → `str`
  实时 LLM 问答，上下文包含当前代码段和调用关系

### cache.py

- 存储位置：`.agentcli/storyline-cache/`
- Key：`{file_path}:{content_hash}:{line_start}-{line_end}`
- Value：`{summary, design_notes, warnings, generated_at}`
- 失效条件：文件内容 hash 变化

### API 端点

```
GET  /api/storylines
  → { storylines: [{id, title, description, node_count, estimated_minutes, file_count}] }

GET  /api/storylines/{id}
  → { id, title, description, nodes: [{order, title, file_path, line_start, line_end, graph_node_id}] }
  （叙事内容不在此返回，按节点单独加载）

GET  /api/storylines/{id}/nodes/{node_id}
  → { node, source_code, narrative: {summary, design_notes, warnings} | null }
  （narrative 为 null 时前端显示加载态，后端异步生成并缓存）

POST /api/storylines/generate
  Body: { description: "用户描述的流程..." }
  → { storyline: {...}, status: "ready" | "generating" }

POST /api/storylines/{id}/nodes/{node_id}/ask
  Body: { question: "...", history: [...] }
  → { answer: "...", source_refs: [...] }
```

### 数据模型

```python
class StorylineNode:
    order: int
    title: str
    file_path: str
    line_start: int
    line_end: int
    graph_node_id: str  # 对应调用图的 node id
    summary: str | None
    design_notes: str | None
    warnings: str | None

class Storyline:
    id: str
    title: str
    description: str
    nodes: list[StorylineNode]
    node_count: int
    estimated_minutes: int
    file_count: int
```

## 前端架构

### 组件树

```
Inspector
├── Tab: 分析 (已有)
├── Tab: 导览 (已有)
└── Tab: 研读 (新增)
    └── CodeReadingPanel
        ├── [发现页] StorylineDiscovery
        │   ├── StorylineCard[]       # 主线卡片列表
        │   └── CustomStorylineInput  # 自定义主线输入
        │
        ├── [阅读中] StorylineReader
        │   ├── ProgressBar           # 顶部进度条
        │   ├── Monaco Editor         # 复用现有，70%宽度
        │   ├── NarrativeCards        # 右侧30%解释卡片区
        │   │   ├── SummaryCard
        │   │   ├── DesignNotesCard
        │   │   └── WarningsCard
        │   ├── NodeQA                # 底部追问区
        │   └── ReaderControls        # 理解了/上一步/展开图
        │
        └── [完成] StorylineComplete
            ├── NodeSummaryList
            ├── ExportNotesButton
            └── NextStorylineSuggest
```

### 状态管理

```typescript
type ReadingState = "discovery" | "reading" | "complete";

type ReaderStore = {
  state: ReadingState;
  storylines: Storyline[];
  activeStoryline: Storyline | null;
  currentNodeIndex: number;
  narratives: Map<string, NodeNarrative>;  // node_id → narrative
  loadingNarrative: Set<string>;          // 正在加载的 node_id
};
```

## 边界情况

| 场景 | 处理 |
|------|------|
| 项目无 Python 文件 | 发现页显示"暂无可读主线，试试自定义" |
| LLM 生成叙事失败 | 节点显示降级态（只有骨架信息），用户可手动重试 |
| 缓存过期（代码变更） | 下次访问节点时自动重新生成 |
| 自定义主线描述不清晰 | LLM 返回引导性问题，帮助用户细化 |
| 用户频繁点"理解了" | 不移除已生成内容，但标记跳过的节点 |
| 问答超时 | 30 秒 abort，显示重试按钮 |
| 主线太长（>15 节点） | 建议用户拆分为两条或选择关注范围 |

## 本次非目标

- 非 Python 语言支持
- 实时协作/多人阅读
- 阅读进度跨设备同步
- 主线社区的分享/导入
- 视频录制式的代码讲解

## 后续增强

- 主线节点可折叠子节点（展开/收起）
- 阅读历史和个人进度追踪
- 从 Monaco 当前光标反向定位主线节点
- 支持 Python 之外的静态分析（TypeScript、Go）
- 导出为 PDF / Markdown 阅读笔记
