"""Focused offline tests for the MongoDB change-stream bridge.

The bridge relays two independent collections: ``episodes`` (battle_finished) and
``arena_events`` (the engine's typed events — how a CLI co-evolution run reaches
``/ws/arena``). A stub async client pins the relay shape, ``_id`` stripping, malformed
document handling and failure isolation without a live MongoDB.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from app.memory.change_stream import MongoChangeStreamBridge
from app.models.events import ArenaEvent

BASE = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)


class _StubStream:
    """Awaitable-to-get stream that is also an async context manager and iterator."""

    def __init__(self, changes: list[dict[str, Any]], fail: Exception | None) -> None:
        self._changes = changes
        self._fail = fail

    async def __aenter__(self) -> "_StubStream":
        if self._fail is not None:
            raise self._fail
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    async def __aiter__(self) -> AsyncIterator[dict[str, Any]]:
        for change in self._changes:
            yield change


class _StubCollection:
    def __init__(self, changes: list[dict[str, Any]], fail: Exception | None = None) -> None:
        self._changes = changes
        self._fail = fail

    async def watch(self) -> _StubStream:
        return _StubStream(self._changes, self._fail)


class _StubDatabase:
    def __init__(self, episodes: _StubCollection, events: _StubCollection) -> None:
        self.episodes = episodes
        self.arena_events = events


class _StubClient:
    def __init__(self, database: _StubDatabase) -> None:
        self._database = database

    def __getitem__(self, name: str) -> _StubDatabase:
        return self._database


def _event_document(**overrides: object) -> dict[str, object]:
    document: dict[str, object] = {
        "_id": "mongo-minted",
        "type": "generation_started",
        "run_id": "LIVE-CHECK",
        "generation": 0,
        "payload": {"source": "test"},
        "created_at": BASE,
    }
    document.update(overrides)
    return document


def _bridge(
    episodes: _StubCollection, events: _StubCollection, published: list[ArenaEvent]
) -> MongoChangeStreamBridge:
    async def publish(event: ArenaEvent) -> None:
        published.append(event)

    return MongoChangeStreamBridge(
        client=_StubClient(_StubDatabase(episodes, events)),  # type: ignore[arg-type]
        database="darwinguard",
        publish=publish,
    )


async def test_bridge_relays_stored_arena_events_and_strips_mongo_id() -> None:
    published: list[ArenaEvent] = []
    changes = [
        {"fullDocument": _event_document()},
        # A malformed row is skipped, not fatal to the stream.
        {"fullDocument": _event_document(type="not_a_real_type")},
        {"fullDocument": None},
        {"fullDocument": _event_document(type="run_report", generation=1)},
    ]
    bridge = _bridge(_StubCollection([]), _StubCollection(changes), published)

    await bridge._consume_events()

    assert [event.type for event in published] == ["generation_started", "run_report"]
    assert published[0].run_id == "LIVE-CHECK"
    assert published[0].payload == {"source": "test"}
    assert published[1].generation == 1


async def test_episode_stream_still_publishes_battle_finished() -> None:
    published: list[ArenaEvent] = []
    episode = {"_id": "e1", "run_id": "R1", "generation": 2, "created_at": BASE}
    bridge = _bridge(_StubCollection([{"fullDocument": episode}]), _StubCollection([]), published)

    await bridge._consume()

    assert [event.type for event in published] == ["battle_finished"]
    assert published[0].payload == {"episode": episode, "source": "change_stream"}


async def test_one_failed_stream_leaves_the_other_relaying() -> None:
    published: list[ArenaEvent] = []
    database = _StubDatabase(
        _StubCollection([], fail=RuntimeError("episodes stream down")),
        _StubCollection([{"fullDocument": _event_document()}]),
    )

    async def publish(event: ArenaEvent) -> None:
        published.append(event)

    bridge = MongoChangeStreamBridge(
        client=_StubClient(database),  # type: ignore[arg-type]
        database="darwinguard",
        publish=publish,
    )

    # The episodes failure is swallowed by its own stream...
    await bridge._consume()
    # ...and the arena_events stream still relays.
    await bridge._consume_events()

    assert [event.type for event in published] == ["generation_started"]
