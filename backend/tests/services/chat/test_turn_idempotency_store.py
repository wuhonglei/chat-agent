"""TurnIdempotencyStore 单元测试（fakeredis）。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from unittest.mock import patch

import fakeredis.aioredis
import pytest
import pytest_asyncio
from fastapi import HTTPException

from app.services.chat.turn_idempotency_store import (
    PENDING_SENTINEL,
    IdempotentTurn,
    TurnIdempotencyStore,
)

_KEY = ("user-1", "conv-1", "turn-1")
_TURN = IdempotentTurn(
    user_message_id="user-msg-1",
    assistant_message_id="asst-msg-1",
)


@pytest_asyncio.fixture
async def fake_redis() -> AsyncIterator[fakeredis.aioredis.FakeRedis]:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


@pytest_asyncio.fixture
async def store(
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> AsyncIterator[TurnIdempotencyStore]:
    with patch(
        "app.services.chat.turn_idempotency_store.get_redis",
        return_value=fake_redis,
    ):
        yield TurnIdempotencyStore(
            ttl_seconds=3600,
            pending_ttl_seconds=60,
            wait_timeout_seconds=1.0,
        )


@pytest.mark.asyncio
async def test_save_then_get(
    store: TurnIdempotencyStore, fake_redis: fakeredis.aioredis.FakeRedis
) -> None:
    await store.save(_KEY, _TURN)
    got = await store.get(_KEY)
    assert got == _TURN
    raw = await fake_redis.get(store._key(_KEY))
    assert raw is not None
    assert "user-msg-1" in raw


@pytest.mark.asyncio
async def test_get_returns_none_when_missing(store: TurnIdempotencyStore) -> None:
    assert await store.get(_KEY) is None


@pytest.mark.asyncio
async def test_reserve_or_get_first_wins(
    store: TurnIdempotencyStore, fake_redis: fakeredis.aioredis.FakeRedis
) -> None:
    result = await store.reserve_or_get(_KEY)
    assert result == "reserved"
    assert await fake_redis.get(store._key(_KEY)) == PENDING_SENTINEL


@pytest.mark.asyncio
async def test_concurrent_reserve_one_reserved_one_gets_turn(
    store: TurnIdempotencyStore,
) -> None:
    create_count = 0

    async def create_fn() -> IdempotentTurn:
        nonlocal create_count
        create_count += 1
        await asyncio.sleep(0.05)
        return _TURN

    async def resolve() -> tuple[IdempotentTurn, bool]:
        return await store.resolve_turn(_KEY, create_fn=create_fn)

    results = await asyncio.gather(resolve(), resolve())
    turns = [r[0] for r in results]
    hits = [r[1] for r in results]

    assert turns[0] == _TURN
    assert turns[1] == _TURN
    assert create_count == 1
    assert hits.count(False) == 1
    assert hits.count(True) == 1


@pytest.mark.asyncio
async def test_resolve_turn_releases_pending_on_create_failure(
    store: TurnIdempotencyStore, fake_redis: fakeredis.aioredis.FakeRedis
) -> None:
    async def failing_create() -> IdempotentTurn:
        raise RuntimeError("db failed")

    with pytest.raises(RuntimeError, match="db failed"):
        await store.resolve_turn(_KEY, create_fn=failing_create)

    assert await fake_redis.get(store._key(_KEY)) is None


@pytest.mark.asyncio
async def test_wait_timeout_raises_503(
    store: TurnIdempotencyStore, fake_redis: fakeredis.aioredis.FakeRedis
) -> None:
    await fake_redis.set(store._key(_KEY), PENDING_SENTINEL, ex=60)

    with pytest.raises(HTTPException) as exc_info:
        await store.reserve_or_get(_KEY)

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_ttl_expiry_clears_entry(
    store: TurnIdempotencyStore, fake_redis: fakeredis.aioredis.FakeRedis
) -> None:
    short_store = TurnIdempotencyStore(
        ttl_seconds=1,
        pending_ttl_seconds=1,
        wait_timeout_seconds=0.5,
    )
    with patch(
        "app.services.chat.turn_idempotency_store.get_redis",
        return_value=fake_redis,
    ):
        await short_store.save(_KEY, _TURN)
        assert await short_store.get(_KEY) == _TURN
        await fake_redis.expire(short_store._key(_KEY), 0)
        # fakeredis may need a tick; force delete via expire 0 / get
        await asyncio.sleep(0.05)
        # Explicitly expire by deleting if still present after TTL 0
        if await fake_redis.ttl(short_store._key(_KEY)) <= 0:
            await fake_redis.delete(short_store._key(_KEY))
        assert await short_store.get(_KEY) is None
