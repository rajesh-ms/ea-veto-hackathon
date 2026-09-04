"""Live Scout and presentation contracts for FR-901..FR-909."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from ea_copilot.domain.models import (
    CalendarEvent,
    ChatMessage,
    DataLimitation,
    DomainModel,
    DraftEvent,
    FileReference,
    MailMessage,
    ScheduleResponse,
    SourceReference,
    TimeSlot,
)

ExecutiveAlias = Literal["Exec A", "Exec B"]
CalendarSource = Literal["fixture", "live_via_scout"]


class CalendarBlock(DomainModel):
    """One privacy-filtered block shown on an executive lane."""

    block_id: str
    start: datetime
    end: datetime
    category: Literal["busy", "protected", "travel", "preparation", "candidate"]
    label: str


class CalendarLane(DomainModel):
    """Presentation-only calendar lane keyed by alias."""

    alias: ExecutiveAlias
    blocks: list[CalendarBlock] = Field(default_factory=list)
    access_limited: bool = False
    limitation: str | None = None


class CalendarBoard(DomainModel):
    """Two-lane calendar projection with no private calendar text."""

    request_id: str
    source: CalendarSource
    lanes: list[CalendarLane]
    candidate_slots: list[TimeSlot] = Field(default_factory=list)


class GraphPreferenceEvidence(DomainModel):
    """One Graph-derived observation that remains outside request-time reads."""

    evidence_id: str
    executive_upn: str
    dimension: Literal["weekday", "time_of_day", "meeting_gap", "preparation"]
    value: str
    source: SourceReference
    confidence: float = Field(ge=0.0, le=1.0)
    observed_at: datetime


class ScoutCalendarSnapshot(DomainModel):
    """Bounded Microsoft 365 read result supplied by authenticated Scout."""

    request_id: str
    captured_at: datetime
    schedules: list[ScheduleResponse]
    events: dict[str, list[CalendarEvent]]
    mail: list[MailMessage] = Field(default_factory=list)
    teams: list[ChatMessage] = Field(default_factory=list)
    files: list[FileReference] = Field(default_factory=list)
    limitations: list[DataLimitation] = Field(default_factory=list)
    preference_evidence: list[GraphPreferenceEvidence] = Field(default_factory=list)


MemoryLayerName = Literal["Current Session", "Evidence History", "Governed Memory"]


class MemoryNote(DomainModel):
    """One privacy-filtered Markdown note destined for a governed layer."""

    layer: MemoryLayerName
    relative_path: str
    title: str
    markdown: str
    append_only: bool


class MemoryProjection(DomainModel):
    """Complete one-way vault projection for a request."""

    request_id: str
    notes: list[MemoryNote]


class VaultProjectionResult(DomainModel):
    """Files and layer names written by the vault adapter."""

    vault_path: Path
    layers: list[MemoryLayerName]
    written_files: list[str]


class DraftAuthorization(DomainModel):
    """Approval identifiers Agent 8 passes to the sole M365 write method."""

    request_id: str
    recommendation_id: str
    approval_id: str


class DraftCommand(DomainModel):
    """Single-use request for Scout to create an unsent Graph draft."""

    command_id: str
    transaction_id: str
    request_id: str
    recommendation_id: str
    approval_id: str
    subject: Literal["[DEMO] Executive scheduling prototype"]
    body: str
    slot: TimeSlot
    attendee: str
    location: str | None = None
    draft: Literal[True] = True
    created_at: datetime


class DraftCompletion(DomainModel):
    """Scout's matching result for one draft command."""

    command_id: str
    transaction_id: str
    graph_event_id: str
    web_link: str
    draft: Literal[True]
    completed_at: datetime


DraftSubmission = DraftEvent | DraftCommand


class ScoutToolCall(DomainModel):
    """Sanitized tool name and arguments used for sequence verification."""

    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ScoutTranscriptResult(DomainModel):
    """Verified safety facts extracted from one Scout scheduling transcript."""

    valid: Literal[True] = True
    draft: Literal[True] = True
    attendee_count: int = 1
    forbidden_tools: list[str] = Field(default_factory=list)
