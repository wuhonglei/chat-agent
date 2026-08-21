"""Langfuse observability bootstrap and helpers."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from typing import Any

from langfuse import Langfuse, propagate_attributes

from app.core.config import settings
from app.utils.logger import logger

_langfuse_client: Langfuse | None = None


def _mask_data(*, data: Any, **kwargs: Any) -> Any:
    """递归清洗事件负载，移除 data URL 图片。

    Langfuse MaskFunction 协议要求关键字参数 ``data``（见 langfuse.types.MaskFunction）。
    """
    _ = kwargs
    if isinstance(data, dict):
        return {key: _mask_data(data=item) for key, item in data.items()}
    if isinstance(data, list):
        return [_mask_data(data=item) for item in data]
    if isinstance(data, str):
        lower = data.lower()
        if lower.startswith("data:image/") and ";base64," in lower:
            return "[image omitted]"
    return data


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
    import os

    global _langfuse_client
    if _langfuse_client is not None:
        return

    # 设置 OpenTelemetry service.name，避免默认的 "unknown_service"
    os.environ.setdefault("OTEL_SERVICE_NAME", "chat-agent-backend")

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


def build_trace_url(trace_id: str | None) -> str | None:
    """根据配置拼装 Langfuse Trace UI 链接。"""
    if not trace_id:
        return None
    host = (settings.langfuse.host or "").rstrip("/")
    if not host:
        return None
    project_id = (settings.langfuse.project_id or "").strip()
    if project_id:
        return f"{host}/project/{project_id}/traces/{trace_id}"
    return f"{host}/trace/{trace_id}"


def ensure_dataset(dataset_name: str, *, description: str | None = None) -> None:
    """确保 Langfuse dataset 存在（create_dataset 为 upsert）。"""
    client = get_langfuse()
    if client is None:
        raise RuntimeError("Langfuse 客户端不可用")
    kwargs: dict[str, Any] = {"name": dataset_name}
    if description is not None:
        kwargs["description"] = description
    try:
        client.create_dataset(**kwargs)
    except Exception as exc:
        logger.error(
            "Failed to ensure Langfuse dataset",
            dataset_name=dataset_name,
            error=exc,
            error_type=type(exc).__name__,
        )
        raise


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


@contextmanager
def observation_span(
    name: str,
    *,
    as_type: str = "span",
    input: Any = None,
    metadata: dict[str, Any] | None = None,
    trace_name: str | None = None,
    trace_context: dict[str, Any] | None = None,
) -> Iterator[Any]:
    """开启一个 Langfuse observation，未启用时退化为 no-op（yield None）。

    所有埋点异常只告警，不冒泡到业务链路。
    """
    if not is_enabled():
        yield None
        return

    client = get_langfuse()
    if client is None:
        yield None
        return

    kwargs: dict[str, Any] = {"as_type": as_type, "name": name}
    if input is not None:
        kwargs["input"] = input
    if metadata is not None:
        kwargs["metadata"] = metadata
    if trace_context is not None:
        kwargs["trace_context"] = trace_context

    try:
        cm = client.start_as_current_observation(**kwargs)
    except Exception as exc:
        logger.warning(
            "Failed to start observation span",
            span_name=name,
            error=exc,
            error_type=type(exc).__name__,
        )
        yield None
        return

    try:
        with cm as span:
            attr_cm = (
                propagate_attributes(trace_name=trace_name)
                if trace_name
                else nullcontext()
            )
            with attr_cm:
                yield span
    except Exception:
        # 业务异常照常向上抛，由调用方决定是否 mark_observation_error。
        raise


def mark_observation_error(span: Any, exc: BaseException) -> None:
    """将给定 observation 标记为 ERROR；span 为 None 或失败时静默。"""
    if span is None:
        return
    try:
        span.update(level="ERROR", status_message=type(exc).__name__)
    except Exception as update_exc:
        logger.warning(
            "Failed to mark observation as error",
            error=update_exc,
            error_type=type(update_exc).__name__,
        )


def score_observation(
    span: Any,
    *,
    name: str,
    value: bool | float | str,
    data_type: str = "BOOLEAN",
    comment: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """给 observation 打分；span 为 None 或失败时静默。"""
    if span is None:
        return
    try:
        kwargs: dict[str, Any] = {
            "name": name,
            "value": value,
            "data_type": data_type,
        }
        if comment is not None:
            kwargs["comment"] = comment
        if metadata is not None:
            kwargs["metadata"] = metadata
        span.score(**kwargs)
    except Exception as score_exc:
        logger.warning(
            "Failed to score observation",
            score_name=name,
            error=score_exc,
            error_type=type(score_exc).__name__,
        )


def flush_langfuse() -> None:
    """主动刷盘 Langfuse 缓冲队列；未启用或失败时静默。"""
    client = get_langfuse()
    if client is None:
        return
    try:
        client.flush()
    except Exception as exc:
        logger.warning(
            "Langfuse flush failed",
            error=exc,
            error_type=type(exc).__name__,
        )
