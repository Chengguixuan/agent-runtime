from typing import Any, Callable, Dict, List, Optional


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, dict] = {}

    def register(
        self,
        name: str,
        description: str,
        schema: dict,
        handler: Callable[[dict, Any], str],
    ):
        self._tools[name] = {
            "name": name,
            "description": description,
            "schema": schema,
            "handler": handler,
        }

    def get_openai_schemas(self) -> List[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["schema"],
                },
            }
            for tool in self._tools.values()
        ]

    def execute(self, name: str, args: dict, session) -> str:
        if name not in self._tools:
            return f"错误：工具 '{name}' 不存在"

        try:
            return self._tools[name]["handler"](args, session)
        except Exception as e:
            return f"工具执行出错：{e}"
