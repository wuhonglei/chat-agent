import uuid
from typing import Any

from fastapi.encoders import jsonable_encoder


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
        # 使用 JSON 模式确保 datetime 等类型可序列化
        return data.model_dump(mode="json")
    if isinstance(data, dict):
        return jsonable_encoder(data)

    return jsonable_encoder(data)


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


def normalize_url(url: str) -> str:
    """
    规范化 URL（去除锚点，保留查询参数）

    Args:
        url: 原始 URL

    Returns:
        str: 规范化后的 URL
    """
    # 去除锚点（# 之后的内容）
    if "#" in url:
        url = url.split("#")[0]
    return url.strip()
