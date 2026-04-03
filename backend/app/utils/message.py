"""消息处理工具函数"""

from typing import Any

from toolz import dissoc

from app.protocols import chat_messages as chat_protocol
from app.schemas.llm import ToolMessage, ToolResultMessage, ToolUseMessage


def clear_reasoning_content_from_history(
    history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """清除历史消息中的 reasoning_content 字段。"""
    return [dissoc(d, "reasoning_content") for d in history]


def format_assistant_tool_call_message(
    message: ToolUseMessage | dict[str, Any],
    clear_reasoning_content: bool = True,
) -> dict[str, Any]:
    return chat_protocol.format_assistant_tool_call_message(
        message,
        clear_reasoning_content=clear_reasoning_content,
    )


def format_tool_call_result_message(
    message: ToolResultMessage | dict[str, Any],
) -> dict[str, Any]:
    return chat_protocol.format_tool_call_result_message(message)


def format_tool_call_message_for_llm(
    message: ToolMessage | dict[str, Any],
    clear_reasoning_content: bool = False,
) -> dict[str, Any]:
    return chat_protocol.format_tool_call_message_for_llm(
        message,
        clear_reasoning_content=clear_reasoning_content,
    )


def format_tool_call_messages_for_llm(
    messages: list[ToolMessage | dict[str, Any]],
    clear_reasoning_content: bool = False,
) -> list[dict[str, Any]]:
    return chat_protocol.format_tool_call_messages_for_llm(
        messages,
        clear_reasoning_content=clear_reasoning_content,
    )


def format_chat_message_for_llm(
    message: Any,
    clear_reasoning_content: bool = True,
) -> dict[str, Any]:
    return chat_protocol.format_chat_message_for_llm(
        message,
        clear_reasoning_content=clear_reasoning_content,
    )


def filter_tool_call_messages(
    tool_call_messages: list[ToolMessage],
) -> list[ToolMessage]:
    """过滤工具调用消息，只保留成功的、成对的 assistant+tool 调用。"""
    if not tool_call_messages:
        return []

    valid_tool_call_ids = set()
    for message in tool_call_messages:
        if isinstance(message, ToolResultMessage) and not message.is_error:
            valid_tool_call_ids.add(message.tool_call_id)

    assistant_tool_call_ids = set()
    for message in tool_call_messages:
        if isinstance(message, ToolUseMessage):
            for tool_call in message.tool_calls or []:
                if tool_call.id in valid_tool_call_ids:
                    assistant_tool_call_ids.add(tool_call.id)

    filtered: list[ToolMessage] = []
    for message in tool_call_messages:
        if isinstance(message, ToolUseMessage):
            filtered_tool_calls = [
                tc
                for tc in (message.tool_calls or [])
                if tc.id in assistant_tool_call_ids
            ]
            if filtered_tool_calls:
                filtered.append(
                    message.model_copy(update={"tool_calls": filtered_tool_calls})
                )
        elif isinstance(message, ToolResultMessage):
            if not message.is_error and message.tool_call_id in assistant_tool_call_ids:
                filtered.append(message)
    return filtered


def get_assistant_tool_call_messages(
    tool_call_messages: list[ToolMessage],
) -> list[ToolUseMessage]:
    """获取 assistant 工具调用消息。"""
    return [
        message for message in tool_call_messages if isinstance(message, ToolUseMessage)
    ]


def get_tool_call_result_messages(
    tool_call_messages: list[ToolMessage],
) -> list[ToolResultMessage]:
    """获取 tool 工具调用消息。"""
    return [
        message
        for message in tool_call_messages
        if isinstance(message, ToolResultMessage)
    ]


def find_last_user_message(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    """查找最后一个用户消息。"""
    for message in reversed(messages):
        if message.get("role") == "user":
            return message
    return None


def update_last_user_message(messages: list[dict[str, Any]], new_content: str) -> None:
    """更新最后一个用户消息。"""
    last_user_message = find_last_user_message(messages)
    if last_user_message:
        last_user_message["content"] = new_content
