"""Immutable data contracts for FR-101..FR-805 and INV-1..INV-6."""

from __future__ import annotations

from datetime import datetime, time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ea_copilot.domain.enums import (
    CandidateStatus,
    ConstraintKind,
    EADecision,
    MeetingFormat,
    PriorityTier,
    ReasonCode,
    RequestStatus,
)


class DomainModel(BaseModel):
    """Frozen base for append-only value semantics."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class Requester(DomainModel):
    entra_object_id: str
    display_name: str
    is_external: bool = False


class MeetingRequest(DomainModel):
    request_id: str
    status: RequestStatus = RequestStatus.DRAFT
    created_at: datetime
    requester: Requester
    raw_text: str
    objective: str | None = None
    business_justification: str | None = None
    requested_executives: list[str] = Field(default_factory=list)
    required_attendees: list[str] = Field(default_factory=list)
    optional_attendees: list[str] = Field(default_factory=list)
    duration_minutes: int | None = None
    duration_min_acceptable: int | None = None
    deadline: datetime | None = None
    earliest: datetime | None = None
    meeting_format: MeetingFormat | None = None
    location: str | None = None
    supporting_artifacts: list[str] = Field(default_factory=list)
    no_artifacts_reason: str | None = None
    clarification_rounds: int = 0


class ClarificationQuestion(DomainModel):
    field_name: str
    question_text: str
    example_answer: str | None = None


class QualificationResult(DomainModel):
    request_id: str
    is_qualified: bool
    missing_fields: list[str]
    questions: list[ClarificationQuestion]
    rejection_reason: str | None = None


class SourceReference(DomainModel):
    source_id: str
    source_type: Literal["mail", "teams", "event", "document", "person"]
    title: str
    url: str | None = None
    retrieved_at: datetime


class ContextItem(DomainModel):
    summary: str
    source: SourceReference
    relevance: float = Field(ge=0.0, le=1.0)


class DataLimitation(DomainModel):
    subject: str
    limitation: str


class ContextPackage(DomainModel):
    request_id: str
    items: list[ContextItem]
    limitations: list[DataLimitation]
    built_at: datetime


class PolicyFactor(DomainModel):
    rule_id: str
    description: str
    evidence: list[SourceReference] = Field(default_factory=list)


class PriorityRecommendation(DomainModel):
    request_id: str
    tier: PriorityTier
    factors: list[PolicyFactor]
    policy_version: str


class TimeSlot(DomainModel):
    start: datetime
    end: datetime


class HardConstraint(DomainModel):
    kind: ConstraintKind
    slot: TimeSlot
    subject: str
    detail: str
    affected_event_id: str | None = None


class BlockedSlot(DomainModel):
    slot: TimeSlot
    constraint: ConstraintKind
    subject: str
    detail: str
    affected_event_id: str | None = None


class FeasibleSet(DomainModel):
    request_id: str
    feasible: list[TimeSlot]
    blocked: list[BlockedSlot]
    binding_constraint: ConstraintKind | None = None
    evaluated_executives: list[str]
    solver_version: str


class ScoreBreakdown(DomainModel):
    priority_alignment: float
    urgency_fit: float
    preference_fit: float
    location_suitability: float
    calendar_quality: float
    disruption_cost: float
    total: float


class AppliedPreference(DomainModel):
    preference_id: str
    profile_version: str
    description: str


class TradeOff(DomainModel):
    description: str
    affected_event_id: str | None = None
    severity: Literal["low", "medium", "high"]


class ScheduleOption(DomainModel):
    option_id: str
    slot: TimeSlot
    rank: int
    score: ScoreBreakdown
    constraints_considered: list[ConstraintKind]
    conflicts_avoided: list[str]
    preferences_applied: list[AppliedPreference]
    trade_offs: list[TradeOff]
    rationale: str


class Counterfactual(DomainModel):
    alternative_slot: TimeSlot
    deciding_term: Literal["P", "U", "F", "L", "C", "D"]
    explanation: str


class RecommendationPacket(DomainModel):
    recommendation_id: str
    request_id: str
    created_at: datetime
    priority: PriorityRecommendation
    options: list[ScheduleOption]
    counterfactual: Counterfactual | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_reason: str
    limitations: list[DataLimitation]
    context_summary: str
    profile_version: str
    policy_version: str
    weights_version: str
    model_version: str


class ApprovalEvent(DomainModel):
    approval_id: str
    recommendation_id: str
    request_id: str
    actor: str
    decision: EADecision
    chosen_option_id: str | None = None
    edits: dict[str, object] = Field(default_factory=dict)
    comment: str | None = None
    decided_at: datetime


class DraftEvent(DomainModel):
    draft_id: str
    request_id: str
    recommendation_id: str
    approval_id: str
    graph_event_id: str
    web_link: str
    is_sent: Literal[False] = False
    created_at: datetime


class FeedbackEvent(DomainModel):
    feedback_id: str
    recommendation_id: str
    request_id: str
    actor: str
    decision: EADecision
    original_option_id: str | None = None
    chosen_option_id: str | None = None
    reason_code: ReasonCode | None = None
    suggested_reason_code: ReasonCode | None = None
    free_text: str | None = None
    executive_upn: str | None = None
    correction_dimension: str | None = None
    correction_value: str | None = None
    profile_version: str
    policy_version: str
    created_at: datetime


class PatternEvidence(DomainModel):
    feedback_ids: list[str]
    graph_evidence_ids: list[str] = Field(default_factory=list)
    observation: str
    occurrences: int
    window_days: int


class CandidateRule(DomainModel):
    candidate_id: str
    executive_upn: str
    status: CandidateStatus = CandidateStatus.PROPOSED
    proposed_rule: str
    rule_expression: dict[str, object]
    evidence: PatternEvidence
    confidence: float = Field(ge=0.0, le=1.0)
    projected_impact: str
    exceptions: list[str] = Field(default_factory=list)
    blocked_by_policy_rule: str | None = None
    created_at: datetime


class ApprovedPreference(DomainModel):
    preference_id: str
    executive_upn: str
    profile_version: str
    rule_expression: dict[str, object]
    description: str
    effective_from: datetime
    approved_by: str
    source_candidate_id: str | None = None
    is_active: bool = True


class WorkingHours(DomainModel):
    days_of_week: list[str]
    start_time: time
    end_time: time
    time_zone: str


class ExecutiveProfile(DomainModel):
    executive_upn: str
    profile_version: str
    preferences: list[ApprovedPreference]
    working_hours: WorkingHours
    updated_at: datetime


class AuditRecord(DomainModel):
    audit_id: str
    request_id: str
    recommendation_id: str | None = None
    actor: str
    action: str
    occurred_at: datetime
    evidence_refs: list[str] = Field(default_factory=list)
    profile_version: str | None = None
    policy_version: str | None = None
    model_version: str | None = None
    weights_version: str | None = None
    approval_id: str | None = None
    outcome: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    latency_ms: int | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None


class InjectionAttempt(DomainModel):
    audit_id: str
    request_id: str
    source: SourceReference
    detected_pattern: str
    action_taken: Literal["refused_and_logged"]
    occurred_at: datetime


class CalendarEvent(DomainModel):
    event_id: str
    subject: str
    body_preview: str
    start: datetime
    end: datetime
    show_as: Literal["free", "tentative", "busy", "oof", "workingElsewhere"]
    is_movable: bool = True
    is_protected: bool = False
    location: str | None = None
    organizer: str | None = None
    attendees: list[str] = Field(default_factory=list)


class FreeBusySlot(DomainModel):
    start: datetime
    end: datetime
    status: Literal["free", "tentative", "busy", "oof", "workingElsewhere"]


class ScheduleResponse(DomainModel):
    upn: str
    slots: list[FreeBusySlot]
    working_hours: WorkingHours | None = None
    access_limited: bool = False


class MailMessage(DomainModel):
    message_id: str
    subject: str
    body_preview: str
    web_url: str
    received_at: datetime


class ChatMessage(DomainModel):
    message_id: str
    topic: str
    body: str
    web_url: str
    created_at: datetime


class FileReference(DomainModel):
    file_id: str
    name: str
    excerpt: str
    web_url: str
    modified_at: datetime


class LlmResult(DomainModel):
    content: str
    parsed: BaseModel | None = None
    model_version: str
    tokens_in: int
    tokens_out: int
    refused: bool = False
    refusal_reason: str | None = None


class EvaluationSummary(DomainModel):
    acceptance_rate: float
    override_rate: float
    mean_latency_ms: float
    token_cost: int
    incomplete_version_records: int


class RecommendationView(DomainModel):
    packet: RecommendationPacket
    context: ContextPackage
    feasible_set: FeasibleSet
