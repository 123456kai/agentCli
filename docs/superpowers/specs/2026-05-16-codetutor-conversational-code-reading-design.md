# CodeTutor：对话式代码阅读助手

> 状态：设计阶段 | 2026-05-16

## 目标

将当前"研读"Tab 从**线性幻灯片模式**改造为**对话式导游模式**。用户体验像跟一位懂代码的老师聊天——老师主动讲解、自然引导、反问推进，而不是扔给你一排选项按钮。

## 核心理念

- **代码是主角，对话是导游**。Monaco 编辑器展示完整代码 + 行号 + 蓝色高亮。对话面板负责解释、引导、反问。
- **不做选择题，做自然对话**。系统每次结尾是一句完整的中文反问（2-3句话），用户用自然语言回应（"好" / "先去看看别的" / 自由提问）。
- **无限延伸的分支对话**。每个分叉点保留消息历史，面包屑回退，旧分支变灰可翻。

---

## 1. 界面布局（不变）

```
┌──────────┐  ┌──────────────────────┐  ┌────────────────────────┐
│  文件树   │  │     Monaco 编辑器       │  │   CodeTutor 对话面板    │
│          │  │                      │  │                        │
│  (不变)  │  │  ← 蓝色高亮 + 行号     │  │  [面包屑导航]            │
│          │  │  ← 每轮自动打开文件    │  │                        │
│          │  │                      │  │  ┌─ 系统消息（讲解）     │
│          │  │                      │  │  │  · 概要             │
│          │  │                      │  │  │  · 代码引用（可点）  │
│          │  │                      │  │  └─ 反问引导           │
│          │  │                      │  │                        │
│          │  │                      │  │  ┌─ 用户消息            │
│          │  │                      │  │  └─ "好，带我去看"      │
│          │  │                      │  │                        │
│          │  │                      │  │  [输入框：自由提问]      │
└──────────┘  └──────────────────────┘  └────────────────────────┘
```

三栏布局不变。Monaco + 文件树完全不动。改动集中在右侧面板的交互模式。

---

## 2. 对话消息模型

### 2.1 消息类型

**系统概览消息**（进入领域时）：

```
Agent 循环模块有 3 个核心环节：run_turn 是主循环入口，负责接收消息；
adapter.respond 负责调用 DeepSeek API；_emit 负责把结果推给前端。
建议先看看 run_turn，从这里你能最直观地理解整个 Agent 是怎么跑起来的。
要不要打开看看？
```

特征：
- 2-4 句话画地图
- 点出核心文件和它们的关系
- 推荐最佳起点
- 结尾是一句自然的反问

**系统讲解消息**（打开代码后）：

```
这段代码在 agent_loop.py 第 82-145 行。
run_turn 的核心思路是：把用户消息和会话历史打包成 messages 列表，
交给 LLM adapter，然后根据返回结果决定是执行工具还是直接回答。
注意第 112 行的循环——只要 LLM 返回的是 tool_call，它就会一直跑下去。

看懂了 run_turn 之后，你可能会好奇一件事：messages 到底是怎么
构造成 DeepSeek API 需要的格式的？这就要看 adapter.respond 了。
要不要继续往下看？
```

特征：
- 先给代码定位（文件 + 行号）
- 2-3 句话解释做什么 + 关键设计
- 1 句引导反问：告诉学生下一块是什么、为什么值得看、跟刚才看的有什么关系
- 反问是自然语言，不是选项按钮

**用户消息**：
- "好" / "继续" / "带我去看" → 推进到系统建议的方向
- "先别，我想看事件怎么发的" → 切换方向，系统识别意图后打开对应代码
- "第 112 行为什么是 while 循环？" → 解答具体问题（不影响当前路径）
- 自由输入任意问题

### 2.2 用户输入处理规则

系统收到用户消息后，判断意图：
1. 确认/推进类（"好""继续""嗯"等）→ 推进到刚才建议的下一块代码
2. 方向切换类（"先看X""换到Y"等）→ 根据调用图 + LLM 找到目标函数，打开代码 + 讲解
3. 提问类（问具体代码细节）→ 直接回答，保持在当前节点不变
4. 无关输入 → 温和引导回当前路径

---

## 3. 面包屑与对话分支

### 3.1 面包屑

对话面板顶部始终显示面包屑：

```
Agent 循环 > run_turn > adapter.respond > DeepSeek API 请求格式
```

- 每级可点击
- 点击后回退到该分叉点
- 回退时下方旧消息变灰保留
- 自动插入分割线：`──────── 你从这里换了方向 ────────`
- 系统感知回退，重新反问下一步方向

### 3.2 分支管理

- 对话历史全量保留在面板中，可滚动
- 旧分支消息变灰但可读
- 不需要用户手动管理任何树形结构
- 分支就是消息历史——翻上去就能看到

---

## 4. 对话起点

进入 CodeTutor Tab 后，展示领域列表（复用当前 `StorylineDiscovery` + `FALLBACK_STAGE1_DOMAINS`），点击领域进入对话。

进入领域后，系统发送第一条概览消息（领域分析 + 入口推荐）。不展示选项按钮，用户自然回应。

### 4.1 领域列表

