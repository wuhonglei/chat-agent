"""SSE stream relay backed by Redis Stream for resumable multi-worker buffering."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from app.core.config import settings
from app.core.redis import get_redis

_APPEND_SCRIPT = """
-- KEYS[1]=stream, KEYS[2]=meta, KEYS[3]=seq
-- ARGV[1]=payload, ARGV[2]=ttl
if redis.call('HGET', KEYS[2], 'closed') == '1' then
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

    def _redis(self) -> Redis:
        return get_redis()

    def _stream_key(self, stream_id: str) -> str:
        return f"{self.STREAM_KEY_PREFIX}{stream_id}"

    def _meta_key(self, stream_id: str) -> str:
        return f"{self.META_KEY_PREFIX}{stream_id}"

    def _seq_key(self, stream_id: str) -> str:
        return f"{self.SEQ_KEY_PREFIX}{stream_id}"

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
            "closed",
            "0",
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

    async def close(self, stream_id: str) -> None:
        redis = self._redis()
        meta_key = self._meta_key(stream_id)
        stream_key = self._stream_key(stream_id)
        seq_key = self._seq_key(stream_id)
        if await redis.exists(meta_key) == 0:
            return
        await redis.hset(meta_key, "closed", "1")
        await redis.expire(meta_key, self._closed_ttl_seconds)
        await redis.expire(stream_key, self._closed_ttl_seconds)
        await redis.expire(seq_key, self._closed_ttl_seconds)

    async def has_stream(self, stream_id: str) -> bool:
        redis = self._redis()
        meta_key = self._meta_key(stream_id)
        if await redis.exists(meta_key) == 0:
            return False
        closed = await redis.hget(meta_key, "closed")
        if closed != "1":
            return True
        # Closed but still within TTL: allow resume to replay remaining events.
        stream_key = self._stream_key(stream_id)
        return await redis.exists(stream_key) == 1

    async def iter_resume(
        self, stream_id: str, last_event_id: int
    ) -> AsyncGenerator[str, None]:
        redis = self._redis()
        stream_key = self._stream_key(stream_id)
        meta_key = self._meta_key(stream_id)

        if await redis.exists(meta_key) == 0:
            return

        cursor_event_id = max(last_event_id, 0)
        # Exclusive lower bound: entries with id > last_event_id
        min_id = f"({cursor_event_id}-0" if cursor_event_id > 0 else "-"

        try:
            replay_raw = await redis.xrange(stream_key, min=min_id, max="+")
        except ResponseError:
            replay_raw = None

        for entry_id, fields in _coerce_stream_entries(replay_raw):
            event_id = _parse_event_id(entry_id)
            if event_id <= cursor_event_id:
                continue
            payload = fields.get("payload", "")
            yield _wrap_sse_event_with_id(payload, event_id)
            cursor_event_id = event_id

        while True:
            closed = await redis.hget(meta_key, "closed")
            xread_id = f"{cursor_event_id}-0" if cursor_event_id > 0 else "0-0"
            try:
                results = await redis.xread(
                    {stream_key: xread_id},
                    block=self._xread_block_ms,
                    count=50,
                )
            except ResponseError:
                results = None

            if results:
                for entry_id, fields in _coerce_xread_results(results):
                    event_id = _parse_event_id(entry_id)
                    if event_id <= cursor_event_id:
                        continue
                    payload = fields.get("payload", "")
                    yield _wrap_sse_event_with_id(payload, event_id)
                    cursor_event_id = event_id
                continue

            if closed == "1":
                # Re-check once for late arrivals after close.
                try:
                    late_raw = await redis.xrange(
                        stream_key,
                        min=f"({cursor_event_id}-0" if cursor_event_id > 0 else "-",
                        max="+",
                    )
                except ResponseError:
                    late_raw = None
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

            if await redis.exists(meta_key) == 0:
                return
