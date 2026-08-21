"""Health / dependency Prometheus gauges（兼容 gunicorn multiprocess）。"""

from __future__ import annotations

import os

from prometheus_client import Gauge

_pid = str(os.getpid())

HEALTH_DEPENDENCY_UP = Gauge(
    "health_dependency_up",
    "1 if dependency probe succeeded, else 0",
    ["component", "pid"],
)
HEALTH_PROBE_LATENCY_SECONDS = Gauge(
    "health_probe_latency_seconds",
    "Last health probe latency in seconds",
    ["component", "pid"],
)
DB_POOL_SIZE = Gauge(
    "db_pool_size",
    "SQLAlchemy pool size for this worker",
    ["pid"],
)
DB_POOL_CHECKED_OUT = Gauge(
    "db_pool_checked_out",
    "SQLAlchemy checked-out connections for this worker",
    ["pid"],
)
DB_POOL_OVERFLOW = Gauge(
    "db_pool_overflow",
    "SQLAlchemy overflow connections for this worker",
    ["pid"],
)


def record_dependency(component: str, *, up: bool, latency_seconds: float) -> None:
    """更新依赖探活 Gauge。"""
    HEALTH_DEPENDENCY_UP.labels(component=component, pid=_pid).set(1 if up else 0)
    HEALTH_PROBE_LATENCY_SECONDS.labels(component=component, pid=_pid).set(
        max(0.0, latency_seconds)
    )


def record_db_pool_stats(*, size: int, checkedout: int, overflow: int) -> None:
    """更新本 worker 连接池 Gauge。"""
    DB_POOL_SIZE.labels(pid=_pid).set(size)
    DB_POOL_CHECKED_OUT.labels(pid=_pid).set(checkedout)
    DB_POOL_OVERFLOW.labels(pid=_pid).set(overflow)
