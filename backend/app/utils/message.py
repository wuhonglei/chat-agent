"""消息处理工具函数"""
from typing import Any

from app.schemas.llm import AssistantToolCallMessage


def normalize_message_to_dict(message: Any) -> dict[str, Any]:
    """
    将消息对象转换为字典格式

    Args:
        message: 消息对象，可以是 Pydantic 模型、字典或其他对象

    Returns:
        字典格式的消息
    """
    if hasattr(message, 'model_dump'):
        return message.model_dump()
    elif isinstance(message, dict):
        return message.copy()
    else:
        return dict(message)


def ensure_reasoning_content_for_tool_calls(message_dict: dict[str, Any]) -> dict[str, Any]:
    """
    确保包含 tool_calls 的 assistant 消息有 reasoning_content 字段
    这是 deepseek-reasoner 模型的要求

    Args:
        message_dict: 消息字典

    Returns:
        处理后的消息字典
    """
    # 对于包含 tool_calls 的 assistant 消息，确保包含 reasoning_content 字段
    if message_dict.get('role') == 'assistant' and message_dict.get('tool_calls'):
        if 'reasoning_content' not in message_dict or message_dict.get('reasoning_content') is None:
            message_dict['reasoning_content'] = ''
    return message_dict


def format_message_for_llm(message: Any) -> dict[str, Any]:
    """
    格式化消息为 LLM API 所需的格式
    统一处理消息转换和 reasoning_content 字段

    Args:
        message: 消息对象，可以是 Pydantic 模型、字典或其他对象

    Returns:
        格式化后的消息字典
    """
    message_dict = normalize_message_to_dict(message)
    message_dict = ensure_reasoning_content_for_tool_calls(message_dict)
    return message_dict


def format_assistant_tool_call_message(message: AssistantToolCallMessage) -> dict[str, Any]:
    """
    格式化 AssistantToolCallMessage 为 LLM API 所需的格式
    确保包含 reasoning_content 字段（如果包含 tool_calls）

    Args:
        message: AssistantToolCallMessage 对象

    Returns:
        格式化后的消息字典
    """
    message_dict = message.model_dump()
    # 对于包含 tool_calls 的 assistant 消息，确保包含 reasoning_content 字段
    if message.tool_calls:
        if message_dict.get('reasoning_content') is None:
            message_dict['reasoning_content'] = ''
    return message_dict


def clear_reasoning_content(message: dict[str, Any]) -> dict[str, Any]:
    """
    清除消息中的 reasoning_content 字段

    Args:
        message: 消息字典

    Returns:
        清除 reasoning_content 字段后的消息字典
    """
    return {k: v for k, v in message.items() if k != 'reasoning_content'}
