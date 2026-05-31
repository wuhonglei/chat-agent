from app.mcp.tool_naming import is_llm_tool
from app.schemas.llm import (
    ToolMessage,
    ToolResultMessage,
    ToolUseMessage,
)


def extract_tool_call_names(output_messages: list[ToolMessage]) -> list[str]:
    """
    从收集的工具调用消息中提取工具名称列表

    Args:
        output_messages: 工具调用消息列表

    Returns:
        list[str]: 工具名称列表（LLM 可见名，带 server 前缀）
    """
    tool_names = []
    for message in output_messages:
        if isinstance(message, ToolUseMessage) and message.tool_calls:
            for tool_call in message.tool_calls:
                tool_names.append(tool_call.function.name)
    return tool_names


def count_tool_calls(output_messages: list[ToolMessage]) -> int:
    """
    统计工具调用结果消息的数量

    Args:
        output_messages: 工具调用消息列表

    Returns:
        int: 工具调用结果消息的数量
    """
    return len([m for m in output_messages if isinstance(m, ToolResultMessage)])


def has_tool_been_called(
    specs: list[tuple[str, str]],
    tool_call_messages: list[ToolMessage],
) -> bool:
    """
    Check if any tool has been called.

    Each spec is ``(server_name, bare_tool_name)``; matches LLM-prefixed names.
    """
    tool_call_names = extract_tool_call_names(tool_call_messages)
    return any(
        is_llm_tool(name, server, bare)
        for name in tool_call_names
        for server, bare in specs
    )
