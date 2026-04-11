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


def format_tool_use_message(
    message: ToolUseMessage | dict[str, Any],
    clear_reasoning_content: bool = True,
) -> dict[str, Any]:
    return chat_protocol.format_tool_use_message(
        message,
        clear_reasoning_content=clear_reasoning_content,
    )


def format_tool_result_message(
    message: ToolResultMessage | dict[str, Any],
) -> dict[str, Any]:
    return chat_protocol.format_tool_result_message(message)


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
    if not last_user_message:
        return

    current_content = last_user_message.get("content")
    if isinstance(current_content, list):
        for part in current_content:
            if (
                isinstance(part, dict)
                and part.get("type") == "text"
                and isinstance(part.get("text"), str)
            ):
                part["text"] = new_content
                return
        # 没有 text 分段时补一个，保留已有图片分段
        current_content.insert(0, {"type": "text", "text": new_content})
        return

    last_user_message["content"] = new_content
