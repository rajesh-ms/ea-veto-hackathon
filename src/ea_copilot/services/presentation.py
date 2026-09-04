"""Privacy-filtered calendar and memory projections for FR-902..FR-905."""

from __future__ import annotations

from ea_copilot.domain.live_models import (
    CalendarBlock,
    CalendarBoard,
    CalendarLane,
    CalendarSource,
)
from ea_copilot.domain.models import CalendarEvent, ScheduleResponse, TimeSlot
from ea_copilot.services.aliases import AliasDirectory
from ea_copilot.services.ids import stable_id


def _category(event: CalendarEvent) -> tuple[str, str]:
    description = f"{event.subject} {event.location or ''}".casefold()
    if event.is_protected:
        return "protected", "Protected"
    if "travel" in description:
        return "travel", "Travel"
    if "prep" in description or "preparation" in description:
        return "preparation", "Preparation"
    return "busy", "Busy"


def _block(alias: str, event: CalendarEvent) -> CalendarBlock:
    category, label = _category(event)
    return CalendarBlock(
        block_id=stable_id(
            "BLOCK", alias, event.start.isoformat(), event.end.isoformat(), category
        ),
        start=event.start,
        end=event.end,
        category=category,  # type: ignore[arg-type]
        label=label,
    )


def _schedule_block(alias: str, slot: TimeSlot, status: str) -> CalendarBlock:
    return CalendarBlock(
        block_id=stable_id("BLOCK", alias, slot.start.isoformat(), slot.end.isoformat(), status),
        start=slot.start,
        end=slot.end,
        category="busy",
        label="Busy",
    )


def build_calendar_board(
    *,
    request_id: str,
    source: CalendarSource,
    aliases: AliasDirectory,
    schedules: list[ScheduleResponse],
    events: dict[str, list[CalendarEvent]],
    candidate_slots: list[TimeSlot],
) -> CalendarBoard:
    """Return exactly two aliased lanes with generic calendar categories."""

    by_identifier = {schedule.upn.casefold(): schedule for schedule in schedules}
    lanes: list[CalendarLane] = []
    for alias in aliases.aliases:
        identifier = aliases.resolve(alias)
        schedule = by_identifier.get(identifier.casefold())
        if schedule is None:
            lanes.append(
                CalendarLane(
                    alias=alias,
                    access_limited=True,
                    limitation="Calendar snapshot unavailable",
                )
            )
            continue
        if schedule.access_limited:
            lanes.append(
                CalendarLane(
                    alias=alias,
                    access_limited=True,
                    limitation="Delegated calendar detail unavailable",
                )
            )
            continue

        calendar_events = events.get(identifier, [])
        blocks = [_block(alias, event) for event in calendar_events]
        represented = {(event.start, event.end) for event in calendar_events}
        for free_busy in schedule.slots:
            if free_busy.status == "free" or (free_busy.start, free_busy.end) in represented:
                continue
            blocks.append(
                _schedule_block(
                    alias,
                    TimeSlot(start=free_busy.start, end=free_busy.end),
                    free_busy.status,
                )
            )
        lanes.append(CalendarLane(alias=alias, blocks=blocks))

    return CalendarBoard(
        request_id=request_id,
        source=source,
        lanes=lanes,
        candidate_slots=candidate_slots,
    )
