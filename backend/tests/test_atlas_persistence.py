"""Focused Atlas persistence tests.

The unit checks run offline. The live round-trip is opt-in and uses the real
``backend/.env`` MONGODB_URI (never printed)::

    ATLAS_LIVE_TESTS=1 uv run pytest -q tests/test_atlas_persistence.py
"""

import os
from datetime import UTC, datetime

import pytest

from app.config import Settings
from app.memory.mongodb import MongoRepository
from app.models.audit import RunReport
from app.models.events import ArenaEvent

PROBE_RUN = "ATLAS-PYTEST-PROBE"


def test_document_sanitizes_mongo_id_before_strict_validation() -> None:
    raw = {
        "_id": "server-minted",
        "run_id": "r1",
        "red_model": "m",
        "blue_model": "m",
        "red_provider": "p",
        "blue_provider": "p",
        "generations": 0,
        "red_versions_created": 0,
        "blue_versions_created": 0,
        "attacks_generated": 0,
        "attacks_successful": 0,
        "harness_patches_generated": 0,
        "candidates_compiled": 0,
        "candidates_promoted": 0,
        "total_model_calls": 0,
    }
    stripped = MongoRepository._document(raw)
    assert stripped is not None
    assert "_id" not in stripped
    report = RunReport.model_validate(stripped)  # extra="forbid" would reject a raw _id
    assert report.run_id == "r1"
    assert MongoRepository._document(None) is None


@pytest.mark.skipif(
    os.environ.get("ATLAS_LIVE_TESTS") != "1",
    reason="set ATLAS_LIVE_TESTS=1 to exercise the real Atlas deployment",
)
async def test_live_disposable_roundtrip_through_fresh_repository_instances() -> None:
    settings = Settings()
    if not settings.mongodb_uri:
        pytest.skip("MONGODB_URI is not configured")

    writer = MongoRepository(settings.mongodb_uri, settings.mongodb_database, settings.embedding_dimensions)
    await writer.start()
    try:
        await writer.save_event(
            ArenaEvent(
                type="run_finished",
                run_id=PROBE_RUN,
                generation=0,
                payload={"probe": "pytest"},
                created_at=datetime.now(UTC),
            )
        )
    finally:
        await writer.close()

    reader = MongoRepository(settings.mongodb_uri, settings.mongodb_database, settings.embedding_dimensions)
    await reader.start()
    try:
        events = [event for event in await reader.recent_events(limit=500) if event.run_id == PROBE_RUN]
        assert len(events) == 1
        assert events[0].payload["probe"] == "pytest"
    finally:
        document = await reader.db.arena_events.find_one({"run_id": PROBE_RUN})
        assert document is not None
        deleted = await reader.db.arena_events.delete_many({"_id": document["_id"]})
        assert deleted.deleted_count == 1
        await reader.close()
