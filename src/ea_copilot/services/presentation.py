"""Privacy-filtered calendar and memory projections for FR-902..FR-905."""

from __future__ import annotations

import json

from ea_copilot.domain.live_models import (
    CalendarBlock,
    CalendarBoard,
    CalendarLane,
    CalendarSource,
    GraphPreferenceEvidence,
    MemoryNote,
    MemoryProjection,
)
from ea_copilot.domain.models import (
    AuditRecord,
    CalendarEvent,
    CandidateRule,
    ExecutiveProfile,
    MeetingRequest,
    RecommendationPacket,
    ScheduleResponse,
    TimeSlot,
)
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


def _note(
    *, layer: str, relative_path: str, title: str, lines: list[str], append_only: bool
) -> MemoryNote:
    return MemoryNote(
        layer=layer,  # type: ignore[arg-type]
        relative_path=relative_path,
        title=title,
        markdown="\n".join(lines).rstrip() + "\n",
        append_only=append_only,
    )


def build_memory_projection(
    *,
    request: MeetingRequest,
    recommendation: RecommendationPacket,
    audit_records: list[AuditRecord],
    graph_evidence: list[GraphPreferenceEvidence],
    candidates: list[CandidateRule],
    profiles: dict[str, list[ExecutiveProfile]],
    aliases: AliasDirectory,
) -> MemoryProjection:
    """Build three privacy-filtered memory layers without reading from a vault."""

    notes: list[MemoryNote] = []
    notes.append(
        _note(
            layer="Current Session",
            relative_path=f"01 Current Session/{request.request_id}.md",
            title=f"Current Session {request.request_id}",
            append_only=False,
            lines=[
                f"# Current Session — {request.request_id}",
                "",
                "- Executives: Exec A, Exec B",
                f"- Status: {request.status.value}",
                f"- Recommendation: {recommendation.recommendation_id}",
                f"- Profile version: {recommendation.profile_version}",
                f"- Policy version: {recommendation.policy_version}",
                "",
                "## Candidate slots",
                *[
                    f"- Rank {option.rank}: {option.slot.start.isoformat()} — "
                    f"{option.slot.end.isoformat()}"
                    for option in recommendation.options
                ],
            ],
        )
    )

    for record in audit_records:
        notes.append(
            _note(
                layer="Evidence History",
                relative_path=(
                    f"02 Evidence History/{record.occurred_at.date().isoformat()}/"
                    f"{record.audit_id}.md"
                ),
                title=f"Evidence {record.audit_id}",
                append_only=True,
                lines=[
                    f"# Evidence — {record.audit_id}",
                    "",
                    f"- Action: {record.action}",
                    f"- Outcome: {record.outcome or 'recorded'}",
                    f"- Profile version: {record.profile_version or 'not applicable'}",
                    f"- Policy version: {record.policy_version or 'not applicable'}",
                ],
            )
        )

    for evidence in graph_evidence:
        alias = aliases.alias_for(evidence.executive_upn)
        notes.append(
            _note(
                layer="Evidence History",
                relative_path=(
                    f"02 Evidence History/{evidence.observed_at.date().isoformat()}/"
                    f"{evidence.evidence_id}.md"
                ),
                title=f"Graph evidence {evidence.evidence_id}",
                append_only=True,
                lines=[
                    f"# Graph evidence — {evidence.evidence_id}",
                    "",
                    f"- Executive: {alias}",
                    f"- Dimension: {evidence.dimension}",
                    f"- Value: {evidence.value}",
                    f"- Confidence: {evidence.confidence:.2f}",
                    "- Status: evidence only; not active memory",
                ],
            )
        )

    for candidate in candidates:
        alias = aliases.alias_for(candidate.executive_upn)
        evidence_ids = [
            *candidate.evidence.feedback_ids,
            *candidate.evidence.graph_evidence_ids,
        ]
        notes.append(
            _note(
                layer="Evidence History",
                relative_path=(
                    f"02 Evidence History/{candidate.created_at.date().isoformat()}/"
                    f"{candidate.candidate_id}.md"
                ),
                title=f"Candidate {candidate.candidate_id}",
                append_only=True,
                lines=[
                    f"# Candidate — {candidate.candidate_id}",
                    "",
                    f"- Executive: {alias}",
                    f"- Status: {candidate.status.value}",
                    f"- Proposal: {candidate.proposed_rule}",
                    f"- Evidence: {', '.join(evidence_ids)}",
                    "- Activation: requires EA approval",
                ],
            )
        )

    for identifier, versions in sorted(
        profiles.items(), key=lambda item: aliases.alias_for(item[0])
    ):
        alias = aliases.alias_for(identifier)
        for profile in versions:
            preference_lines = [
                f"- {preference.description} — "
                f"`{json.dumps(preference.rule_expression, sort_keys=True)}`"
                for preference in profile.preferences
            ] or ["- No approved preferences"]
            notes.append(
                _note(
                    layer="Governed Memory",
                    relative_path=(
                        f"03 Governed Memory/{alias}/profile-{profile.profile_version}.md"
                    ),
                    title=f"{alias} profile {profile.profile_version}",
                    append_only=True,
                    lines=[
                        f"# {alias} profile {profile.profile_version}",
                        "",
                        f"- Version: {profile.profile_version}",
                        "- Activation: EA-approved only",
                        "",
                        "## Approved preferences",
                        *preference_lines,
                    ],
                )
            )

    safe_notes = [
        note.model_copy(update={"markdown": aliases.redact(note.markdown)}) for note in notes
    ]
    return MemoryProjection(request_id=request.request_id, notes=safe_notes)
