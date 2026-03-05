import json
from typing import Any

from openai.types.chat import ChatCompletionMessageFunctionToolCall

from app.schemas.llm import (
    ToolCallMessage,
    ToolResultMessage,
    ToolUseMessage,
)
from app.utils.message import (
    get_assistant_tool_call_messages,
    get_tool_call_result_messages,
)


def get_component_data(
    component_tool_call_messages: list[ToolCallMessage],
    component_schema: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """获取组件数据"""
    if not component_tool_call_messages:
        return []

    component_data: list[dict[str, Any]] = []
    tool_call_by_id: dict[str, ChatCompletionMessageFunctionToolCall] = {}
    for msg in component_tool_call_messages:
        if isinstance(msg, ToolUseMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_call_by_id[tc.id] = tc
    for msg in component_tool_call_messages:
        if isinstance(msg, ToolResultMessage) and not msg.is_error:
            tool_call = tool_call_by_id.get(msg.tool_call_id)
            if tool_call:
                component_name = tool_call.function.name.replace(
                    "generate_component_", ""
                )
                component_description = (
                    component_schema.get(component_name, {}).get("description") or ""
                )
                props = json.loads(tool_call.function.arguments)
                component_json_data = {
                    "component_name": component_name,
                    "props": props,
                }
                component_json_str = json.dumps(
                    component_json_data, indent=2, ensure_ascii=False
                )
                component_dict = {
                    "component_name": component_name,
                    "component_description": component_description,
                    "component_json_str": component_json_str,
                }
                component_data.append(component_dict)

    if not component_data:
        return []

    return component_data


def get_mcp_tool_items(
    mcp_tool_call_messages: list[ToolCallMessage],
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