| 领域 | 目录 | 职责 |
|------|------|------|
| CLI 入口 | cli.py, config.py | 命令解析、配置合并 |
| Agent 循环 | agent_loop.py, engine/ | 多轮对话、事件系统 |
| LLM 适配 | llm/adapter.py | DeepSeek API 封装 |
| 代码分析 | analysis/ | 调用图、主线发现、项目扫描 |
| 工具系统 | tools/ | 6 个源码工具 |
| Web API | api/ | FastAPI 服务、数据模型 |
| 会话管理 | session.py, session_store.py | 会话持久化 |

---

## 5. LLM 提示词设计

### 5.1 系统提示词

```
你是一位代码导游。你的学生正在阅读这个 Python 项目的源码。
你的讲解风格是：像老师带学生参观一样，自然引导，不强加选择。

## 当前会话状态
- 所在领域：{domain_name} — {domain_description}
- 当前文件：{file_path} 第 {line_start}-{line_end} 行
- 已读节点摘要：{visited_nodes_summary}

## 当前源码
```python
{code_snippet}
```

## 你的任务
1. 用 2-3 句话解释这段代码做什么、关键设计是什么。
   先说"这段代码在 {file_path} 第 X-Y 行"。
2. 解释时禁止说"A调用B"。应该说"理解了这段之后，你会好奇
   X是怎么发生的"这种句式。
3. 结尾用一句自然的反问引导学生继续探索。告诉他下一块代码
   是什么、为什么值得看、跟刚才看的有什么关系。
4. 反问必须是完整的一句话，像老师指路，让学生说"好"就能继续。
   不要给选项列表，不要给按钮。

## 反问示例
"看懂了 run_turn，你可能会好奇：用户消息最终是怎么到达
DeepSeek 的？中间经过了什么处理？要不要我打开 adapter.respond，
看看 LLM 调用那一层是怎么封装的？"
```

### 5.2 方向切换处理

当用户说"我想看 XXX"时，系统调用 LLM：
- 输入：用户意图 + 调用图索引（当前节点周围 1-2 层的边）
- 输出：匹配到的目标节点 + 解释为什么跳到这里 + 代码讲解 + 反问
- 降级：调用图直接匹配 `function_name` 或 `file_path` 查找

---

## 6. 后端 API 改动

### 6.1 新增端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/codetutor/start` | 进入领域，返回概览消息 |
| `POST` | `/api/codetutor/message` | 发送用户消息，返回导游回复（含代码引用） |

### 6.2 请求/响应模型

**POST /api/codetutor/start**

Request: `{ "domain_id": "agent" }`

Response:
```json
{
  "message": {
    "role": "tutor",
    "content": "Agent 循环模块有 3 个核心环节...要不要打开看看？",
    "code_ref": null
  },
  "session_id": "abc123"
}
```

**POST /api/codetutor/message**

Request:
```json
{
  "session_id": "abc123",
  "message": "好，带我去看",
  "history": [ ... ]
}
```

Response:
```json
{
  "message": {
    "role": "tutor",
    "content": "这段代码在 agent_loop.py 第 82-145 行...要不要继续往下看？",
    "code_ref": {
      "file_path": "src/agentcli/agent_loop.py",
      "line_start": 82,
      "line_end": 145,
      "graph_node_id": "src/agentcli/agent_loop.py::AgentLoop.run_turn"
    }
  }
}
```

### 6.3 现有端点保留

- `GET /api/storylines` — 保留，用于领域列表展示
- `GET /api/storylines/{id}/enhance` — 保留，可选用于后台预生成
- `POST /api/storylines/generate` — 保留

---

## 7. 前端组件改动

| 组件 | 操作 | 说明 |
|------|------|------|
| `CodeReadingPanel.tsx` | 重写 | 从幻灯片模式改为对话模式 |
| `CodeTutorChat.tsx` | 新增 | 对话消息流 + 面包屑 + 分支管理 + 输入框 |
| `MessageBubble.tsx` | 新增 | 单条消息气泡（系统讲解 / 用户回应） |
| `StorylineDiscovery.tsx` | 保留简化 | 只展示领域列表，点击进入对话 |
| `StorylineReader.tsx` | 废弃 | 被 CodeTutorChat 取代 |
| `StorylineComplete.tsx` | 废弃 | 对话无"完成"概念 |
| `NarrativeCards.tsx` | 废弃 | 被对话气泡取代 |
| `NodeQA.tsx` | 合并 | 输入框内置在 CodeTutorChat 底部 |
| `types.ts` | 扩展 | 新增 TutorMessage、TutorSession 类型 |
| `useSSEEnhancement.ts` | 保留 | 可选用于流式输出 |
| `api/client.ts` | 扩展 | 新增 `startTutorSession`、`sendTutorMessage` |

---

## 8. 不变的部分

- Monaco 编辑器 + 蓝色高亮逻辑
- 文件树
- 分析 Tab（Agent 问答）
- 导览 Tab
- graph.py、cache.py
- `discover_storylines` 阶段1（领域分析）
- FALLBACK_STAGE1_DOMAINS

---

## 9. 验证清单

1. TypeScript `tsc --noEmit` 零错误
2. 后端 `python -m pytest tests/ -v` 全过
3. 点击领域 → 显示概览消息 → 用户说"好" → 打开代码 + 讲解 + 反问
4. 用户说"换成XXX" → 系统切换方向 → 打开新代码 + 新分支
5. 面包屑可点击回退 → 旧分支变灰 → 新分支追加
6. 自由提问不影响当前路径
7. Vite 构建成功
