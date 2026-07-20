"""SSE stream relay backed by Redis Stream for resumable multi-worker buffering."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.core.config import settings
from app.core.redis import get_redis
from app.schemas.chat import MessageStatus
from app.utils.logger import logger

# Socket / network blips during XREAD BLOCK must not tear down the SSE response.
_TRANSIENT_REDIS_ERRORS = (RedisTimeoutError, RedisConnectionError)
_MAX_XREAD_TRANSIENT_FAILURES = 3

_APPEND_SCRIPT = """
-- KEYS[1]=stream, KEYS[2]=meta, KEYS[3]=seq
-- ARGV[1]=payload, ARGV[2]=ttl
local status = redis.call('HGET', KEYS[2], 'status')
if status and status ~= 'pending' then
  return tonumber(redis.call('GET', KEYS[3]) or '0')
end
-- Legacy fallback: keys that only have closed field
if not status and redis.call('HGET', KEYS[2], 'closed') == '1' then
  return tonumber(redis.call('GET', KEYS[3]) or '0')
end
local event_id = redis.call('INCR', KEYS[3])
local entry_id = event_id .. '-0'
redis.call('XADD', KEYS[1], entry_id, 'payload', ARGV[1])
redis.call('HSET', KEYS[2], 'last_event_id', event_id)
redis.call('EXPIRE', KEYS[1], ARGV[2])
redis.call('EXPIRE', KEYS[2], ARGV[2])
redis.call('EXPIRE', KEYS[3], ARGV[2])
return event_id
"""

_REQUEST_STOP_SCRIPT = """
-- KEYS[1]=meta
-- ARGV[1]=ttl
if redis.call('EXISTS', KEYS[1]) == 0 then
  return 0
end
local status = redis.call('HGET', KEYS[1], 'status')
if not status then
  -- Legacy: treat closed=1 as terminal
  if redis.call('HGET', KEYS[1], 'closed') == '1' then
    return 0
  end
  status = 'pending'
end
if status ~= 'pending' then
  return 0
