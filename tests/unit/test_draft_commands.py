"""Append-only two-phase draft command tests for FR-906, INV-1, and INV-2."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from ea_copilot.domain.errors import DraftCompletionError
from ea_copilot.domain.live_models import DraftCommand, DraftCompletion
from ea_copilot.domain.models import TimeSlot
from ea_copilot.services.database import Database
from ea_copilot.services.draft_commands import DraftCommandStore

NOW = datetime(2026, 9, 14, 13, 0, tzinfo=UTC)


def command() -> DraftCommand:
    return DraftCommand(
        command_id="CMD-1",
        transaction_id="TX-1",
        request_id="REQ-1",
        recommendation_id="REC-1",
        approval_id="APR-1",
        subject="[DEMO] Executive scheduling prototype",
        body="Draft only",
        slot=TimeSlot(start=NOW, end=NOW + timedelta(minutes=30)),
        attendee="demo-user-id",
        draft=True,
        created_at=NOW,
    )


def completion(**updates: object) -> DraftCompletion:
    values: dict[str, object] = {
        "command_id": "CMD-1",
        "transaction_id": "TX-1",
        "graph_event_id": "GRAPH-DRAFT-1",
        "web_link": "https://example.invalid/drafts/1",
        "draft": True,
        "completed_at": NOW + timedelta(seconds=1),
    }
    values.update(updates)
    return DraftCompletion.model_validate(values)


def test_FR_906_command_store_appends_then_completes_exactly_once() -> None:
    store = DraftCommandStore(Database.memory())
    stored = store.append(command())

    assert stored == command()
    assert store.pending() == [command()]

    event = store.complete(completion())
    duplicate = store.complete(completion())
    assert duplicate == event
    assert event.request_id == "REQ-1"
    assert event.recommendation_id == "REC-1"
    assert event.approval_id == "APR-1"
    assert event.graph_event_id == "GRAPH-DRAFT-1"
    assert event.is_sent is False
    assert store.pending() == []
    assert not hasattr(store, "update")
    assert not hasattr(store, "delete")


def test_FR_906_completion_must_match_command_and_transaction() -> None:
    store = DraftCommandStore(Database.memory())
    store.append(command())

    with pytest.raises(DraftCompletionError, match="transaction"):
        store.complete(completion(transaction_id="TX-WRONG"))
    with pytest.raises(DraftCompletionError, match="command"):
        store.complete(completion(command_id="CMD-WRONG"))
    assert store.pending() == [command()]


def test_FR_906_draft_false_is_rejected_by_the_data_contract() -> None:
    with pytest.raises(ValidationError, match="draft"):
        completion(draft=False)
