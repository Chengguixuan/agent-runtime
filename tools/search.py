def search_handler(args: dict, session) -> str:
    query = args.get("query", "")
    if not query:
        return "错误：请提供搜索关键词"

    return (
        "搜索结果：\n"
        "1. 今日AI大会在京召开\n"
        "2. 股市小幅上涨0.5%\n"
        "3. 多地发布高温预警"
    )
