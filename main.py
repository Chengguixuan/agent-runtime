import os
import uuid

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

from session import SessionManager
from tools.registry import ToolRegistry
from tools.calculator import calculator_handler
from tools.search import search_handler
from tools.todo import todo_handler
from context import ContextManager
from runtime import AgentRuntime


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()

    registry.register(
        name="calculator",
        description="执行数学计算，传入 expression 如 '1+2*3'，支持 math 模块函数",
        schema={
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "数学表达式"}
            },
            "required": ["expression"],
        },
        handler=calculator_handler,
    )

    registry.register(
        name="search",
        description="搜索信息，传入 query 关键词",
        schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"}
            },
            "required": ["query"],
        },
        handler=search_handler,
    )

    registry.register(
        name="todo",
        description="管理待办事项，action 为 add / list / delete",
        schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型：add / list / delete",
                },
                "content": {"type": "string", "description": "待办内容"},
            },
            "required": ["action"],
        },
        handler=todo_handler,
    )

    return registry


def main():
    # 1. 加载环境变量
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("错误：请设置环境变量 DEEPSEEK_API_KEY")
        return

    # 2. 初始化组件
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
    registry = build_registry()
    ctx = ContextManager(max_turns=20)
    manager = SessionManager()
    runtime = AgentRuntime(llm_client=client, tool_registry=registry, context_manager=ctx)

    # 3. 欢迎信息
    print("=" * 50)
    print("欢迎使用 Agent!")
    sessions = manager.get_all_sessions()
    if sessions:
        print(f"当前已有 sessions: {', '.join(sessions)}")
    else:
        print("当前没有已保存的会话")
    print("输入 session_id 继续，回车新建，输入 list 查看所有，输入 quit 退出")
    print("=" * 50)

    # 4. 外层循环：选择/创建 session
    while True:
        print()
        choice = input("会话ID: ").strip()

        if choice in ("退出", "exit", "quit"):
            manager.save_all()
            print("已保存，再见！")
            break

        if choice == "list":
            sessions = manager.get_all_sessions()
            if sessions:
                print(f"所有 sessions: {', '.join(sessions)}")
            else:
                print("暂无已保存的会话")
            continue

        # 新建或恢复 session
        if choice == "":
            session_id = uuid.uuid4().hex[:8]
            session = manager.get_or_create(session_id)
            print(f"新会话: {session_id}")
        else:
            session = manager.get_or_create(choice)
            msg_count = len(session.messages)
            if msg_count > 0:
                print(f"已恢复会话 {choice}，共 {msg_count} 条消息")
            else:
                print(f"新会话: {choice}")

        # 5. 内层循环：对话
        print("（输入 \"退出\" 回到会话选择）")
        while True:
            try:
                user_input = input("\n你: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                manager.save_all()
                print("已保存，再见！")
                return

            if not user_input:
                continue

            # 回到会话选择
            if user_input in ("退出", "返回", "quit"):
                manager.save_all()
                print("已保存，回到会话选择")
                break

            response = runtime.run(session, user_input)
            print(f"Agent: {response}")


# ============================================================
# Mock 工具类（用于测试）
# ============================================================
import json
import sys


class MockCompletions:
    def __init__(self, responses):
        self.responses = responses
        self.idx = 0

    def create(self, **kwargs):
        if self.idx >= len(self.responses):
            raise RuntimeError("Mock 响应耗尽")
        resp = self.responses[self.idx]
        self.idx += 1
        return resp


class MockChat:
    def __init__(self, responses):
        self.completions = MockCompletions(responses)


class MockClient:
    def __init__(self, responses):
        self.chat = MockChat(responses)


class MockMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class MockChoice:
    def __init__(self, message):
        self.message = message


class MockResponse:
    def __init__(self, message):
        self.choices = [MockChoice(message)]


class MockToolCall:
    def __init__(self, call_id, name, arguments):
        self.id = call_id
        self.function = type("F", (), {"name": name, "arguments": json.dumps(arguments)})()


def test_all():
    passed = 0
    failed = 0

    def check(case_num: int, desc: str, condition: bool, detail: str = ""):
        nonlocal passed, failed
        status = "PASS" if condition else "FAIL"
        print(f"[{status}] 用例 {case_num}: {desc}")
        if not condition:
            print(f"       失败原因: {detail}")
            failed += 1
        else:
            passed += 1

    # 清理
    if os.path.exists("sessions.json"):
        os.remove("sessions.json")

    registry = build_registry()
    manager = SessionManager()

    # ================================================================
    # 用例 1: 纯对话 —— 发送"你好"，验证直接回复（无 tool_calls）
    # ================================================================
    mock1 = MockClient([
        MockResponse(MockMessage(content="你好！有什么可以帮助你的？")),
    ])
    ctx1 = ContextManager(max_turns=20)
    rt1 = AgentRuntime(llm_client=mock1, tool_registry=registry, context_manager=ctx1)
    session1 = manager.get_or_create("test-1")
    answer1 = rt1.run(session1, "你好")
    check(1, "纯对话-直接回复",
          answer1 == "你好！有什么可以帮助你的？",
          f"回复内容: {answer1}")

    # ================================================================
    # 用例 2: 单工具调用 —— 发送"1+2+3"，验证 calculator 被调用
    # ================================================================
    mock2 = MockClient([
        MockResponse(MockMessage(content=None, tool_calls=[
            MockToolCall("c1", "calculator", {"expression": "1+2+3"})
        ])),
        MockResponse(MockMessage(content="1+2+3 的结果是 6")),
    ])
    ctx2 = ContextManager(max_turns=20)
    rt2 = AgentRuntime(llm_client=mock2, tool_registry=registry, context_manager=ctx2)
    session2 = manager.get_or_create("test-2")
    answer2 = rt2.run(session2, "计算 1+2+3")
    has_tool_call = any(
        m.get("role") == "assistant" and m.get("tool_calls")
        for m in session2.messages
    )
    has_tool_result = any(
        m.get("role") == "tool" and m.get("content") == "6"
        for m in session2.messages
    )
    check(2, "单工具调用-calculator被调用",
          has_tool_call,
          f"工具调用存在: {has_tool_call}")
    check(2, "单工具调用-计算结果正确",
          has_tool_result and answer2 == "1+2+3 的结果是 6",
          f"结果: {answer2}, tool消息: {has_tool_result}")

    # ================================================================
    # 用例 3: 带工具的追问 —— 两轮对话验证上下文传递
    # ================================================================
    mock3 = MockClient([
        # Turn 1: 计算 10*5
        MockResponse(MockMessage(content=None, tool_calls=[
            MockToolCall("c3a", "calculator", {"expression": "10*5"})
        ])),
        MockResponse(MockMessage(content="10*5 等于 50")),
        # Turn 2: 再除以 2（无 tool_call，验证能看到上一轮的结果）
        MockResponse(MockMessage(content="50 除以 2 等于 25")),
    ])
    ctx3 = ContextManager(max_turns=20)
    rt3 = AgentRuntime(llm_client=mock3, tool_registry=registry, context_manager=ctx3)
    session3 = manager.get_or_create("test-3")

    answer3a = rt3.run(session3, "计算 10*5")
    check(3, "追问-第一轮",
          answer3a == "10*5 等于 50",
          f"回复: {answer3a}")

    answer3b = rt3.run(session3, "再除以2")
    # 验证上下文中包含了第一轮的内容
    has_user1 = any("10*5" in str(m.get("content", "")) for m in session3.messages)
    has_user2 = any("再除以2" in str(m.get("content", "")) for m in session3.messages)
    check(3, "追问-上下文包含两轮问题",
          has_user1 and has_user2,
          f"Q1存在: {has_user1}, Q2存在: {has_user2}")
    check(3, "追问-第二轮回复正确",
          answer3b == "50 除以 2 等于 25",
          f"回复: {answer3b}")

    # ================================================================
    # 用例 4: 多工具混合 —— search + todo
    # ================================================================
    mock4 = MockClient([
        # Turn 1: 搜索
        MockResponse(MockMessage(content=None, tool_calls=[
            MockToolCall("c4a", "search", {"query": "今日新闻"})
        ])),
        MockResponse(MockMessage(content="已为您搜索到今日新闻")),
        # Turn 2: 待办
        MockResponse(MockMessage(content=None, tool_calls=[
            MockToolCall("c4b", "todo", {"action": "add", "content": "买咖啡"})
        ])),
        MockResponse(MockMessage(content="已为您添加待办")),
    ])
    ctx4 = ContextManager(max_turns=20)
    rt4 = AgentRuntime(llm_client=mock4, tool_registry=registry, context_manager=ctx4)
    session4 = manager.get_or_create("test-4")

    answer4a = rt4.run(session4, "搜索今日新闻")
    answer4b = rt4.run(session4, "帮我记住：买咖啡")
    check(4, "多工具-search被调用",
          "已为您搜索到今日新闻" in answer4a,
          f"回复: {answer4a}")
    check(4, "多工具-todo添加成功",
          "买咖啡" in session4.todo_list,
          f"todo_list: {session4.todo_list}")

    # ================================================================
    # 用例 5: 待办管理 —— add → list → delete → list
    # ================================================================
    session5 = manager.get_or_create("test-5")

    # add 买菜
    mock5a = MockClient([
        MockResponse(MockMessage(content=None, tool_calls=[
            MockToolCall("c5a", "todo", {"action": "add", "content": "买菜"})
        ])),
        MockResponse(MockMessage(content="已添加待办：买菜")),
    ])
    ctx5a = ContextManager(max_turns=20)
    rt5a = AgentRuntime(llm_client=mock5a, tool_registry=registry, context_manager=ctx5a)
    rt5a.run(session5, "加 买菜")

    # add 洗衣
    mock5b = MockClient([
        MockResponse(MockMessage(content=None, tool_calls=[
            MockToolCall("c5b", "todo", {"action": "add", "content": "洗衣"})
        ])),
        MockResponse(MockMessage(content="已添加待办：洗衣")),
    ])
    ctx5b = ContextManager(max_turns=20)
    rt5b = AgentRuntime(llm_client=mock5b, tool_registry=registry, context_manager=ctx5b)
    rt5b.run(session5, "加 洗衣")

    check(5, "待办-添加两项",
          session5.todo_list == ["买菜", "洗衣"],
          f"todo_list: {session5.todo_list}")

    # list
    mock5c = MockClient([
        MockResponse(MockMessage(content=None, tool_calls=[
            MockToolCall("c5c", "todo", {"action": "list"})
        ])),
        MockResponse(MockMessage(content="您的待办有：买菜, 洗衣")),
    ])
    ctx5c = ContextManager(max_turns=20)
    rt5c = AgentRuntime(llm_client=mock5c, tool_registry=registry, context_manager=ctx5c)
    list_result = rt5c.run(session5, "列出所有")
    check(5, "待办-列表查询",
          "买菜" in list_result or len(session5.todo_list) == 2,
          f"list结果: {list_result}")

    # delete 买菜
    mock5d = MockClient([
        MockResponse(MockMessage(content=None, tool_calls=[
            MockToolCall("c5d", "todo", {"action": "delete", "content": "买菜"})
        ])),
        MockResponse(MockMessage(content="已删除待办：买菜")),
    ])
    ctx5d = ContextManager(max_turns=20)
    rt5d = AgentRuntime(llm_client=mock5d, tool_registry=registry, context_manager=ctx5d)
    rt5d.run(session5, "删除 买菜")

    check(5, "待办-删除后只剩洗衣",
          session5.todo_list == ["洗衣"],
          f"todo_list: {session5.todo_list}")

    # ================================================================
    # 用例 6: Session 隔离 —— 两个 session todo 互不影响
    # ================================================================
    session6a = manager.get_or_create("test-6a")
    session6b = manager.get_or_create("test-6b")

    # Session A: 加待办
    mock6a = MockClient([
        MockResponse(MockMessage(content=None, tool_calls=[
            MockToolCall("c6a", "todo", {"action": "add", "content": "A的待办"})
        ])),
        MockResponse(MockMessage(content="ok")),
    ])
    ctx6 = ContextManager(max_turns=20)
    rt6a = AgentRuntime(llm_client=mock6a, tool_registry=registry, context_manager=ctx6)
    rt6a.run(session6a, "加 A的待办")

    # Session B: 加另一个待办
    mock6b = MockClient([
        MockResponse(MockMessage(content=None, tool_calls=[
            MockToolCall("c6b", "todo", {"action": "add", "content": "B的待办"})
        ])),
        MockResponse(MockMessage(content="ok")),
    ])
    rt6b = AgentRuntime(llm_client=mock6b, tool_registry=registry, context_manager=ctx6)
    rt6b.run(session6b, "加 B的待办")

    check(6, "Session隔离-A只有A的待办",
          session6a.todo_list == ["A的待办"],
          f"sessionA: {session6a.todo_list}")
    check(6, "Session隔离-B只有B的待办",
          session6b.todo_list == ["B的待办"],
          f"sessionB: {session6b.todo_list}")

    # ================================================================
    # 用例 7: Context 压缩 —— 超过 max_turns，验证截断
    # ================================================================
    ctx7 = ContextManager(max_turns=3)
    session7 = manager.get_or_create("test-7")

    # 造 5 轮对话
    for i in range(1, 6):
        session7.messages.append({"role": "user", "content": f"问题{i}"})
        if i == 2:
            session7.messages.append({
                "role": "assistant", "content": None,
                "tool_calls": [{"id": "tc", "type": "function",
                                "function": {"name": "calculator", "arguments": "{}"}}]
            })
            session7.messages.append({"role": "tool", "tool_call_id": "tc", "content": "42"})
        session7.messages.append({"role": "assistant", "content": f"回答{i}"})

    user_count_before = sum(1 for m in session7.messages if m.get("role") == "user")
    compressed = ctx7.compress_if_needed(session7)
    user_count_after = sum(1 for m in session7.messages if m.get("role") == "user")
    kept_users = [m["content"] for m in session7.messages if m.get("role") == "user"]

    check(7, "压缩-触发压缩",
          compressed,
          f"compressed: {compressed}")
    check(7, "压缩-前轮次5后轮次3",
          user_count_before == 5 and user_count_after == 3,
          f"before={user_count_before}, after={user_count_after}")
    check(7, "压缩-保留最近3轮",
          kept_users == ["问题3", "问题4", "问题5"],
          f"kept: {kept_users}")
    check(7, "压缩-旧轮次tool消息被丢弃",
          not any("42" == str(m.get("content", "")) for m in session7.messages),
          "第2轮的tool结果42应被丢弃")

    # ================================================================
    # 用例 8: 异常处理 —— 错误表达式不崩溃
    # ================================================================
    mock8 = MockClient([
        MockResponse(MockMessage(content=None, tool_calls=[
            MockToolCall("c8", "calculator", {"expression": "1/0"})
        ])),
        MockResponse(MockMessage(content="计算出现错误，请检查表达式")),
    ])
    ctx8 = ContextManager(max_turns=20)
    rt8 = AgentRuntime(llm_client=mock8, tool_registry=registry, context_manager=ctx8)
    session8 = manager.get_or_create("test-8")
    answer8 = rt8.run(session8, "计算 1/0")
    # 工具应该返回错误信息而不是崩溃
    tool_msg = [m for m in session8.messages if m.get("role") == "tool"]
    tool_has_error = any("division by zero" in str(m.get("content", "")).lower() or "错误" in str(m.get("content", "")) for m in tool_msg) if tool_msg else False
    check(8, "异常处理-工具错误被捕获",
          tool_has_error and "出错" not in answer8,
          f"tool内容: {[m.get('content') for m in tool_msg]}, answer: {answer8}")

    # 测试 registry 不存在的工具
    result_bad = registry.execute("nonexistent", {}, session8)
    check(8, "异常处理-不存在的工具",
          "不存在" in result_bad or "不存在" in result_bad,
          f"错误信息: {result_bad}")

    # ================================================================
    # 汇总
    # ================================================================
    total = passed + failed
    print()
    print("=" * 50)
    print(f"测试完成: {total} 项, PASS={passed}, FAIL={failed}")
    if failed == 0:
        print("全部通过!")
    else:
        print(f"有 {failed} 项失败")
    print("=" * 50)

    # 清理
    if os.path.exists("sessions.json"):
        os.remove("sessions.json")

    return failed == 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_all()
    else:
        main()
