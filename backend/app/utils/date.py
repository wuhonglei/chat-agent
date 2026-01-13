from datetime import datetime, timezone


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
