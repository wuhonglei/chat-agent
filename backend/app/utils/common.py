import uuid
from typing import Any

from app.schemas.llm import AssistantToolCallMessage, ToolCallMessage


def remove_leading_whitespace(text: str) -> str:
    """移除每行前面的空白符"""
    lines = text.split("\n")
    processed_lines = [line.lstrip() for line in lines if line.strip()]
    return "\n".join(processed_lines)


def remove_all_whitespace(text: str) -> str:
    """移除每行前面和后面的空白符"""
    lines = text.split("\n")
    processed_lines = [line.strip() for line in lines if line.strip()]
    return "\n".join(processed_lines)


def normalize_to_dict(data: Any) -> dict[str, Any]:
    """
    将消息对象转换为字典格式

    Args:
        data: 消息对象，可以是 Pydantic 模型、字典或其他对象

    Returns:
        字典格式的消息
    """
    if hasattr(data, "model_dump"):
        return data.model_dump()
    elif isinstance(data, dict):
        return data
    else:
        return dict(data)


def omit_fields(dict_data: dict, fields: list[str]) -> dict:
    """移除指定字段"""
    return {k: v for k, v in dict_data.items() if k not in fields}


def pick_fields(dict_data: dict, field_names: list[str]) -> dict:
    """
    根据字段名列表从对象中提取字段并返回字典

    Args:
        dict_data: 字典
        field_names: 要提取的字段名列表

    Returns:
        dict: 包含指定字段的字典
    """
    # 根据字段名列表过滤
    return {k: v for k, v in dict_data.items() if k in field_names}


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
        isinstance(tool_call, AssistantToolCallMessage)
        and tool_call.tool_calls
        and any(
            tool_name.lower() in tool_call_item.function.name.lower()
            for tool_call_item in tool_call.tool_calls
        )
        for tool_call in tool_call_messages
    )
