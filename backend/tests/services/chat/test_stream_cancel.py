"""Cross-worker SSE cancel / stop 相关测试。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from unittest.mock import patch

import fakeredis.aioredis
import pytest
import pytest_asyncio

from app.api import chat as chat_api
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
async def test_poll_cancel_triggers_producer_cancel(relay: StreamRelay) -> None:
    stream_id = "asst-poll-1"
    await relay.register(stream_id)

    cancelled = asyncio.Event()

    async def _producer() -> None:
        try:
            while True:
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    producer = asyncio.create_task(_producer())
    chat_api._STREAM_PRODUCER_TASKS[stream_id] = producer

    with (
        patch.object(chat_api, "_STREAM_RELAY", relay),
        patch.object(
            chat_api.settings.chat_stream,
            "sse_stream_cancel_poll_ms",
            50,
        ),
    ):
        poll_task = asyncio.create_task(chat_api._poll_cancel(stream_id, 50))
        await asyncio.sleep(0.05)
        assert await relay.request_stop(stream_id) is True
        await asyncio.wait_for(cancelled.wait(), timeout=2.0)
        await asyncio.wait_for(poll_task, timeout=2.0)

    assert producer.cancelled() or producer.done()
    chat_api._STREAM_PRODUCER_TASKS.pop(stream_id, None)


@pytest.mark.asyncio
async def test_cross_worker_request_stop_only(relay: StreamRelay) -> None:
    """Simulate stop on another worker: only Redis signal, no local task dict."""
    stream_id = "asst-cross-1"
    await relay.register(stream_id)
    await relay.append(stream_id, "data: chunk\n\n")

    # No entry in _STREAM_PRODUCER_TASKS (other worker)
    assert stream_id not in chat_api._STREAM_PRODUCER_TASKS

    applied = await relay.request_stop(stream_id)
    assert applied is True
    assert await relay.is_stop_requested(stream_id) is True
    assert await relay.get_status(stream_id) == MessageStatus.STOPPED

    # Append rejected after stop
    last_id = await relay.append(stream_id, "data: after-stop\n\n")
    assert last_id == 1


@pytest.mark.asyncio
async def test_run_producer_stops_on_redis_status(relay: StreamRelay) -> None:
    """Producer loop exits via CancelledError when Redis status becomes stopped."""
    stream_id = "asst-producer-1"
    await relay.register(stream_id)

    async def slow_events() -> AsyncIterator[str]:
        for i in range(100):
            yield f"data: {i}\n\n"
            await asyncio.sleep(0.05)

    with (
        patch.object(chat_api, "_STREAM_RELAY", relay),
        patch.object(
            chat_api.settings.chat_stream,
            "sse_stream_cancel_poll_ms",
            50,
        ),
    ):
        producer = asyncio.create_task(
            chat_api._run_producer(
                event_stream=slow_events(),
                stream_id=stream_id,
                log_ctx={"assistant_message_id": stream_id},
            )
        )
        chat_api._STREAM_PRODUCER_TASKS[stream_id] = producer
        await asyncio.sleep(0.08)
        # Cross-worker style: only Redis signal
        assert await relay.request_stop(stream_id) is True
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(producer, timeout=2.0)

    assert await relay.get_status(stream_id) == MessageStatus.STOPPED
    chat_api._STREAM_PRODUCER_TASKS.pop(stream_id, None)
