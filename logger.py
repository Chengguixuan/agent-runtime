from datetime import datetime


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _truncate(text: str, max_len: int = 200) -> str:
    s = str(text)
    return s if len(s) <= max_len else s[:max_len] + "..."


def log_tool_call(session_id: str, tool_name: str, args: dict):
    print(f"[{_now()}] TOOL_CALL {session_id} {tool_name} {args}")


def log_tool_result(session_id: str, tool_name: str, result: str):
    print(f"[{_now()}] TOOL_RESULT {session_id} {tool_name} {_truncate(result)}")


def log_llm_call(session_id: str, message_count: int):
    print(f"[{_now()}] LLM_CALL {session_id} messages={message_count}")


def log_compression(session_id: str, old_count: int, new_count: int):
    print(f"[{_now()}] COMPRESS {session_id} 轮次从 {old_count} -> {new_count}")


def log_error(session_id: str, error_msg: str):
    print(f"[{_now()}] ERROR {session_id} {error_msg}")
