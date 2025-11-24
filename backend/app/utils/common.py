import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger


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


def filter_dict(dict_data: dict, values: Optional[list[Any]] = None) -> list[Any]:
    """过滤字典，返回值为指定值的键"""
    values = values or [True]
    return [k for k, v in dict_data.items() if v in values]


def gen_uuid() -> str:
    """Generate a new UUID string"""
    return str(uuid.uuid4())
