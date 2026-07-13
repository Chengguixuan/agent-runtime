from typing import TYPE_CHECKING

import logger

if TYPE_CHECKING:
    from session import SessionData


class ContextManager:
    def __init__(self, max_turns: int = 20):
        self.max_turns = max_turns

    def compress_if_needed(self, session: "SessionData") -> bool:
        # 找到所有 user 消息的索引
        user_indices = [
            i for i, msg in enumerate(session.messages)
            if msg.get("role") == "user"
        ]
        turns = len(user_indices)

        if turns <= self.max_turns:
            return False

        # 保留最近 max_turns 个 user 消息及其关联的所有后续消息
        keep_from = user_indices[-self.max_turns]
        old_count = turns
        session.messages = session.messages[keep_from:]
        new_count = self.max_turns

        logger.log_compression(session.session_id, old_count, new_count)
        return True
