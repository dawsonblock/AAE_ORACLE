"""tests/replay/test_event_replay.py

Replay test: write events to JSONL event store, replay them back and assert
ordering + payload fidelity. No external services required (JSONL only).
"""
from __future__ import annotations

import pytest


class TestEventReplay:
    """Event store JSONL write + replay assertion."""

    @pytest.fixture
    def event_store(self, tmp_path):
        from aae.events.event_store import EventStore
        store = EventStore(jsonl_path=str(tmp_path / "events.jsonl"))
        return store

    @pytest.mark.asyncio
    async def test_write_and_replay_order(self, event_store):
        events = [
            {"type": "task_created", "task_id": "t1", "seq": 0},
            {"type": "task_started", "task_id": "t1", "seq": 1},
            {"type": "task_completed", "task_id": "t1", "seq": 2},
        ]
        for ev in events:
            event_store.append(ev)  # sync

        replayed = await event_store.replay()
        assert len(replayed) == 3
        for i, ev in enumerate(replayed):
            assert ev["seq"] == i

    @pytest.mark.asyncio
    async def test_replay_payload_fidelity(self, event_store):
        payload = {
            "type": "patch_applied",
            "task_id": "t99",
            "file": "src/main.py",
            "lines_changed": 5,
        }
        event_store.append(payload)  # sync
        replayed = await event_store.replay()
        assert len(replayed) == 1
        assert replayed[0]["file"] == "src/main.py"
        assert replayed[0]["lines_changed"] == 5

    @pytest.mark.asyncio
    async def test_replay_empty_store(self, event_store):
        replayed = await event_store.replay()
        assert replayed == []

    @pytest.mark.asyncio
    async def test_replay_multiple_batches(self, event_store):
        event_store.append({"type": "a", "seq": 0})
        event_store.append({"type": "b", "seq": 1})
        event_store.append({"type": "c", "seq": 2})

        replayed = await event_store.replay()
        assert len(replayed) == 3
        types = [ev["type"] for ev in replayed]
        assert types == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_replay_filter_by_type(self, event_store):
        event_store.append({"type": "task_created", "task_id": "t1"})
        event_store.append({"type": "task_started", "task_id": "t1"})
        event_store.append({"type": "task_created", "task_id": "t2"})

        all_events = await event_store.replay()
        created = [
            ev for ev in all_events if ev["type"] == "task_created"
        ]
        assert len(created) == 2
