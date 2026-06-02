"""Langfuse observability bootstrap and helpers."""

from __future__ import annotations

import hashlib
from typing import Any

from langfuse import Langfuse

from app.core.config import settings
from app.utils.logger import logger

_langfuse_client: Langfuse | None = None


def _mask_data(value: Any) -> Any:
    """递归清洗事件负载，移除 data URL 图片。"""
    if isinstance(value, dict):
        return {key: _mask_data(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_mask_data(item) for item in value]
    if isinstance(value, str):
        lower = value.lower()
        if lower.startswith("data:image/") and ";base64," in lower:
            return "[image omitted]"
    return value


def _build_langfuse_kwargs(tracing_enabled: bool) -> dict[str, Any]:
    cfg = settings.langfuse
    return {
        "public_key": cfg.public_key,
        "secret_key": cfg.secret_key,
        "host": cfg.host,
        "sample_rate": cfg.sample_rate,
        "environment": cfg.environment,
        "debug": cfg.debug,
        "tracing_enabled": tracing_enabled,
        "mask": _mask_data,
    }


def init_langfuse() -> None:
    """初始化 Langfuse 客户端（失败不影响主链路）。"""
    global _langfuse_client
    if _langfuse_client is not None:
        return

    tracing_enabled = bool(settings.langfuse.enabled)
    try:
        kwargs = _build_langfuse_kwargs(tracing_enabled=tracing_enabled)
        try:
            _langfuse_client = Langfuse(**kwargs)
        except TypeError:
            # 兼容不支持 mask 参数的 SDK 版本
            kwargs.pop("mask", None)
            _langfuse_client = Langfuse(**kwargs)
        logger.info(
            "Langfuse initialized",
            enabled=tracing_enabled,
            host=settings.langfuse.host,
            environment=settings.langfuse.environment,
            sample_rate=settings.langfuse.sample_rate,
        )
    except Exception as exc:
        _langfuse_client = None
        logger.warning(
            "Langfuse initialization failed, tracing disabled",
            error=exc,
            error_type=type(exc).__name__,
        )


def get_langfuse() -> Langfuse | None:
    return _langfuse_client


def is_enabled() -> bool:
    return bool(settings.langfuse.enabled and _langfuse_client is not None)


def shutdown_langfuse() -> None:
    """优雅关闭 Langfuse，确保缓冲队列刷盘。"""
    global _langfuse_client
    if _langfuse_client is None:
        return

    try:
        _langfuse_client.flush()
    except Exception as exc:
        logger.warning(
            "Langfuse flush failed",
            error=exc,
            error_type=type(exc).__name__,
        )
    finally:
        _langfuse_client = None


def new_trace_id(seed: str) -> str:
    """生成确定性 trace_id，优先使用 Langfuse 内置方法。"""
    try:
        return Langfuse.create_trace_id(seed=seed)
    except Exception:
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        return digest[:32]
