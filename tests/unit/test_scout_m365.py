"""Scout snapshot adapter tests for FR-903, FR-907, and FR-908."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ea_copilot.adapters.clock_fixed import FixedClock
from ea_copilot.adapters.scout_m365 import ScoutM365Adapter
from ea_copilot.domain.errors import CalendarWritesDisabledError, FixtureMissingError
from ea_copilot.domain.live_models import ScoutCalendarSnapshot
from ea_copilot.domain.models import (
    CalendarEvent,
    ChatMessage,
    DataLimitation,
    FileReference,
    FreeBusySlot,
    MailMessage,
    ScheduleResponse,
    TimeSlot,
    WorkingHours,
)

NOW = datetime(2026, 9, 14, 13, 0, tzinfo=UTC)


def working_hours() -> WorkingHours:
    return WorkingHours(
        days_of_week=["monday", "tuesday", "wednesday", "thursday", "friday"],
        start_time="08:00:00",  # type: ignore[arg-type]
        end_time="17:00:00",  # type: ignore[arg-type]
        time_zone="Central Standard Time",
    )


def snapshot() -> ScoutCalendarSnapshot:
    free = FreeBusySlot(
        start=datetime(2026, 9, 15, 15, 0, tzinfo=UTC),
        end=datetime(2026, 9, 15, 16, 0, tzinfo=UTC),
        status="free",
    )
    busy = CalendarEvent(
        event_id="opaque-event-1",
        subject="Private strategy",
        body_preview="Private body",
        start=datetime(2026, 9, 15, 14, 0, tzinfo=UTC),
        end=datetime(2026, 9, 15, 14, 30, tzinfo=UTC),
        show_as="busy",
    )
    return ScoutCalendarSnapshot(
        request_id="REQ-SCOUT-1",
        captured_at=NOW,
        schedules=[
            ScheduleResponse(upn="alpha-mailbox-id", slots=[free], working_hours=working_hours()),
            ScheduleResponse(upn="beta-mailbox-id", slots=[free], working_hours=working_hours()),
        ],
        events={"alpha-mailbox-id": [busy], "beta-mailbox-id": []},
        mail=[
            MailMessage(
                message_id="mail-1",
                subject="Decision background",
                body_preview="Forecast decision context",
                web_url="https://example.invalid/mail/1",
                received_at=NOW,
            )
        ],
        teams=[
            ChatMessage(
                message_id="chat-1",
                topic="Forecast",
                body="Decision discussion",
                web_url="https://example.invalid/chat/1",
                created_at=NOW,
            )
        ],
        files=[
            FileReference(
                file_id="file-1",
                name="forecast.pdf",
                excerpt="Q4 decision",
                web_url="https://example.invalid/file/1",
                modified_at=NOW,
            )
        ],
        limitations=[
            DataLimitation(subject="related mailbox detail", limitation="Delegated access denied")
        ],
    )


def test_FR_908_scout_adapter_fails_closed_before_snapshot_ingestion() -> None:
    adapter = ScoutM365Adapter(FixedClock(NOW))

    with pytest.raises(FixtureMissingError, match="Scout calendar snapshot"):
        adapter.get_schedule(["alpha-mailbox-id"], TimeSlot(start=NOW, end=NOW + timedelta(days=1)))


def test_FR_903_scout_snapshot_drives_all_read_surfaces_without_network() -> None:
    adapter = ScoutM365Adapter(FixedClock(NOW))
    adapter.ingest(snapshot())
    window = TimeSlot(start=NOW, end=NOW + timedelta(days=2))

    ordered = adapter.get_schedule(["beta-mailbox-id", "alpha-mailbox-id"], window)
    assert [item.upn for item in ordered] == [
        "beta-mailbox-id",
        "alpha-mailbox-id",
    ]
    assert adapter.get_working_hours("alpha-mailbox-id") == working_hours()
    assert [item.event_id for item in adapter.get_calendar_view("alpha-mailbox-id", window)] == [
        "opaque-event-1"
    ]
    assert adapter.find_meeting_times(
        ["alpha-mailbox-id", "beta-mailbox-id"], timedelta(minutes=30), window
    ) == [
        TimeSlot(
            start=datetime(2026, 9, 15, 15, 0, tzinfo=UTC),
            end=datetime(2026, 9, 15, 15, 30, tzinfo=UTC),
        )
    ]
    assert [item.message_id for item in adapter.search_mail("forecast")] == ["mail-1"]
    assert [item.message_id for item in adapter.search_teams("decision")] == ["chat-1"]
    assert [item.file_id for item in adapter.search_files("q4")] == ["file-1"]
    events, token = adapter.delta_events("alpha-mailbox-id", None)
    assert [item.event_id for item in events] == ["opaque-event-1"]
    assert token.startswith("DELTA-")
    assert adapter.network_calls == 0


def test_FR_906_scout_adapter_has_no_calendar_write_before_draft_bridge() -> None:
    adapter = ScoutM365Adapter(FixedClock(NOW))
    adapter.ingest(snapshot())

    with pytest.raises(CalendarWritesDisabledError, match="draft bridge"):
        adapter.create_draft_event(
            organiser="demo-user-id",
            subject="[DEMO] Executive scheduling prototype",
            body="Draft only",
            slot=TimeSlot(start=NOW, end=NOW + timedelta(minutes=30)),
            required=["demo-user-id"],
            optional=[],
            location=None,
        )
