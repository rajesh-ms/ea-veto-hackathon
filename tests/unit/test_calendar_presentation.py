"""Privacy-safe calendar presentation tests for FR-902 and FR-903."""

from __future__ import annotations

from datetime import datetime

from ea_copilot.domain.models import CalendarEvent, FreeBusySlot, ScheduleResponse, TimeSlot
from ea_copilot.services.aliases import AliasDirectory
from ea_copilot.services.presentation import build_calendar_board


def instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_FR_903_calendar_board_has_two_ordered_alias_lanes_and_generic_blocks() -> None:
    aliases = AliasDirectory(
        {"Exec A": "alpha-mailbox-id", "Exec B": "beta-mailbox-id"}
    )
    schedules = [
        ScheduleResponse(
            upn="beta-mailbox-id",
            slots=[
                FreeBusySlot(
                    start=instant("2026-09-15T15:00:00Z"),
                    end=instant("2026-09-15T15:30:00Z"),
                    status="busy",
                )
            ],
        ),
        ScheduleResponse(
            upn="alpha-mailbox-id",
            slots=[
                FreeBusySlot(
                    start=instant("2026-09-15T14:00:00Z"),
                    end=instant("2026-09-15T14:30:00Z"),
                    status="busy",
                )
            ],
        ),
    ]
    events = {
        "alpha-mailbox-id": [
            CalendarEvent(
                event_id="private-event-a",
                subject="Private acquisition discussion",
                body_preview="Confidential counterparty details",
                start=instant("2026-09-15T14:00:00Z"),
                end=instant("2026-09-15T14:30:00Z"),
                show_as="busy",
                is_protected=True,
                organizer="alpha-mailbox-id",
                attendees=["beta-mailbox-id"],
            )
        ],
        "beta-mailbox-id": [
            CalendarEvent(
                event_id="private-event-b",
                subject="Compensation review",
                body_preview="Private compensation numbers",
                start=instant("2026-09-15T15:00:00Z"),
                end=instant("2026-09-15T15:30:00Z"),
                show_as="busy",
                is_movable=False,
                organizer="beta-mailbox-id",
                attendees=["alpha-mailbox-id"],
            )
        ],
    }
    candidates = [
        TimeSlot(
            start=instant("2026-09-15T16:00:00Z"),
            end=instant("2026-09-15T16:30:00Z"),
        )
    ]

    board = build_calendar_board(
        request_id="REQ-LIVE-1",
        source="live_via_scout",
        aliases=aliases,
        schedules=schedules,
        events=events,
        candidate_slots=candidates,
    )

    assert [lane.alias for lane in board.lanes] == ["Exec A", "Exec B"]
    assert [[block.label for block in lane.blocks] for lane in board.lanes] == [
        ["Protected"],
        ["Busy"],
    ]
    assert board.candidate_slots == candidates
    public = board.model_dump_json()
    for private_text in (
        "alpha-mailbox-id",
        "beta-mailbox-id",
        "Private acquisition discussion",
        "Confidential counterparty details",
        "Compensation review",
        "Private compensation numbers",
        "private-event-a",
        "private-event-b",
    ):
        assert private_text not in public


def test_FR_903_access_limited_lane_is_explicit_and_never_fabricated() -> None:
    aliases = AliasDirectory(
        {"Exec A": "alpha-mailbox-id", "Exec B": "beta-mailbox-id"}
    )
    schedules = [
        ScheduleResponse(upn="alpha-mailbox-id", slots=[]),
        ScheduleResponse(upn="beta-mailbox-id", slots=[], access_limited=True),
    ]

    board = build_calendar_board(
        request_id="REQ-LIVE-2",
        source="live_via_scout",
        aliases=aliases,
        schedules=schedules,
        events={"alpha-mailbox-id": [], "beta-mailbox-id": []},
        candidate_slots=[],
    )

    limited = board.lanes[1]
    assert limited.alias == "Exec B"
    assert limited.access_limited is True
    assert limited.limitation == "Delegated calendar detail unavailable"
    assert limited.blocks == []
