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


def get_current_datetime_str() -> str:
    """获取当前日期和时间字符串"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_current_date() -> str:
    """获取当前日期字符串"""
    return datetime.now().strftime("%Y-%m-%d")


def get_datetime_now(with_timezone: bool = True) -> datetime:
    """获取当前时间"""
    logger.debug("获取当前时间")
    if with_timezone:
        return datetime.now(timezone.utc)
    else:
        return datetime.now()
