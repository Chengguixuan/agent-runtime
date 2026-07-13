import math


def calculator_handler(args: dict, session) -> str:
    expression = args.get("expression", "")
    if not expression:
        return "错误：请提供数学表达式"

    # 构建安全的计算环境：只允许数学运算符和 math 模块函数
    safe_globals = {"__builtins__": {}}
    safe_locals = {
        k: getattr(math, k)
        for k in dir(math)
        if not k.startswith("_")
    }

    try:
        result = eval(expression, safe_globals, safe_locals)
        return str(result)
    except Exception as e:
        return f"计算错误：{e}"
