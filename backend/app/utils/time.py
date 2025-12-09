import time
from datetime import datetime


def get_current_time() -> float:
    """获取当前时间
    Returns:
        float: 当前时间戳
    """
    return time.time()


def get_time_duration(start_time: float) -> float:
    """获取时间差
    Args:
        start_time: 开始时间
    Returns:
        float: 时间差
    """
    return round(time.time() - start_time, 2)


def format_datetime_to_iso8601(time_obj: datetime) -> str:
    """将 datetime 对象格式化为 ISO 8601 格式字符串（使用系统本地时区）

    功能：
    - 将 datetime 对象转换为系统本地时区的 ISO 8601 格式
    - 如果时间对象没有时区信息，将其视为系统本地时区
    - 如果时间对象已有其他时区，会自动转换为系统本地时区
    - 输出格式包含微秒精度和时区偏移量（如 +08:00）

    Args:
        time_obj: datetime 对象（可以是 naive 或 aware）

    Returns:
        str: ISO 8601 格式的时间字符串，例如 "2025-01-09T08:00:00.123456+08:00"

    Example:
        >>> from datetime import datetime
        >>> dt = datetime.now()
        >>> format_datetime_to_iso8601(dt)
        '2025-01-09T08:00:00.123456+08:00'
    """
    # 获取系统本地时区
    local_tz = datetime.now().astimezone().tzinfo
    # 确保时间对象有时区信息，如果没有则视为系统本地时区
    if time_obj.tzinfo is None:
        time_obj = time_obj.replace(tzinfo=local_tz)
    # 转换为系统本地时区（如果已经是其他时区，会自动转换）
    time_local = time_obj.astimezone(local_tz)
    # 格式化为 ISO 8601 格式（包含微秒和时区）
    # 使用 isoformat() 方法生成标准格式，会自动显示系统时区的偏移量（如 +08:00）
    return time_local.isoformat(timespec="microseconds")
