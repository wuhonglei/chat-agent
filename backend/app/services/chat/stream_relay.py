"""SSE stream relay with resumable ring buffer."""

from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field


@dataclass(frozen=True)
class _StreamEvent:
    seq: int
    payload: str


class _Terminal:
    """Sentinel value for subscriber completion."""


@dataclass
class _RelayEntry:
    events: deque[_StreamEvent]
    next_seq: int = 1
    closed: bool = False
    subscribers: set[asyncio.Queue[_StreamEvent | _Terminal]] = field(
        default_factory=set
    )


def _inject_seq_into_sse_payload(event: str, seq: int) -> str:
    """Inject sequence number into the SSE JSON payload."""
    prefix = "data: "
    if not event.startswith(prefix):
        return event
    body = event[len(prefix) :].strip()
    try:
        payload = json.loads(body)
    except Exception:
        return event
    if not isinstance(payload, dict):
        return event
    payload["seq"] = seq
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


class StreamRelay:
    """In-memory relay for resumable SSE streams."""

    def __init__(self, *, max_events: int = 2000):
        self._entries: dict[str, _RelayEntry] = {}
        self._lock = asyncio.Lock()
        self._max_events = max_events

    async def register(self, stream_id: str) -> None:
        async with self._lock:
            if stream_id in self._entries:
                return
            self._entries[stream_id] = _RelayEntry(
                events=deque(maxlen=self._max_events)
            )

    async def append(self, stream_id: str, event: str) -> int:
        async with self._lock:
            entry = self._entries.get(stream_id)
            if entry is None:
                entry = _RelayEntry(events=deque(maxlen=self._max_events))
                self._entries[stream_id] = entry
            if entry.closed:
                return entry.next_seq - 1

            seq = entry.next_seq
            entry.next_seq += 1
            wrapped_event = _inject_seq_into_sse_payload(event, seq)
            stream_event = _StreamEvent(seq=seq, payload=wrapped_event)
            entry.events.append(stream_event)
            for queue in entry.subscribers:
                queue.put_nowait(stream_event)
            return seq

    async def close(self, stream_id: str) -> None:
        async with self._lock:
            entry = self._entries.pop(stream_id, None)
            if entry is None:
                return
            entry.closed = True
            terminal = _Terminal()
            for queue in entry.subscribers:
                queue.put_nowait(terminal)

    async def has_stream(self, stream_id: str) -> bool:
        async with self._lock:
            return stream_id in self._entries

    async def iter_resume(
        self, stream_id: str, after_seq: int
    ) -> AsyncGenerator[str, None]:
        queue: asyncio.Queue[_StreamEvent | _Terminal] | None = None
        replay_events: list[_StreamEvent] = []
        async with self._lock:
            entry = self._entries.get(stream_id)
            if entry is None:
                return
            replay_events = [event for event in entry.events if event.seq > after_seq]
            if not entry.closed:
                queue = asyncio.Queue()
                entry.subscribers.add(queue)

        try:
            for event in replay_events:
                yield event.payload
                after_seq = max(after_seq, event.seq)

            if queue is None:
                return

            while True:
                item = await queue.get()
                if isinstance(item, _Terminal):
                    return
                if item.seq <= after_seq:
                    continue
                after_seq = item.seq
                yield item.payload
        finally:
            if queue is not None:
                async with self._lock:
                    entry = self._entries.get(stream_id)
                    if entry is not None:
                        entry.subscribers.discard(queue)
