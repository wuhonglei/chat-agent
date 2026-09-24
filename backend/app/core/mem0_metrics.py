"""Mem0 出站调用计数（兼容 gunicorn multiprocess；Counter 无需 pid 标签）。"""

from __future__ import annotations

from typing import Literal

from prometheus_client import Counter

Mem0Operation = Literal["add"]
Mem0Result = Literal["ok", "timeout", "error"]

MEM0_REQUESTS = Counter(
    "mem0_requests",
    "Outbound Mem0 HTTP calls by operation and result",
    ["operation", "result"],
)


def record_mem0_request(operation: Mem0Operation, result: Mem0Result) -> None:
    """记一次实际发出的 Mem0 调用。未启用时的提前返回不要调用。"""
    MEM0_REQUESTS.labels(operation=operation, result=result).inc()
