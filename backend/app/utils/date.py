from datetime import datetime, timezone

import humanize  # noqa: F401


def get_current_datetime_str() -> str:
    """获取当前日期和时间字符串"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_current_date() -> str:
    """获取当前日期字符串"""
    return datetime.now().strftime("%Y-%m-%d")


def get_datetime_now(with_timezone: bool = True) -> datetime:
    """获取当前时间"""
    if with_timezone:
        return datetime.now(timezone.utc)
    else:
        return datetime.now()


def get_unix_timestamp() -> int:
    """获取当前时间戳"""
    return int(datetime.now().timestamp())


def get_relative_time_diff(target_datetime: datetime | None) -> str | None:
    """获取当前时间与指定时间的相对时间差（如：`3 minutes ago`）。"""
    if target_datetime is None:
        return None
    now = (
        datetime.now(tz=target_datetime.tzinfo)
        if target_datetime.tzinfo is not None
        else datetime.now()
    )
    return humanize.naturaltime(target_datetime, when=now)
