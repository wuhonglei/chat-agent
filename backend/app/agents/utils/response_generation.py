from app.schemas.llm import ToolMessage
from app.utils.message import (
    get_assistant_tool_call_messages,
    get_tool_call_result_messages,
)


def get_mcp_tool_items(
    mcp_tool_call_messages: list[ToolMessage],
) -> list[dict[str, str]]:
    """将 MCP 工具调用结果格式化为可拼接到用户消息的纯文本。
    转为「工具名 + 参数 + 返回结果」的纯文本，便于拼接到 final_user_message，
    避免向模型传入 assistant/tool 消息结构，减少模型模仿 DSML/function_calls 格式输出。
    """
    if not mcp_tool_call_messages:
        return []

    assistant_msgs = get_assistant_tool_call_messages(mcp_tool_call_messages)
    result_msgs = get_tool_call_result_messages(mcp_tool_call_messages)
    id_to_fn: dict[str, tuple[str, str]] = {}
    for message in assistant_msgs:
        for tool_call in message.tool_calls or []:
            id_to_fn[tool_call.id] = (
                tool_call.function.name,
                tool_call.function.arguments or "",
            )

    mcp_tool_items: list[dict[str, str]] = []
    for result_msg in result_msgs:
        name, args = id_to_fn.get(result_msg.tool_call_id, ("unknown", ""))
        mcp_tool_items.append(
            {
                "name": name,
                "args": args,
                "content": result_msg.content,
            }
        )

    if not mcp_tool_items:
        return []

    return mcp_tool_items
