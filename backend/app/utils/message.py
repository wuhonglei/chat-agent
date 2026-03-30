"""消息处理工具函数"""

from collections.abc import Sequence
from typing import Any

from toolz import dissoc, get

from app.schemas.chat import ChatMessageItemWithToolCalls
from app.schemas.llm import (
    ToolMessage,
    ToolResultMessage,
    ToolUseMessage,
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
    return [dissoc(d, "reasoning_content") for d in history]


def format_assistant_tool_call_message(
    message: ToolUseMessage | dict[str, Any],
    clear_reasoning_content: bool = True,
) -> dict[str, Any]:
    """
    格式化 ToolUseMessage 为 LLM API 所需的格式
    只保留 API 需要的字段：role, tool_calls
    过滤掉额外的字段：reasoning_content

    Args:
        message: ToolUseMessage 对象
        clear_reasoning_content: 如果为 True，则清除 reasoning_content 字段；如果为 False，则保留
    """
    message = normalize_to_dict(message)
    result: dict[str, Any] = {
        "role": get("role", message),
        "content": get("content", message, None),
        "reasoning_content": None
        if clear_reasoning_content
        else get("reasoning_content", message, None),
        "tool_calls": get("tool_calls", message),
    }
    return result


def format_tool_call_result_message(
    message: ToolResultMessage | dict[str, Any],
) -> dict[str, Any]:
    """
    格式化 ToolResultMessage 为 LLM API 所需的格式
    只保留 API 需要的字段：role, tool_call_id, content
    过滤掉额外的字段：token_count, is_error（及历史 JSON 中的 duration 等业务字段）

    Args:
        message: ToolResultMessage 对象

    Returns:
        格式化后的消息字典，只包含 API 需要的字段
    """
    message = normalize_to_dict(message)
    result: dict[str, Any] = {
        "role": get("role", message),
        "tool_call_id": get("tool_call_id", message),
        "content": get("content", message, ""),
    }
    return result


def format_tool_call_message_for_llm(
    message: ToolMessage | dict[str, Any],
    clear_reasoning_content: bool = False,
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
    messages: Sequence[ToolMessage | dict[str, Any]],
    clear_reasoning_content: bool = False,
) -> list[dict[str, Any]]:
    """
    格式化工具调用消息为 LLM API 所需的格式
    """
    new_messages: list[dict[str, Any]] = []
    for _message in messages:
        new_messages.append(
            format_tool_call_message_for_llm(_message, clear_reasoning_content)
        )
    return new_messages


def filter_tool_call_messages(
    tool_call_messages: list[ToolMessage],
) -> list[ToolMessage]:
    """过滤工具调用消息，只保留成功的、成对的 assistant+tool 调用。

    第一步：收集所有有效的 tool_call_id（从成功的 ToolResultMessage）
    第二步：收集 assistant 消息中存在的、且有成功结果的 tool_call_id
    第三步：只保留 is_error=False 且有对应 assistant 的 ToolResultMessage，
           以及 tool_calls 中 id 在 assistant_tool_call_ids 内的 ToolUseMessage

    Args:
        tool_call_messages: 原始工具调用相关消息（assistant + tool 交替）

    Returns:
        过滤后的消息列表，保证 assistant 与 tool 成对且无错误
    """
    if not tool_call_messages:
        return []

    # 第一步：收集所有有效的 tool_call_id（从成功的 ToolResultMessage）
    valid_tool_call_ids = set()
    for message in tool_call_messages:
        if isinstance(message, ToolResultMessage) and not message.is_error:
            valid_tool_call_ids.add(message.tool_call_id)

    # 第二步：收集 assistant 消息中实际存在的 tool_call_id（只保留那些有成功结果的）
    assistant_tool_call_ids = set()
    for message in tool_call_messages:
        if isinstance(message, ToolUseMessage):
            for tool_call in message.tool_calls or []:
                if tool_call.id in valid_tool_call_ids:
                    assistant_tool_call_ids.add(tool_call.id)

    # 第三步：只保留正确的工具调用（ToolResultMessage is_error=False 且有对应的 assistant 消息）
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
    """获取 assistant 工具调用消息"""
    return [
        message for message in tool_call_messages if isinstance(message, ToolUseMessage)
    ]


def get_tool_call_result_messages(
    tool_call_messages: list[ToolMessage],
) -> list[ToolResultMessage]:
    """获取 tool 工具调用消息"""
    return [
        message
        for message in tool_call_messages
        if isinstance(message, ToolResultMessage)
    ]


def format_chat_message_for_llm(
    message: ChatMessageItemWithToolCalls,
    clear_reasoning_content: bool = True,
) -> dict[str, Any]:
    """
    格式化聊天消息为 LLM API 所需的格式（仅用户/助手消息）
    """
    if isinstance(message, ToolMessage):
        return format_tool_call_message_for_llm(message)

    message_dict = normalize_to_dict(message)
    role = get("role", message_dict)
    content = get("content", message_dict, "")
    reasoning = get("reasoning", message_dict, None)
    payload: dict[str, Any] = {"role": role, "content": content, "reasoning": reasoning}
    if clear_reasoning_content:
        del payload["reasoning"]

    return payload


def find_last_user_message(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    """
    查找最后一个用户消息
    """
    for message in reversed(messages):
        if message.get("role") == "user":
            return message
    return None


def update_last_user_message(messages: list[dict[str, Any]], new_content: str) -> None:
    """
    更新最后一个用户消息
    """
    last_user_message = find_last_user_message(messages)
    if last_user_message:
        last_user_message["content"] = new_content
