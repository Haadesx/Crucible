from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

if TYPE_CHECKING:
    from pymongo import AsyncMongoClient
else:
    # The name is only ever needed at runtime by something other than an
    # annotation, and ``from __future__ import annotations`` makes every annotation a
    # string, so a minimal install without pymongo still imports. A checker reads the
    # TYPE_CHECKING branch and sees the real client type, which is why this is a guard
    # rather than a try/except that overwrites the class with ``Any`` and erases the
    # caller's signature.
    try:
        from pymongo import AsyncMongoClient
    except ImportError:  # pragma: no cover - exercised only in minimal demo installs
        pass

from app.models.events import ArenaEvent

logger = logging.getLogger(__name__)


class MongoChangeStreamBridge:
    """Best-effort bridge from MongoDB writes to the internal event bus.

    Two independent streams: ``episodes`` (durable battle results) and ``arena_events``
    (the engine's typed events, which is how a CLI co-evolution run reaches the
    observer's ``/ws/arena``). Each stream has its own task and swallows its own
    failures, so one collection going down cannot silence the other.
    """

    def __init__(
        self,
        # PyMongo parameterises the client by document type; this bridge reads raw
        # documents, so the untyped mapping is the honest one.
        client: AsyncMongoClient[dict[str, Any]],
        database: str,
        publish: Callable[[ArenaEvent], Awaitable[None]],
    ) -> None:
        self.client = client
        self.database = database
        self.publish = publish
        self.task: asyncio.Task[None] | None = None
        self.events_task: asyncio.Task[None] | None = None

    def start(self) -> None:
        self.task = asyncio.create_task(self._consume(), name="darwinguard-change-stream")
        self.events_task = asyncio.create_task(
            self._consume_events(), name="darwinguard-change-stream-events"
        )

    async def stop(self) -> None:
        for task in (self.task, self.events_task):
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    async def _consume(self) -> None:
        try:
            # PyMongo's async ``watch`` is itself a coroutine returning the stream, so
            # entering it as a context manager without awaiting first raised "'coroutine'
            # object does not support the asynchronous context manager protocol" and the
            # bridge silently published nothing.
            stream = await self.client[self.database].episodes.watch()
            async with stream:
                async for change in stream:
                    document = change.get("fullDocument")
                    if not document:
                        continue
                    # Episode documents already contain the durable battle result.
                    # The internal bus receives a compact event rather than a raw BSON payload.
                    await self.publish(
                        ArenaEvent.model_validate(
                            {
                                "type": "battle_finished",
                                "run_id": document.get("run_id", "MONGO"),
                                "generation": document.get("generation", 0),
                                "payload": {"episode": document, "source": "change_stream"},
                                "created_at": document.get("created_at"),
                            }
                        )
                    )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(
                "MongoDB episodes change stream stopped; arena_events stream remains active: %s", exc
            )

    async def _consume_events(self) -> None:
        """Relay every persisted ``ArenaEvent`` written by another process.

        The co-evolution CLI writes its full typed event stream to ``arena_events``; this
        stream is what makes ``/ws/arena`` follow a CLI run live. One malformed document
        is skipped, not fatal.
        """

        try:
            stream = await self.client[self.database].arena_events.watch()
            async with stream:
                async for change in stream:
                    document = change.get("fullDocument")
                    if not document:
                        continue
                    # Mongo mints ``_id`` on insert; ``ArenaEvent`` forbids extra fields.
                    stored = dict(document)
                    stored.pop("_id", None)
                    try:
                        event = ArenaEvent.model_validate(stored)
                    except ValidationError as exc:
                        logger.warning("Skipping malformed arena_event change: %s", exc)
                        continue
                    await self.publish(event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(
                "MongoDB arena_events change stream stopped; episodes stream remains active: %s", exc
            )
