"""消息处理工具函数"""

from typing import Any

from toolz import dissoc, get

from app.schemas.chat import ChatMessageItem
from app.schemas.llm import (
    AssistantToolCallMessage,
    ToolCallMessage,
    ToolCallResultMessage,
)
from app.utils.common import normalize_to_dict


def clear_reasoning_content_from_history(
    history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    清除历史消息中的 reasoning_content 字段

    Args:
        history: 历史消息列表

    Returns:
        清除 reasoning_content 字段后的消息字典
    """
    return dissoc(history, "reasoning_content")


def format_assistant_tool_call_message(
    message: AssistantToolCallMessage | dict, clear_reasoning_content: bool = True
) -> dict[str, Any]:
    """
    格式化 AssistantToolCallMessage 为 LLM API 所需的格式
    只保留 API 需要的字段：role, tool_calls
    过滤掉额外的字段：reasoning_content

    Args:
        message: AssistantToolCallMessage 对象
        clear_reasoning_content: 如果为 True，则清除 reasoning_content 字段；如果为 False，则保留
    """
    message = normalize_to_dict(message)
    return {
        "role": get("role", message),
        "content": get("content", message, None),
        "reasoning_content": None
        if clear_reasoning_content
        else get("reasoning_content", message, None),
        "tool_calls": get("tool_calls", message),
    }


def format_tool_call_result_message(
    message: ToolCallResultMessage | dict,
) -> dict[str, Any]:
    """
    格式化 ToolCallResultMessage 为 LLM API 所需的格式
    只保留 API 需要的字段：role, tool_call_id, content
    过滤掉额外的字段：token_count, duration, is_error

    Args:
        message: ToolCallResultMessage 对象

    Returns:
        格式化后的消息字典，只包含 API 需要的字段
    """
    message = normalize_to_dict(message)
    return {
        "role": get("role", message),
        "tool_call_id": get("tool_call_id", message),
        "content": get("content", message, ""),
    }


def format_tool_call_message_for_llm(
    message: ToolCallMessage | dict, clear_reasoning_content: bool = False
) -> dict[str, Any]:
    """
    格式化工具调用消息为 LLM API 所需的格式
    """
    message = normalize_to_dict(message)
    is_assistant_message = get("role", message) == "assistant"
    if is_assistant_message:
        return format_assistant_tool_call_message(message, clear_reasoning_content)
    else:
        return format_tool_call_result_message(message)


def format_tool_call_messages_for_llm(
    messages: list[ToolCallMessage | dict], clear_reasoning_content: bool = False
) -> list[dict[str, Any]]:
    """
    格式化工具调用消息为 LLM API 所需的格式
    """
    new_messages = []
    for _message in messages:
        new_messages.append(
            format_tool_call_message_for_llm(_message, clear_reasoning_content)
        )
    return new_messages


def format_chat_message_for_llm(
    message: ChatMessageItem | dict,
    keep_reasoning: bool = False,
) -> dict[str, Any]:
    """
    格式化聊天消息为 LLM API 所需的格式（仅用户/助手消息）
    """
    message_dict = normalize_to_dict(message)
    role = get("role", message_dict)
    content = get("content", message_dict, "")
    payload: dict[str, Any] = {"role": role, "content": content}
    reasoning = get("reasoning", message_dict, None)
    if keep_reasoning and role == "assistant" and reasoning:
        payload["reasoning"] = reasoning
    return payload


def find_last_user_message(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    """
    查找最后一个用户消息
    """
    for message in reversed(messages):
        if message.get("role") == "user":
            return message
    return None
