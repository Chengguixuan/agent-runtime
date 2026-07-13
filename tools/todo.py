def todo_handler(args: dict, session) -> str:
    action = args.get("action", "")
    content = args.get("content", "")

    if action == "add":
        if not content:
            return "错误：请提供待办内容"
        session.todo_list.append(content)
        return f"已添加待办：{content}"

    elif action == "list":
        if not session.todo_list:
            return "暂无待办"
        lines = [f"{i + 1}. {item}" for i, item in enumerate(session.todo_list)]
        return "待办列表：\n" + "\n".join(lines)

    elif action == "delete":
        if not content:
            return "错误：请提供要删除的待办内容"
        if content in session.todo_list:
            session.todo_list.remove(content)
            return f"已删除待办：{content}"
        else:
            return f"未找到：{content}"

    else:
        return f"错误：不支持的操作 '{action}'，支持 add / list / delete"
