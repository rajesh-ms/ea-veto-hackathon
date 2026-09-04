"""Executable Scout tool-sequence guard for FR-906 and FR-907."""

from __future__ import annotations

from ea_copilot.domain.errors import ScoutSequenceError
from ea_copilot.domain.live_models import ScoutToolCall, ScoutTranscriptResult

_REQUIRED = [
    "ea_submit_request",
    "ea_attach_snapshot",
    "ea_get_recommendation",
    "ea_record_decision",
    "ea_prepare_draft",
    "workiq_create_event",
    "ea_complete_draft",
]
_CALENDAR_MUTATIONS = ("update", "delete", "send", "cancel", "move", "accept", "decline")


def _forbidden_calendar_tool(name: str) -> bool:
    normalized = name.casefold()
    calendar_surface = "event" in normalized or "calendar" in normalized
    return calendar_surface and any(action in normalized for action in _CALENDAR_MUTATIONS)


def validate_scout_transcript(calls: list[ScoutToolCall]) -> ScoutTranscriptResult:
    """Validate approval order and the literal draft-only Work IQ call."""

    forbidden = [call.name for call in calls if _forbidden_calendar_tool(call.name)]
    if forbidden:
        raise ScoutSequenceError(
            f"Scout transcript contains forbidden calendar tool: {forbidden[0]}"
        )

    positions: list[int] = []
    cursor = 0
    for required in _REQUIRED:
        position = next(
            (index for index in range(cursor, len(calls)) if calls[index].name == required),
            None,
        )
        if position is None:
            raise ScoutSequenceError(f"Scout tool sequence is missing or out of order: {required}")
        positions.append(position)
        cursor = position + 1

    decision = calls[positions[3]].arguments.get("decision")
    if decision not in {"approve", "edit"}:
        raise ScoutSequenceError("Scout draft requires an approve or edit EA decision")

    create = calls[positions[5]].arguments
    if create.get("draft") is not True:
        raise ScoutSequenceError("workiq_create_event must use literal draft=true")
    if create.get("subject") != "[DEMO] Executive scheduling prototype":
        raise ScoutSequenceError("workiq_create_event must use the fixed [DEMO] subject")
    attendees = create.get("attendees")
    if not isinstance(attendees, list) or len(attendees) != 1:
        raise ScoutSequenceError("workiq_create_event must have exactly one self attendee")

    completed = calls[positions[6]].arguments
    if completed.get("draft") is not True:
        raise ScoutSequenceError("ea_complete_draft must attest draft=true")

    return ScoutTranscriptResult(attendee_count=1, forbidden_tools=[])
