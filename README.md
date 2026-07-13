# Agent Runtime

这是一个从零实现的 Agent Runtime，支持工具调用、多会话隔离、上下文管理和 JSON 持久化。

## 运行方式

```bash
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY
python main.py
```

## 系统设计

**核心架构**：ReAct 模式。每轮循环 LLM 返回 `tool_calls` 或最终答案——有工具调用则执行后把结果追加到消息历史并继续循环，无工具调用则返回最终答案。最多循环 5 次防止死循环。

**Session 管理**：每个会话通过 `SessionData` 维护独立的 `messages` 和 `todo_list`，`SessionManager` 负责 JSON 持久化到 `sessions.json`。

**工具注册**：`ToolRegistry` 以 OpenAI function calling 格式管理工具，目前注册了 calculator（数学计算）、search（搜索 mock）、todo（待办增删查）三个工具。

**Context 管理**：`ContextManager` 按 `role == "user"` 的消息数统计轮次，超限时截断保留最近 N 轮及其关联的 assistant/tool 消息。

**日志**：5 个日志函数覆盖 LLM 调用、工具调用、工具结果、压缩、错误，所有日志带时间戳。

## Memory 的召回时机与放置方式

**当前实现**：记忆放在每个会话的 `messages` 列表中，通过 Session 隔离。每条消息按 OpenAI 对话格式存储（`role` + `content`，工具调用额外包含 `tool_calls` / `tool_call_id`）。

**召回时机**：每次 LLM 调用时，当前会话的所有历史消息（包括 user、assistant、tool）作为 `messages` 参数一次性传入 API，LLM 从完整上下文中理解对话历史。

**放置方式**：工具结果和 assistant 回复按时间顺序追加到 `messages` 列表末尾。当轮次超过 `max_turns` 时，`ContextManager` 从最早的消息开始截断，只保留最近 N 轮 user 消息及其后续的 assistant/tool 消息，确保每条被保留的 user 消息的上下文完整。

## 项目结构

```
agent/
├── main.py              # 交互入口：初始化所有组件，命令行会话管理和对话循环
├── runtime.py           # AgentRuntime：ReAct 循环核心，工具调用调度与异常处理
├── session.py           # SessionData + SessionManager：多会话数据模型与 JSON 持久化
├── context.py           # ContextManager：按 user 轮次计数，超限自动截断压缩
├── logger.py            # 5 个日志函数：LLM_CALL / TOOL_CALL / TOOL_RESULT / COMPRESS / ERROR
├── requirements.txt     # 依赖：openai、python-dotenv
├── .env.example         # 环境变量模板
└── tools/
    ├── __init__.py
    ├── registry.py      # ToolRegistry：工具注册与 OpenAI function calling schema 生成
    ├── calculator.py    # 数学计算工具（安全 eval，支持 math 模块函数）
    ├── search.py        # 搜索工具（返回固定 mock 结果）
    └── todo.py          # 待办管理工具（add / list / delete，读写 session.todo_list）
```
