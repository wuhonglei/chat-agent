import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.schemas.llm import AssistantToolCallMessage, ToolCallMessage


def remove_leading_whitespace(text: str) -> str:
    """移除每行前面的空白符"""
    lines = text.split('\n')
    processed_lines = [line.lstrip() for line in lines if line.strip()]
    return '\n'.join(processed_lines)


def remove_all_whitespace(text: str) -> str:
    """移除每行前面和后面的空白符"""
    lines = text.split('\n')
    processed_lines = [line.strip() for line in lines if line.strip()]
    return '\n'.join(processed_lines)


def exclude_fields(dict_data: dict, fields: list[str]) -> dict:
    """移除指定字段"""
    return {k: v for k, v in dict_data.items() if k not in fields}


def include_fields(dict_data: dict, values: Optional[list[Any]] = None) -> list[Any]:
    """过滤字典，返回值为指定值的键"""
    values = values or [True]
    return [k for k, v in dict_data.items() if v in values]


def gen_uuid() -> str:
    """Generate a new UUID string"""
    return str(uuid.uuid4())


def has_tool_call_with_name(tool_call_messages: list[ToolCallMessage], tool_name: str) -> bool:
    """
    检查工具调用消息列表中是否包含指定名称的工具调用

    Args:
        tool_call_messages: 工具调用消息列表
        tool_name: 要查找的工具名称（不区分大小写）

    Returns:
        如果找到匹配的工具调用返回 True，否则返回 False
    """
    return any(
        isinstance(tool_call, AssistantToolCallMessage) and tool_call.tool_calls and
        any(tool_name.lower() in tool_call_item.function.name.lower()
            for tool_call_item in tool_call.tool_calls)
        for tool_call in tool_call_messages
    )
