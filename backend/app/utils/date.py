from datetime import datetime, timezone

import humanize  # noqa: F401

# datetime.weekday(): Monday=0 ... Sunday=6。不用 strftime("%A")，避免依赖系统 locale。
_WEEKDAY_ZH = (
    "星期一",
    "星期二",
    "星期三",
    "星期四",
    "星期五",
    "星期六",
    "星期日",
)


def get_current_datetime_str(dt: datetime | None = None) -> str:
    """格式化为本地时区日期时间字符串（YYYY-MM-DD HH:MM:SS 星期X）。

    传入 ``dt`` 时按该时刻格式化（aware datetime 会转到本地时区）；
    缺省则为当前本地时间。用于冻结 turn 级 ``<current_datetime>``。
    """
    if dt is None:
        dt = datetime.now()
    elif dt.tzinfo is not None:
        dt = dt.astimezone()
    return f"{dt.strftime('%Y-%m-%d %H:%M:%S')} {_WEEKDAY_ZH[dt.weekday()]}"


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


def get_relative_time_diff(target_datetime: datetime | str | None) -> str | None:
    """获取当前时间与指定时间的相对时间差（如：`3 minutes ago`）。"""
    if target_datetime is None:
        return None
    if isinstance(target_datetime, str):
        try:
            target_datetime = datetime.fromisoformat(
                target_datetime.replace("Z", "+00:00")
            )
        except ValueError:
            return None
    now = (
        datetime.now(tz=target_datetime.tzinfo)
        if target_datetime.tzinfo is not None
        else datetime.now()
    )
    return humanize.naturaltime(target_datetime, when=now)
