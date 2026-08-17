"""In-memory event bus for streaming pipeline/agent events to SSE clients.

A pipeline run publishes events to a channel keyed by project id; any number
of SSE subscribers can attach and receive them in real time. Channels keep a
short replay buffer so a client that connects slightly late still sees the
recent history.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from typing import Any, AsyncGenerator, Deque, Dict, List

_BUFFER_SIZE = 200


class EventBus:
    def __init__(self) -> None:
        self._subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        self._history: Dict[str, Deque[Dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=_BUFFER_SIZE)
        )
        self._lock = asyncio.Lock()

    async def publish(self, channel: str, event: Dict[str, Any]) -> None:
        event = {"ts": time.time(), **event}
        async with self._lock:
            self._history[channel].append(event)
            for q in list(self._subscribers.get(channel, [])):
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:  # pragma: no cover - defensive
                    pass

    async def subscribe(self, channel: str, replay: bool = True) -> AsyncGenerator[Dict[str, Any], None]:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        async with self._lock:
            self._subscribers[channel].append(q)
            backlog = list(self._history.get(channel, [])) if replay else []
        try:
            for ev in backlog:
                yield ev
            while True:
                ev = await q.get()
                yield ev
                if ev.get("type") in ("pipeline.complete", "pipeline.failed"):
                    break
        finally:
            async with self._lock:
                subs = self._subscribers.get(channel, [])
                if q in subs:
                    subs.remove(q)

    def clear(self, channel: str) -> None:
        self._history.pop(channel, None)


_bus = EventBus()


def get_event_bus() -> EventBus:
    return _bus
