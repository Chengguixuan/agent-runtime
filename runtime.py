import json
from typing import TYPE_CHECKING

import logger

if TYPE_CHECKING:
    from tools.registry import ToolRegistry
    from context import ContextManager
    from session import SessionData


class AgentRuntime:
    def __init__(
        self,
        llm_client,
        tool_registry: "ToolRegistry",
        context_manager: "ContextManager",
    ):
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.context_manager = context_manager

    def run(self, session: "SessionData", user_input: str) -> str:
        # 1. 追加 user 消息
        session.messages.append({"role": "user", "content": user_input})

        # 2. 增加轮次计数
        session.turn_count += 1

        # 3. 防止死循环
        max_iterations = 5

        for _ in range(max_iterations):
            try:
                # a. 记录 LLM 调用
                logger.log_llm_call(session.session_id, len(session.messages))

                # b. 调用 LLM
                response = self.llm_client.chat.completions.create(
                    model="deepseek-v4-pro",
                    messages=session.messages,
                    tools=self.tool_registry.get_openai_schemas(),
                    tool_choice="auto",
                )

                # c. 提取 message
                msg = response.choices[0].message

                # d. 处理 tool_calls
                if msg.tool_calls:
                    # 先把 assistant 消息（含 tool_calls）追加到历史
                    session.messages.append({
                        "role": "assistant",
                        "content": msg.content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in msg.tool_calls
                        ],
                    })

                    # 执行每个工具调用
                    for tc in msg.tool_calls:
                        tool_name = tc.function.name
                        try:
                            args = json.loads(tc.function.arguments)
                        except json.JSONDecodeError:
                            args = {}

                        logger.log_tool_call(session.session_id, tool_name, args)
                        result = self.tool_registry.execute(tool_name, args, session)
                        logger.log_tool_result(session.session_id, tool_name, result)

                        # 追加 tool 消息
                        session.messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result,
                        })

                    # 继续循环，让 LLM 看到工具结果
                    continue

                # e. 没有 tool_calls，提取最终答案
                final_answer = msg.content or ""
                session.messages.append({
                    "role": "assistant",
                    "content": final_answer,
                })

                # 压缩
                self.context_manager.compress_if_needed(session)

                return final_answer

            except Exception as e:
                logger.log_error(session.session_id, str(e))
                return f"运行出错：{e}"

        # 5. 超过最大循环次数
        return "达到最大循环次数，请重试"
