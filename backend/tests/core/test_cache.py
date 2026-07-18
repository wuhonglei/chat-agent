"""Tests for L1/L2 business cache primitives."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest
import pytest_asyncio

from app.core import local_cache
from app.core.cache import (
    conversation_list_key,
    get_owned_cache_response,
    l2_delete_pattern,
    l2_get,
    l2_set,
    owned_cache_envelope,
)


@pytest_asyncio.fixture
async def fake_redis() -> AsyncIterator[fakeredis.aioredis.FakeRedis]:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


def test_l1_set_get_delete_and_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    local_cache.l1_delete("health")
    monkeypatch.setitem(
        local_cache._CACHE_CONFIGS,
        "health",
        local_cache._CacheConfig(maxsize=1, ttl=0.01),
    )
    local_cache._caches.pop("health", None)

    local_cache.l1_set("health", "redis_ping", "ok")
    assert local_cache.l1_get("health", "redis_ping") == "ok"

    local_cache.l1_delete("health", "redis_ping")
    assert local_cache.l1_get("health", "redis_ping") is None

    local_cache.l1_set("health", "redis_ping", "ok")
    asyncio.run(asyncio.sleep(0.02))
    assert local_cache.l1_get("health", "redis_ping") is None


@pytest.mark.asyncio
async def test_l2_round_trip_and_oversize_skip(
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> None:
    with patch("app.core.cache.get_redis", return_value=fake_redis):
        assert await l2_set(
            "cache:test",
            {"name": "value"},
            namespace="test",
            ttl=60,
        )
        assert await l2_get("cache:test", namespace="test") == {"name": "value"}

        assert not await l2_set(
            "cache:large",
            {"value": "too large"},
            namespace="test",
            ttl=60,
            max_bytes=1,
        )
        assert await fake_redis.exists("cache:large") == 0


@pytest.mark.asyncio
async def test_l2_delete_pattern_uses_prefix(
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> None:
    await fake_redis.mset(
        {
            "cache:conv_list:user-1::20": "one",
            "cache:conv_list:user-1:cursor:20": "two",
            "cache:conv_list:user-2::20": "other",
        }
    )
    with patch("app.core.cache.get_redis", return_value=fake_redis):
        deleted = await l2_delete_pattern(
            "cache:conv_list:user-1:*",
            namespace="conv_list",
        )

    assert deleted == 2
    assert await fake_redis.exists("cache:conv_list:user-1::20") == 0
    assert await fake_redis.exists("cache:conv_list:user-2::20") == 1


@pytest.mark.asyncio
async def test_l2_errors_are_logged_and_reraised() -> None:
    redis = MagicMock()
    redis.get = AsyncMock(side_effect=RuntimeError("redis unavailable"))
    with (
        patch("app.core.cache.get_redis", return_value=redis),
        patch("app.core.cache.logger.error") as log_error,
        pytest.raises(RuntimeError, match="redis unavailable"),
    ):
        await l2_get("cache:test", namespace="test")

    log_error.assert_called_once()


def test_key_normalization_and_owned_envelope() -> None:
    assert conversation_list_key("user-1", None, 20) == ("cache:conv_list:user-1::20")
    envelope = owned_cache_envelope("user-1", {"id": "conv-1"})
    assert get_owned_cache_response(envelope, "user-1") == {"id": "conv-1"}
    assert get_owned_cache_response(envelope, "user-2") is None
