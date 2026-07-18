"""Redis-backed Cache-Aside primitives and business cache keys."""

from __future__ import annotations

import asyncio
import json
from typing import Any, TypedDict

from app.core.redis import get_redis
from app.utils.logger import logger

USER_DETAIL_TTL_SECONDS = 60
CONVERSATION_DETAIL_TTL_SECONDS = 30
CONVERSATION_LIST_TTL_SECONDS = 10
MESSAGES_TTL_SECONDS = 15
MAX_CACHE_VALUE_BYTES = 512 * 1024


class OwnedCacheEnvelope(TypedDict):
    """Cache payload carrying the owner separately from the API response."""

    owner_user_id: str
    response: Any


def user_detail_key(user_id: str) -> str:
    return f"cache:user:{user_id}"


def conversation_detail_key(conversation_id: str) -> str:
    return f"cache:conv:{conversation_id}"


def conversation_list_key(user_id: str, cursor: str | None, limit: int) -> str:
    return f"cache:conv_list:{user_id}:{cursor or ''}:{limit}"


def messages_key(conversation_id: str) -> str:
    return f"cache:msg:{conversation_id}"


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


async def l2_get(key: str, *, namespace: str) -> Any | None:
    try:
        raw = await get_redis().get(key)
        value = None if raw is None else json.loads(raw)
    except Exception as exc:
        _cache_error("get", namespace, exc)
        raise
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
    max_bytes: int | None = None,
) -> bool:
    raw = json.dumps(value, ensure_ascii=False, default=str)
    if max_bytes is not None and len(raw.encode("utf-8")) > max_bytes:
        logger.info(
            "cache_skip_oversize",
            cache_level="l2",
            cache_namespace=namespace,
            max_bytes=max_bytes,
        )
        return False
    try:
        await get_redis().set(key, raw, ex=ttl)
    except Exception as exc:
        _cache_error("set", namespace, exc)
        raise
    return True


async def l2_delete(key: str, *, namespace: str) -> int:
    try:
        deleted = await get_redis().unlink(key)
    except Exception as exc:
        _cache_error("unlink", namespace, exc)
        raise
    logger.info(
        "cache_invalidate",
        cache_level="l2",
        cache_namespace=namespace,
        deleted=deleted,
    )
    return deleted


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
            deleted += await redis.unlink(*batch)
            batch.clear()
        if batch:
            deleted += await redis.unlink(*batch)
    except Exception as exc:
        _cache_error("scan_unlink", namespace, exc)
        raise
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
    await l2_delete_pattern(
        f"cache:conv_list:{user_id}:*",
        namespace="conv_list",
    )


async def invalidate_conversation(conversation_id: str, user_id: str) -> None:
    await asyncio.gather(
        l2_delete(
            conversation_detail_key(conversation_id),
            namespace="conv",
        ),
        invalidate_conversation_list(user_id),
    )


async def invalidate_messages(conversation_id: str) -> None:
    await l2_delete(messages_key(conversation_id), namespace="msg")


async def invalidate_conversation_state(
    conversation_id: str,
    user_id: str,
) -> None:
    await asyncio.gather(
        invalidate_conversation(conversation_id, user_id),
        invalidate_messages(conversation_id),
    )
