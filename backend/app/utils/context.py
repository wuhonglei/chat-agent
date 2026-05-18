"""请求上下文管理 - 使用 ContextVar 存储请求/业务上下文信息

集中管理所有请求级别的上下文变量，供日志、中间件、Agent 等模块使用。
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import asdict, dataclass, fields
from typing import Any


@dataclass
class RequestContext:
    """请求上下文数据对象，包含所有请求级别的上下文字段"""

    request_id: str | None = None
    user_id: str | None = None
    anonymous_user_id: str | None = None
    client_id: str | None = None
    client_ip: str | None = None
    conversation_id: str | None = None

    def to_log_dict(self) -> dict[str, Any]:
        """返回非 None 字段，用于日志绑定"""
        return {k: v for k, v in asdict(self).items() if v is not None}


request_context_var: ContextVar[RequestContext | None] = ContextVar(
    "request_context", default=None
)


def set_request_context(**kwargs: str | None) -> RequestContext:
    """设置请求上下文字段，仅更新非 None 的值

    Args:
        **kwargs: 要设置的上下文字段（如 user_id="xxx", request_id="yyy"）

    Returns:
        更新后的 RequestContext
    """
    ctx = request_context_var.get() or RequestContext()
    valid_keys = {f.name for f in fields(ctx)}
    for key, value in kwargs.items():
        if value is not None and key in valid_keys:
            setattr(ctx, key, value)
    request_context_var.set(ctx)
    return ctx


def get_request_context() -> RequestContext:
    """获取当前请求上下文"""
    return request_context_var.get() or RequestContext()


def reset_request_context() -> None:
    """重置请求上下文为默认空值"""
    request_context_var.set(None)
