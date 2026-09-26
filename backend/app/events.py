import asyncio
from collections.abc import AsyncIterator

from app.models.events import ArenaEvent


class ArenaEventBus:
    def __init__(self, history_size: int = 500) -> None:
        self._subscribers: set[asyncio.Queue[ArenaEvent]] = set()
        self._history: list[ArenaEvent] = []
        self._history_size = history_size
        self._lock = asyncio.Lock()

    async def publish(self, event: ArenaEvent) -> None:
        async with self._lock:
            self._history.append(event)
            if len(self._history) > self._history_size:
                self._history = self._history[-self._history_size :]
            subscribers = tuple(self._subscribers)
        for queue in subscribers:
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(event)

    async def subscribe(self) -> AsyncIterator[ArenaEvent]:
        queue: asyncio.Queue[ArenaEvent] = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._subscribers.add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            async with self._lock:
                self._subscribers.discard(queue)

    async def history(self, limit: int = 100) -> list[ArenaEvent]:
        async with self._lock:
            return list(self._history[-limit:])

    async def clear(self) -> None:
        async with self._lock:
            self._history.clear()
