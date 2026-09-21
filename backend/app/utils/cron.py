"""5 段 cron 表达式解析（供独立 Worker 进程复用）。"""

from __future__ import annotations


def parse_cron_5field(cron: str) -> dict[str, str]:
    """解析标准 5 段 cron: minute hour day month day_of_week。

    返回值可直接作为 ``apscheduler.triggers.cron.CronTrigger`` 的 kwargs。
    """
    parts = cron.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {cron}")
    minute, hour, day, month, day_of_week = parts
    return {
        "minute": minute,
        "hour": hour,
        "day": day,
        "month": month,
        "day_of_week": day_of_week,
    }
