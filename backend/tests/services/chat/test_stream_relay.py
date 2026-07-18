"""Redis StreamRelay 单元测试（fakeredis）。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from unittest.mock import patch

import fakeredis.aioredis
import pytest
import pytest_asyncio

from app.schemas.chat import MessageStatus
from app.services.chat.stream_relay import StreamRelay


@pytest_asyncio.fixture
async def fake_redis() -> AsyncIterator[fakeredis.aioredis.FakeRedis]:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


@pytest_asyncio.fixture
async def relay(fake_redis: fakeredis.aioredis.FakeRedis) -> AsyncIterator[StreamRelay]:
    with patch(
        "app.services.chat.stream_relay.get_redis",
        return_value=fake_redis,
    ):
        yield StreamRelay(
            ttl_seconds=3600,
            closed_ttl_seconds=600,
            xread_block_ms=50,
        )


@pytest.mark.asyncio
async def test_append_increments_event_id_and_wraps_sse(
    relay: StreamRelay, fake_redis: fakeredis.aioredis.FakeRedis
) -> None:
    stream_id = "asst-1"
    await relay.register(stream_id)

    id1 = await relay.append(stream_id, 'data: {"type":"ack","data":{}}\n\n')
    id2 = await relay.append(stream_id, 'data: {"type":"done","data":{}}\n\n')

    assert id1 == 1
    assert id2 == 2

    events: list[str] = []
    async for event in relay.iter_resume(stream_id, last_event_id=0):
        events.append(event)
        if len(events) >= 2:
            break

    assert events[0].startswith("id: 1\n")
    assert 'data: {"type":"ack"' in events[0]
    assert events[1].startswith("id: 2\n")


@pytest.mark.asyncio
async def test_iter_resume_filters_by_last_event_id(relay: StreamRelay) -> None:
    stream_id = "asst-2"
    await relay.register(stream_id)
    await relay.append(stream_id, "data: a\n\n")
    await relay.append(stream_id, "data: b\n\n")
    await relay.append(stream_id, "data: c\n\n")
    await relay.close(stream_id)

    events = [event async for event in relay.iter_resume(stream_id, last_event_id=2)]
    assert len(events) == 1
    assert events[0].startswith("id: 3\n")
    assert "data: c" in events[0]


@pytest.mark.asyncio
async def test_close_then_consumer_exits(relay: StreamRelay) -> None:
    stream_id = "asst-3"
    await relay.register(stream_id)
    await relay.append(stream_id, "data: x\n\n")
    await relay.close(stream_id)

    events = [event async for event in relay.iter_resume(stream_id, last_event_id=0)]
    assert len(events) == 1
    assert events[0].startswith("id: 1\n")


@pytest.mark.asyncio
async def test_has_stream_states(relay: StreamRelay) -> None:
    stream_id = "asst-4"
    assert await relay.has_stream(stream_id) is False

    await relay.register(stream_id)
    assert await relay.has_stream(stream_id) is True

    await relay.append(stream_id, "data: y\n\n")
    await relay.close(stream_id)
    # Closed but still within TTL with stream data → resume allowed
    assert await relay.has_stream(stream_id) is True


@pytest.mark.asyncio
async def test_many_appends_are_not_trimmed(relay: StreamRelay) -> None:
    stream_id = "asst-5"
    await relay.register(stream_id)
    count = 50
    for i in range(count):
        await relay.append(stream_id, f"data: {i}\n\n")
    await relay.close(stream_id)

    events = [event async for event in relay.iter_resume(stream_id, last_event_id=0)]
    assert len(events) == count
    assert events[0].startswith("id: 1\n")
    assert events[-1].startswith(f"id: {count}\n")


@pytest.mark.asyncio
async def test_append_after_close_does_not_add_event(relay: StreamRelay) -> None:
    stream_id = "asst-6"
    await relay.register(stream_id)
    await relay.append(stream_id, "data: a\n\n")
    await relay.close(stream_id)

    last_id = await relay.append(stream_id, "data: ignored\n\n")
    assert last_id == 1

    events = [event async for event in relay.iter_resume(stream_id, last_event_id=0)]
    assert len(events) == 1


@pytest.mark.asyncio
async def test_live_tail_receives_new_events(relay: StreamRelay) -> None:
    stream_id = "asst-7"
    await relay.register(stream_id)

    collected: list[str] = []

    async def consume() -> None:
        async for event in relay.iter_resume(stream_id, last_event_id=0):
            collected.append(event)
            if len(collected) >= 2:
                return

    consumer = asyncio.create_task(consume())
    await asyncio.sleep(0.05)
    await relay.append(stream_id, "data: first\n\n")
    await relay.append(stream_id, "data: second\n\n")
    await asyncio.wait_for(consumer, timeout=2.0)

    assert len(collected) == 2
    assert collected[0].startswith("id: 1\n")
    assert collected[1].startswith("id: 2\n")


@pytest.mark.asyncio
async def test_register_initializes_status_pending(relay: StreamRelay) -> None:
    stream_id = "asst-status-1"
    await relay.register(stream_id)
    assert await relay.get_status(stream_id) == MessageStatus.PENDING
    assert await relay.is_stop_requested(stream_id) is False


@pytest.mark.asyncio
async def test_request_stop_pending_to_stopped(relay: StreamRelay) -> None:
    stream_id = "asst-status-2"
    await relay.register(stream_id)

    assert await relay.request_stop(stream_id) is True
    assert await relay.get_status(stream_id) == MessageStatus.STOPPED
    assert await relay.is_stop_requested(stream_id) is True

    # Idempotent: already stopped
    assert await relay.request_stop(stream_id) is False
    assert await relay.get_status(stream_id) == MessageStatus.STOPPED


@pytest.mark.asyncio
async def test_request_stop_missing_meta_returns_false(relay: StreamRelay) -> None:
    assert await relay.request_stop("missing-stream") is False
    assert await relay.get_status("missing-stream") is None


@pytest.mark.asyncio
async def test_close_pending_to_done_and_failed(relay: StreamRelay) -> None:
    stream_id = "asst-status-3"
    await relay.register(stream_id)
    await relay.close(stream_id, final_status=MessageStatus.DONE)
    assert await relay.get_status(stream_id) == MessageStatus.DONE

    stream_id_f = "asst-status-3f"
    await relay.register(stream_id_f)
    await relay.close(stream_id_f, final_status=MessageStatus.FAILED)
    assert await relay.get_status(stream_id_f) == MessageStatus.FAILED


@pytest.mark.asyncio
async def test_close_preserves_stopped(relay: StreamRelay) -> None:
    stream_id = "asst-status-4"
    await relay.register(stream_id)
    await relay.request_stop(stream_id)
    await relay.close(stream_id, final_status=MessageStatus.DONE)
    assert await relay.get_status(stream_id) == MessageStatus.STOPPED


@pytest.mark.asyncio
async def test_append_after_stop_does_not_add_event(relay: StreamRelay) -> None:
    stream_id = "asst-status-5"
    await relay.register(stream_id)
    await relay.append(stream_id, "data: a\n\n")
    await relay.request_stop(stream_id)

    last_id = await relay.append(stream_id, "data: ignored\n\n")
    assert last_id == 1

    await relay.close(stream_id, final_status=MessageStatus.STOPPED)
    events = [event async for event in relay.iter_resume(stream_id, last_event_id=0)]
    assert len(events) == 1
    assert "data: a" in events[0]


@pytest.mark.asyncio
async def test_has_stream_after_stopped_with_data(relay: StreamRelay) -> None:
    stream_id = "asst-status-6"
    await relay.register(stream_id)
    await relay.append(stream_id, "data: y\n\n")
    await relay.request_stop(stream_id)
    await relay.close(stream_id, final_status=MessageStatus.STOPPED)
    assert await relay.has_stream(stream_id) is True


@pytest.mark.asyncio
async def test_legacy_closed_field_fallback(
    relay: StreamRelay, fake_redis: fakeredis.aioredis.FakeRedis
) -> None:
    stream_id = "asst-legacy"
    meta_key = relay._meta_key(stream_id)
    stream_key = relay._stream_key(stream_id)
    await fake_redis.hset(
        meta_key,
        mapping={"closed": "1", "created_at": "2020-01-01T00:00:00+00:00"},
    )
    await fake_redis.xadd(stream_key, {"payload": "data: legacy\n\n"}, id="1-0")

    assert await relay.get_status(stream_id) == MessageStatus.DONE
    assert await relay.request_stop(stream_id) is False
    assert await relay.has_stream(stream_id) is True
