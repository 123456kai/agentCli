"""LLM prompts for the three-stage storyline generation pipeline.

Stage 1 — Domain analysis: scan directory tree, output domain groups.
Stage 2 — Path planning: given domains and call-graph nodes, plan reading paths.
Stage 3 — Progressive narrative: per-node teaching narrative with context.
"""

# ---------------------------------------------------------------------------
# Stage 1: Domain analysis
# ---------------------------------------------------------------------------

STAGE1_DOMAIN_ANALYSIS = """你是一位软件架构分析师。分析以下项目的目录结构，将文件按业务领域分组。

## 项目目录树
{dir_tree}

## 要求
1. 识别跨目录的逻辑分组（例如 cli.py + config.py 属于"CLI 入口"领域）
2. 每组给定一个中文名称和一句话职责描述
3. 返回 JSON 对象（不要 markdown，不要额外文字）：

```json
{{
  "domains": [
    {{
      "id": "cli",
      "name": "CLI 入口",
      "description": "命令行接口定义和配置解析",
      "files": ["src/agentcli/cli.py", "src/agentcli/config.py"]
    }}
  ]
}}
```

分组粒度建议 4-8 个领域。"""

# ---------------------------------------------------------------------------
# Stage 2: Path planning
# ---------------------------------------------------------------------------

STAGE2_PATH_PLANNING = """你是一位代码阅读教练。为一个 Python 项目规划代码阅读主线。

## 项目领域
{domains_json}

## 调用图关键节点（入口函数）
{entry_nodes}

## 什么是好的阅读主线
- 有明确主题：不是"A调用B"，而是"Web API 请求从路由到响应的完整管道"
- 有叙事节奏：按"理解的自然顺序"排列节点。先理解整体结构，再好奇内部细节
- 每个节点有角色名：不是裸函数名，而是"请求入口与路由组装"这样的描述

## Few-shot 示例
示例主线: "Web API 请求管道"
  领域覆盖: api → agent_loop → llm → session
  描述: 从一个 HTTP 请求到达开始，追踪它如何经过路由、Agent 分析、LLM 调用，到最终产生回答
  叙事节奏: 先看应用组装（路由注册），再看请求处理（Agent 入口），最后看响应生成（LLM 调用）

示例主线: "Agent 循环执行流程"
  领域覆盖: agent_loop → llm → tools
  描述: Agent 如何处理一个用户问题——从接收消息、调用 LLM、执行工具、到返回答案
  叙事节奏: 先看循环骨架（run_turn），再看 LLM 交互（adapter），最后看工具执行

## 要求
为每个领域生成一条阅读主线。每条主线 4-10 个节点。

返回 JSON：
```json
{{
  "storylines": [
    {{
      "title": "Web API 请求管道",
      "description": "从一个 HTTP 请求到达开始，追踪完整处理流程",
      "theme": "api",
      "node_sequence": [
        {{"order": 0, "role_title": "应用组装与路由注册", "file_path": "src/agentcli/api/server.py", "graph_node_id": "src/agentcli/api/server.py::create_app"}},
        {{"order": 1, "role_title": "请求接入", "file_path": "src/agentcli/api/server.py", "graph_node_id": "src/agentcli/api/server.py::run_endpoint"}}
      ]
    }}
  ]
}}
```

graph_node_id 必须从上面"调用图关键节点"列表中选取，确保精确匹配。"""

# ---------------------------------------------------------------------------
# Stage 3: Progressive narrative (code tour guide)
# ---------------------------------------------------------------------------

STAGE3_PROGRESSIVE_NARRATIVE = """你是一位代码导游。你的学生正在逐节点阅读一条代码主线。

## 当前主线
主题: {storyline_title}

## 已读节点摘要
{previous_nodes_context}

## 当前节点
角色: {node_role_title}
文件: {file_path}

## 源码
```python
{code_snippet}
```

## 叙事要求
1. 先说"这个节点解决什么问题"（1句话），建立阅读动机。不要一上来就讲代码细节
2. 再说"它怎么做的"（2-3句话），解释关键设计决策和值得注意的模式
3. 最后说"接下来你会好奇什么"（1句话），与已读节点形成逻辑衔接。用"理解了X之后，你会好奇Y是怎么发生的"这种句式
4. **禁止**说"A调用B"、"该函数调用X"这类调用关系描述
5. **禁止**重复已读节点中已经解释过的内容

返回 JSON（不要 markdown，不要额外文字）：
{{
  "summary": "建立阅读动机+解释做什么（1-2句话）",
  "design_notes": "怎么做的+设计决策（2-3句话）",
  "warnings": "潜在问题或注意事项，没有则为 null",
  "next_teaser": "接下来你会好奇什么（1句话，与前序节点衔接）"
}}"""

# ---------------------------------------------------------------------------
# Fallback narrative (no LLM available)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Stage 4: Custom storyline generation from user description
# ---------------------------------------------------------------------------

STAGE4_STORYLINE_GENERATION = """你是一位代码阅读教练。根据用户的描述，为这个 Python 项目规划一条自定义的代码阅读路径。

## 调用图关键节点
{entry_nodes}

## 用户需求
{description}

## 什么是好的阅读路径
- 有明确主题：不是"A调用B"，而是"Web API 请求从路由到响应的完整管道"
- 按"理解的自然顺序"排列节点。先理解整体结构，再好奇内部细节
- 每个节点有角色名：不是裸函数名，而是"请求入口与路由组装"这样的描述

## Few-shot 示例
示例: 用户说"我想了解 agent 是怎么处理用户请求的"
  node_sequence: [
    {{"order": 0, "role_title": "Agent 主循环入口", "file_path": "src/agentcli/agent_loop.py", "graph_node_id": "exact_id"}},
    {{"order": 1, "role_title": "消息上下文构建", "file_path": "src/agentcli/agent_loop.py", "graph_node_id": "exact_id"}},
    {{"order": 2, "role_title": "LLM 请求发送与响应解析", "file_path": "src/agentcli/llm/adapter.py", "graph_node_id": "exact_id"}}
  ]

## 要求
生成一条 3-10 个节点的阅读路径。

返回 JSON（不要 markdown，不要额外文字）：
{{
  "title": "主线标题",
  "description": "一句话描述这条路径讲什么",
  "theme": "custom",
  "node_sequence": [
    {{"order": 0, "role_title": "角色描述（非函数名）", "file_path": "path/to/file.py", "graph_node_id": "必须从上面关键节点列表精确选取"}}
  ]
}}

graph_node_id 必须从上面"调用图关键节点"列表中精确选取，确保一致。"""

FALLBACK_STAGE1_DOMAINS = {
    "api": {"name": "Web API", "description": "HTTP 接口与路由", "dirs": ["api"]},
    "cli": {"name": "CLI 入口", "description": "命令行接口与配置", "dirs": ["cli.py", "config.py"]},
    "agent": {"name": "Agent 引擎", "description": "Agent 循环与事件", "dirs": ["agent_loop.py", "engine"]},
    "llm": {"name": "LLM 适配", "description": "大模型调用接口", "dirs": ["llm"]},
    "tools": {"name": "工具系统", "description": "Agent 可调用工具集", "dirs": ["tools"]},
    "analysis": {"name": "代码分析", "description": "静态分析与调用图", "dirs": ["analysis"]},
    "session": {"name": "会话管理", "description": "会话存储与知识库", "dirs": ["session.py", "session_store.py", "knowledge"]},
    "guard": {"name": "安全边界", "description": "文件访问控制", "dirs": ["repo_guard.py"]},
}
