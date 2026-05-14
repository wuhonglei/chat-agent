"""SSE stream relay with resumable ring buffer."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field


@dataclass(frozen=True)
class _StreamEvent:
    last_event_id: int
    payload: str


class _Terminal:
    """Sentinel value for subscriber completion."""


@dataclass
class _RelayEntry:
    events: deque[_StreamEvent]
    next_event_id: int = 1
    closed: bool = False
    subscribers: set[asyncio.Queue[_StreamEvent | _Terminal]] = field(
        default_factory=set
    )


def _wrap_sse_event_with_id(event: str, last_event_id: int) -> str:
    """Attach an SSE id line so clients can resume with Last-Event-ID."""
    return f"id: {last_event_id}\n{event}"


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
                return entry.next_event_id - 1

            last_event_id = entry.next_event_id
            entry.next_event_id += 1
            wrapped_event = _wrap_sse_event_with_id(event, last_event_id)
            stream_event = _StreamEvent(
                last_event_id=last_event_id,
                payload=wrapped_event,
            )
            entry.events.append(stream_event)
            for queue in entry.subscribers:
                queue.put_nowait(stream_event)
            return last_event_id

    async def close(self, stream_id: str) -> None:
        async with self._lock:
            entry = self._entries.get(stream_id)
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
        self, stream_id: str, last_event_id: int
    ) -> AsyncGenerator[str, None]:
        queue: asyncio.Queue[_StreamEvent | _Terminal] | None = None
        replay_events: list[_StreamEvent] = []
        async with self._lock:
            entry = self._entries.get(stream_id)
            if entry is None:
                return
            replay_events = [
                event for event in entry.events if event.last_event_id > last_event_id
            ]
            if not entry.closed:
                queue = asyncio.Queue()
                entry.subscribers.add(queue)

        try:
            for event in replay_events:
                yield event.payload
                last_event_id = max(last_event_id, event.last_event_id)

            if queue is None:
                return

            while True:
                item = await queue.get()
                if isinstance(item, _Terminal):
                    return
                if item.last_event_id <= last_event_id:
                    continue
                last_event_id = item.last_event_id
                yield item.payload
        finally:
            if queue is not None:
                async with self._lock:
                    entry = self._entries.get(stream_id)
                    if entry is not None:
                        entry.subscribers.discard(queue)
