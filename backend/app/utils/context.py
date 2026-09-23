"""请求上下文管理 - 使用 ContextVar 存储请求/业务上下文信息

集中管理所有请求级别的上下文变量，供日志、中间件、Agent 等模块使用。
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field, fields
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
    # 子任务委派快照。标题流会在新任务里恢复 async generator，新任务看不到
    # 上一段的 ContextVar.set，但会共享这份请求对象。不进日志、不可被
    # set_request_context 覆盖。
    _turn_delegation: Any = field(default=None, repr=False, compare=False)

    def to_log_dict(self) -> dict[str, Any]:
        """返回非 None 的公开字段，用于日志绑定"""
        return {
            item.name: getattr(self, item.name)
            for item in fields(self)
            if not item.name.startswith("_") and getattr(self, item.name) is not None
        }


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
    valid_keys = {f.name for f in fields(ctx) if not f.name.startswith("_")}
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