end
redis.call('HSET', KEYS[1], 'status', 'stopped')
redis.call('EXPIRE', KEYS[1], ARGV[1])
return 1
"""


def _wrap_sse_event_with_id(event: str, last_event_id: int) -> str:
    """Attach an SSE id line so clients can resume with Last-Event-ID."""
    return f"id: {last_event_id}\n{event}"


def _parse_event_id(entry_id: str) -> int:
    """Parse Redis Stream entry id ``{event_id}-0`` into an integer event id."""
    return int(entry_id.split("-", 1)[0])


def _as_str(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode()
    if isinstance(value, str):
        return value
    return str(value)


def _coerce_pair(raw: object) -> tuple[object, object] | None:
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        return raw[0], raw[1]
    return None


def _coerce_stream_entries(raw: object) -> list[tuple[str, dict[str, str]]]:
    if not isinstance(raw, list):
        return []
    entries: list[tuple[str, dict[str, str]]] = []
    for item in raw:
        pair = _coerce_pair(item)
        if pair is None:
            continue
        entry_id, fields = pair
        if not isinstance(fields, dict):
            continue
        entries.append(
            (
                _as_str(entry_id),
                {_as_str(k): _as_str(v) for k, v in fields.items()},
            )
        )
    return entries


def _coerce_xread_results(raw: object) -> list[tuple[str, dict[str, str]]]:
    if not isinstance(raw, list):
        return []
    entries: list[tuple[str, dict[str, str]]] = []
    for item in raw:
        pair = _coerce_pair(item)
        if pair is None:
            continue
        _stream_name, stream_entries = pair
        entries.extend(_coerce_stream_entries(stream_entries))
    return entries


def _parse_status(raw: object, closed: object = None) -> MessageStatus:
    """Parse meta status with legacy ``closed`` fallback."""
    status_str = _as_str(raw)
    if status_str:
        try:
            return MessageStatus(status_str)
        except ValueError:
            return MessageStatus.PENDING
    # Legacy keys that only have closed field
    if _as_str(closed) == "1":
        return MessageStatus.DONE
    return MessageStatus.PENDING


class StreamRelay:
    """Redis Stream relay for resumable SSE streams."""

    STREAM_KEY_PREFIX = "chat:sse:stream:"
    META_KEY_PREFIX = "chat:sse:meta:"
    SEQ_KEY_PREFIX = "chat:sse:seq:"

    def __init__(
        self,
        *,
        ttl_seconds: int | None = None,
        closed_ttl_seconds: int | None = None,
        xread_block_ms: int | None = None,
    ) -> None:
        cfg = settings.chat_stream
        self._ttl_seconds = (
            ttl_seconds if ttl_seconds is not None else cfg.sse_stream_ttl_seconds
        )
        self._closed_ttl_seconds = (
            closed_ttl_seconds
            if closed_ttl_seconds is not None
            else cfg.sse_stream_closed_ttl_seconds
        )
        self._xread_block_ms = (
            xread_block_ms
            if xread_block_ms is not None
            else cfg.sse_stream_xread_block_ms
        )
        self._append_script: Any | None = None
        self._request_stop_script: Any | None = None

    def _redis(self) -> Redis:
        return get_redis()

    def _stream_key(self, stream_id: str) -> str:
        return f"{self.STREAM_KEY_PREFIX}{stream_id}"

    def _meta_key(self, stream_id: str) -> str:
        return f"{self.META_KEY_PREFIX}{stream_id}"

    def _seq_key(self, stream_id: str) -> str:
        return f"{self.SEQ_KEY_PREFIX}{stream_id}"

    async def _read_status(self, meta_key: str) -> MessageStatus | None:
        redis = self._redis()
        if await redis.exists(meta_key) == 0:
            return None
        raw = await redis.hget(meta_key, "status")
        closed = await redis.hget(meta_key, "closed")
        return _parse_status(raw, closed)

    async def _eval_append(
        self, stream_key: str, meta_key: str, seq_key: str, payload: str, ttl: int
    ) -> int:
        redis = self._redis()
        if self._append_script is None:
            self._append_script = redis.register_script(_APPEND_SCRIPT)
        result = await self._append_script(
            keys=[stream_key, meta_key, seq_key],
            args=[payload, ttl],
        )
        return int(result)

    async def register(self, stream_id: str) -> None:
        redis = self._redis()
        meta_key = self._meta_key(stream_id)
        stream_key = self._stream_key(stream_id)
        seq_key = self._seq_key(stream_id)
        created = await redis.hsetnx(
            meta_key,
            "status",
            MessageStatus.PENDING.value,
        )
        if created:
            await redis.hset(
                meta_key,
                mapping={
                    "created_at": datetime.now(UTC).isoformat(),
                    "last_event_id": "0",
                },
            )
        await redis.expire(meta_key, self._ttl_seconds)
        await redis.expire(stream_key, self._ttl_seconds)
        await redis.expire(seq_key, self._ttl_seconds)

    async def append(self, stream_id: str, event: str) -> int:
        event_id = await self._eval_append(
            self._stream_key(stream_id),
            self._meta_key(stream_id),
            self._seq_key(stream_id),
            event,
            self._ttl_seconds,
        )
        return event_id

    async def close(
        self,
        stream_id: str,
        *,
        final_status: MessageStatus = MessageStatus.DONE,
    ) -> None:
        """Mark stream terminal. Preserves ``stopped``; only pending → final_status."""
        if final_status == MessageStatus.PENDING:
            raise ValueError("final_status must be a terminal MessageStatus")
        redis = self._redis()
        meta_key = self._meta_key(stream_id)
        stream_key = self._stream_key(stream_id)
        seq_key = self._seq_key(stream_id)
        current = await self._read_status(meta_key)
        if current is None:
            return
        if current == MessageStatus.PENDING:
            await redis.hset(meta_key, "status", final_status.value)
        # stopped / done / failed: keep existing status (idempotent)
        await redis.expire(meta_key, self._closed_ttl_seconds)
        await redis.expire(stream_key, self._closed_ttl_seconds)
        await redis.expire(seq_key, self._closed_ttl_seconds)

    async def get_status(self, stream_id: str) -> MessageStatus | None:
        return await self._read_status(self._meta_key(stream_id))

    async def request_stop(self, stream_id: str) -> bool:
        """CAS pending → stopped. Returns True if transition applied."""
        redis = self._redis()
        if self._request_stop_script is None:
            self._request_stop_script = redis.register_script(_REQUEST_STOP_SCRIPT)
        result = await self._request_stop_script(
            keys=[self._meta_key(stream_id)],
            args=[self._ttl_seconds],
        )
        return int(result) == 1

    async def is_stop_requested(self, stream_id: str) -> bool:
        return await self.get_status(stream_id) == MessageStatus.STOPPED

    async def has_stream(self, stream_id: str) -> bool:
        redis = self._redis()
        meta_key = self._meta_key(stream_id)
        status = await self._read_status(meta_key)
        if status is None:
            return False
        if status == MessageStatus.PENDING:
            return True
        # Terminal but still within TTL: allow resume to replay remaining events.
        stream_key = self._stream_key(stream_id)
        return await redis.exists(stream_key) == 1

    async def iter_resume(
        self, stream_id: str, last_event_id: int
    ) -> AsyncGenerator[str, None]:
        redis = self._redis()
        stream_key = self._stream_key(stream_id)
        meta_key = self._meta_key(stream_id)

        try:
            if await redis.exists(meta_key) == 0:
                return
        except _TRANSIENT_REDIS_ERRORS as exc:
            logger.warning(
                "SSE resume aborted: Redis unavailable on meta exists",
                stream_id=stream_id,
                error=exc,
                error_type=type(exc).__name__,
            )
            raise

        cursor_event_id = max(last_event_id, 0)
        # Exclusive lower bound: entries with id > last_event_id
        min_id = f"({cursor_event_id}-0" if cursor_event_id > 0 else "-"

        try:
            replay_raw = await redis.xrange(stream_key, min=min_id, max="+")
        except ResponseError:
            replay_raw = None
        except _TRANSIENT_REDIS_ERRORS as exc:
            logger.warning(
                "SSE resume aborted: Redis unavailable on xrange replay",
                stream_id=stream_id,
                error=exc,
                error_type=type(exc).__name__,
            )
            raise

        for entry_id, fields in _coerce_stream_entries(replay_raw):
            event_id = _parse_event_id(entry_id)
            if event_id <= cursor_event_id:
                continue
            payload = fields.get("payload", "")
            yield _wrap_sse_event_with_id(payload, event_id)
            cursor_event_id = event_id

        transient_failures = 0
        while True:
            try:
                status = await self._read_status(meta_key)
                xread_id = f"{cursor_event_id}-0" if cursor_event_id > 0 else "0-0"
                try:
                    results = await redis.xread(
                        {stream_key: xread_id},
                        block=self._xread_block_ms,
                        count=50,
                    )
                except ResponseError:
                    results = None
                transient_failures = 0
            except _TRANSIENT_REDIS_ERRORS as exc:
                transient_failures += 1
                logger.warning(
                    "SSE XREAD transient Redis error",
                    stream_id=stream_id,
                    attempt=transient_failures,
                    max_attempts=_MAX_XREAD_TRANSIENT_FAILURES,
                    error=exc,
                    error_type=type(exc).__name__,
                )
                if transient_failures >= _MAX_XREAD_TRANSIENT_FAILURES:
                    raise
                await asyncio.sleep(min(0.5 * transient_failures, 2.0))
                continue

            if results:
                for entry_id, fields in _coerce_xread_results(results):
                    event_id = _parse_event_id(entry_id)
                    if event_id <= cursor_event_id:
                        continue
                    payload = fields.get("payload", "")
                    yield _wrap_sse_event_with_id(payload, event_id)
                    cursor_event_id = event_id
                continue

            if status is not None and status != MessageStatus.PENDING:
                # Re-check once for late arrivals after terminal status.
                try:
                    late_raw = await redis.xrange(
                        stream_key,
                        min=f"({cursor_event_id}-0" if cursor_event_id > 0 else "-",
                        max="+",
                    )
                except ResponseError:
                    late_raw = None
                except _TRANSIENT_REDIS_ERRORS as exc:
                    logger.warning(
                        "SSE resume aborted: Redis unavailable on late xrange",
                        stream_id=stream_id,
                        error=exc,
                        error_type=type(exc).__name__,
                    )
                    raise
                late_entries = _coerce_stream_entries(late_raw)
                if not late_entries:
                    return
                for entry_id, fields in late_entries:
                    event_id = _parse_event_id(entry_id)
                    if event_id <= cursor_event_id:
                        continue
                    payload = fields.get("payload", "")
                    yield _wrap_sse_event_with_id(payload, event_id)
                    cursor_event_id = event_id
                return

            try:
                if await redis.exists(meta_key) == 0:
                    return
            except _TRANSIENT_REDIS_ERRORS as exc:
                transient_failures += 1
                logger.warning(
                    "SSE meta exists transient Redis error",
                    stream_id=stream_id,
                    attempt=transient_failures,
                    max_attempts=_MAX_XREAD_TRANSIENT_FAILURES,
                    error=exc,
                    error_type=type(exc).__name__,
                )
                if transient_failures >= _MAX_XREAD_TRANSIENT_FAILURES:
                    raise
                await asyncio.sleep(min(0.5 * transient_failures, 2.0))
                continue
