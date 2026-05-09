# DeepSeek 真实接入实现计划

> **给执行型 Agent 的要求：** 实施本计划时，必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，并按任务逐项推进。步骤使用复选框 `- [ ]` 语法跟踪。

**目标：** 将当前基于 `DemoAdapter` 的源码阅读助手升级为可通过 DeepSeek OpenAI 兼容接口进行真实推理和工具调用的版本。

**架构：** 保留当前 `Runtime -> AgentLoop -> Tools` 主骨架，把 `DemoAdapter` 升级为 `DeepSeekOpenAIAdapter`。Adapter 负责与 `https://api.deepseek.com` 通信，并把模型的 tool call 翻译成当前主循环可执行的本地工具调用。

**技术栈：** Python 3.12、OpenAI Python SDK、Typer、Pydantic、Pytest

---

## 任务拆分

### 任务 1：补 Runtime 的 LLM 配置
- 从环境变量读取 `DEEPSEEK_API_KEY`、`DEEPSEEK_MODEL`、`DEEPSEEK_BASE_URL`
- 给 `RuntimeState` 增加 `llm` 配置
- 保持无 Key 时也能构建 Runtime，但在真正创建 Adapter 时再报错

### 任务 2：把工具定义升级为真实 function schema
- 为 `search_files`、`grep_text`、`read_file`、`save_note` 增加 JSON Schema 参数定义
- 让 `AgentLoop` 输出 OpenAI-compatible `tools` 数组

### 任务 3：实现 DeepSeekOpenAIAdapter
- 引入 `openai` SDK
- 使用 `OpenAI(api_key=..., base_url=...)`
- 实现 `chat.completions.create(...)`
- 支持返回最终回答和单个 tool call

### 任务 4：调整主循环消息格式
- 在工具调用回合中，追加 assistant tool_call message
- 追加 tool result message，并带 `tool_call_id`
- 让后续回合能被 DeepSeek 正确续上

### 任务 5：接通 CLI 与错误提示
- `build_adapter()` 默认构建 `DeepSeekOpenAIAdapter`
- 若缺少 `DEEPSEEK_API_KEY`，给出明确错误
- README 增加真实接入说明

### 任务 6：补测试并完成验证
- 增加 adapter 单元测试
- 增加 CLI 缺少 API Key 的测试
- 跑完整测试集

## 验证目标

- 没有 `DEEPSEEK_API_KEY` 时，CLI 给出明确报错
- 有 Key 时，`ask` 能基于真实仓库内容回答
- `note` 能基于真实回答写入 Markdown
- 所有自动化测试通过
