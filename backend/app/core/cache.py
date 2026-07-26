"""Redis-backed Cache-Aside primitives and business cache keys."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable
from typing import Any, TypedDict, TypeVar

from app.core.config import settings
from app.core.redis import get_redis
from app.utils.logger import logger

T = TypeVar("T")


class OwnedCacheEnvelope(TypedDict):
    """Cache payload carrying the owner separately from the API response."""

    owner_user_id: str
    response: Any


def user_detail_key(user_id: str) -> str:
    return f"cache:user:{user_id}"




def owned_cache_envelope(owner_user_id: str, response: Any) -> OwnedCacheEnvelope:
    return {"owner_user_id": owner_user_id, "response": response}


def get_owned_cache_response(value: Any, user_id: str) -> Any | None:
    """Return the response only when a cached envelope belongs to ``user_id``."""
    if not isinstance(value, dict):
        return None
    if value.get("owner_user_id") != user_id:
        return None
    return value.get("response")


def _cache_error(operation: str, namespace: str, exc: Exception) -> None:
    logger.error(
        "cache_l2_error",
        cache_operation=operation,
        cache_namespace=namespace,
        error=exc,
        error_type=type(exc).__name__,
    )


async def _with_cache_timeout(awaitable: Awaitable[T]) -> T:
    """Bound a Redis call so cache paths fail fast under pool pressure.

    Shared pool ``socket_timeout`` is sized for SSE XREAD BLOCK; cache ops use
    a shorter asyncio budget and must not wait that long when connections queue.
    """
    return await asyncio.wait_for(
        awaitable,
        timeout=settings.cache.operation_timeout_seconds,
    )


async def l2_get(key: str, *, namespace: str) -> Any | None:
    try:
        raw = await _with_cache_timeout(get_redis().get(key))
        value = None if raw is None else json.loads(raw)
    except Exception as exc:
        _cache_error("get", namespace, exc)
        return None
    logger.debug(
        "cache_hit" if value is not None else "cache_miss",
        cache_level="l2",
        cache_namespace=namespace,
    )
    return value


async def l2_set(
    key: str,
    value: Any,
    *,
    namespace: str,
    ttl: int,
) -> bool:
    raw = json.dumps(value, ensure_ascii=False, default=str)
    try:
        await _with_cache_timeout(get_redis().set(key, raw, ex=ttl))
    except Exception as exc:
        _cache_error("set", namespace, exc)
        return False
    return True


async def l2_delete(key: str, *, namespace: str) -> int:
    try:
        deleted = await _with_cache_timeout(get_redis().unlink(key))
    except Exception as exc:
        _cache_error("unlink", namespace, exc)
        return 0
    logger.info(
        "cache_invalidate",
        cache_level="l2",
        cache_namespace=namespace,
        deleted=deleted,
    )
    return int(deleted or 0)


async def l2_delete_pattern(pattern: str, *, namespace: str) -> int:
    """Delete matching keys in bounded UNLINK batches without using KEYS."""
    try:
        redis = get_redis()
        deleted = 0
        batch: list[str] = []
        async for key in redis.scan_iter(match=pattern, count=100):
            batch.append(key)
            if len(batch) < 100:
                continue
            deleted += int(await _with_cache_timeout(redis.unlink(*batch)) or 0)
            batch.clear()
        if batch:
            deleted += int(await _with_cache_timeout(redis.unlink(*batch)) or 0)
    except Exception as exc:
        _cache_error("scan_unlink", namespace, exc)
        return 0
    logger.info(
        "cache_invalidate",
        cache_level="l2",
        cache_namespace=namespace,
        deleted=deleted,
    )
    return deleted


async def invalidate_user(user_id: str) -> None:
    await l2_delete(user_detail_key(user_id), namespace="user")


async def invalidate_conversation_list(user_id: str) -> None:
    """No-op: L2 cache for conversation list removed."""


async def invalidate_conversation(conversation_id: str, user_id: str) -> None:
    """No-op: L2 cache for conversation detail removed."""


async def invalidate_messages(conversation_id: str) -> None:
    """No-op: L2 cache for messages removed."""


async def invalidate_conversation_state(
    conversation_id: str,
    user_id: str,
) -> None:
    """No-op: L2 cache for conversation/messages removed."""
