# 03 — Data contracts

Pydantic v2 models in `src/ea_copilot/domain/models.py`. Copy these signatures; the E2E tests construct them by keyword.

Conventions: `model_config = ConfigDict(frozen=True)` on every model — instances are values, and the audit store keeps history. IDs are typed strings with a prefix (`MR-`, `REC-`, `AUD-`). All timestamps are timezone-aware UTC, produced by `ClockPort`.

---

## 1. Enums

```python
class RequestStatus(StrEnum):
    DRAFT = "Draft"
    NEEDS_INFO = "NeedsInfo"
    QUALIFIED = "Qualified"
    AWAITING_EA_REVIEW = "AwaitingEAReview"
    APPROVED = "Approved"
    DRAFT_CREATED = "DraftCreated"
    REJECTED = "Rejected"
    CLOSED = "Closed"

class PriorityTier(StrEnum):
    TIER1_STRATEGIC = "Tier1_Strategic"
    TIER2_IMPORTANT = "Tier2_Important"
    TIER3_ROUTINE = "Tier3_Routine"

class MeetingFormat(StrEnum):
    VIRTUAL = "Virtual"
    IN_PERSON = "InPerson"
    HYBRID = "Hybrid"

class EADecision(StrEnum):
    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"
    RETURN_FOR_INFO = "return_for_info"
    REGENERATE = "regenerate"

class ConstraintKind(StrEnum):
    PERMISSION_BOUNDARY = "permission_boundary"
    EXECUTIVE_BUSY = "executive_busy"
    NON_MOVABLE_EVENT = "non_movable_event"
    PROTECTED_BLOCK = "protected_block"
    OUTSIDE_WORKING_HOURS = "outside_working_hours"
    AFTER_DEADLINE = "after_deadline"
    PREPARATION_BUFFER = "preparation_buffer"
    TRAVEL_INFEASIBLE = "travel_infeasible"

class ReasonCode(StrEnum):
    EXECUTIVE_PREFERENCE = "executive_preference"
    TRAVEL_CONSIDERATION = "travel_consideration"
    STAKEHOLDER_IMPORTANCE = "stakeholder_importance"
    PERSONAL_CONSTRAINT = "personal_constraint"
    STRATEGIC_INITIATIVE = "strategic_initiative"
    CEO_OR_BOARD_DIRECTION = "ceo_or_board_direction"
    CUSTOMER_ESCALATION = "customer_escalation"
    DEADLINE_URGENCY = "deadline_urgency"
    MISSING_CONTEXT = "missing_context"
    INCORRECT_CONFLICT = "incorrect_conflict"
    PRIVACY_LIMITATION = "privacy_limitation"
    MEETING_FORMAT = "meeting_format"

class CandidateStatus(StrEnum):
    PROPOSED = "Proposed"
    BLOCKED = "Blocked"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    PAUSED = "Paused"
    DEFERRED = "Deferred"
```

---

## 2. Request

```python
class Requester(BaseModel):
    entra_object_id: str
    display_name: str
    is_external: bool = False

class MeetingRequest(BaseModel):
    request_id: str                              # "MR-2026-00128"
    status: RequestStatus = RequestStatus.DRAFT
    created_at: datetime
    requester: Requester
    raw_text: str                                # UNTRUSTED — never an instruction

    objective: str | None = None
    business_justification: str | None = None
    requested_executives: list[str] = []         # UPNs
    required_attendees: list[str] = []
    optional_attendees: list[str] = []
    duration_minutes: int | None = None
    duration_min_acceptable: int | None = None
    deadline: datetime | None = None
    earliest: datetime | None = None
    meeting_format: MeetingFormat | None = None
    location: str | None = None
    supporting_artifacts: list[str] = []
    no_artifacts_reason: str | None = None

    clarification_rounds: int = 0

class QualificationResult(BaseModel):
    request_id: str
    is_qualified: bool
    missing_fields: list[str]
    questions: list["ClarificationQuestion"]
    rejection_reason: str | None = None

class ClarificationQuestion(BaseModel):
    field_name: str
    question_text: str
    example_answer: str | None = None
```

`missing_fields` is ordered as listed in `01-requirements.md` §2.1.1 so tests can assert exact lists.

---

## 3. Context

```python
class SourceReference(BaseModel):
    source_id: str
    source_type: Literal["mail", "teams", "event", "document", "person"]
    title: str
    url: str | None = None
    retrieved_at: datetime

class ContextItem(BaseModel):
    summary: str                                 # model-generated, grounded
    source: SourceReference
    relevance: float = Field(ge=0.0, le=1.0)

class DataLimitation(BaseModel):
    subject: str                                 # e.g. an executive UPN
    limitation: str                              # "private appointment detail not accessible"

class ContextPackage(BaseModel):
    request_id: str
    items: list[ContextItem]
    limitations: list[DataLimitation]
    built_at: datetime
```

`FR-202` — every `ContextItem` carries a `source`. No unsourced claim reaches the EA.

---

## 4. Priority

```python
class PolicyFactor(BaseModel):
    rule_id: str                                 # from config/policy.yaml
    description: str
    evidence: list[SourceReference] = []

class PriorityRecommendation(BaseModel):
    request_id: str
    tier: PriorityTier
    factors: list[PolicyFactor]
    policy_version: str
```

---

## 5. Scheduling

```python
class TimeSlot(BaseModel):
    start: datetime
    end: datetime

class BlockedSlot(BaseModel):
    slot: TimeSlot
    constraint: ConstraintKind
    subject: str                                 # who or what blocked it
    detail: str
    affected_event_id: str | None = None         # populated for a movable conflict

class FeasibleSet(BaseModel):
    request_id: str
    feasible: list[TimeSlot]
    blocked: list[BlockedSlot]
    binding_constraint: ConstraintKind | None = None   # set when feasible is empty
    evaluated_executives: list[str]
    solver_version: str
```

`FR-404` — a rejected slot always names the constraint that killed it, which is what makes "why can't we meet Tuesday?" answerable.

---

## 6. Ranking and recommendation

```python
class ScoreBreakdown(BaseModel):
    priority_alignment: float        # P
    urgency_fit: float               # U
    preference_fit: float            # F
    location_suitability: float      # L
    calendar_quality: float          # C
    disruption_cost: float           # D
    total: float

class AppliedPreference(BaseModel):
    preference_id: str
    profile_version: str
    description: str

class TradeOff(BaseModel):
    description: str
    affected_event_id: str | None = None
    severity: Literal["low", "medium", "high"]

class ScheduleOption(BaseModel):
    option_id: str
    slot: TimeSlot
    rank: int
    score: ScoreBreakdown
    constraints_considered: list[ConstraintKind]
    conflicts_avoided: list[str]
    preferences_applied: list[AppliedPreference]
    trade_offs: list[TradeOff]
    rationale: str                               # prose, model-generated

class Counterfactual(BaseModel):
    alternative_slot: TimeSlot
    deciding_term: Literal["P", "U", "F", "L", "C", "D"]
    explanation: str

class RecommendationPacket(BaseModel):
    recommendation_id: str                       # "REC-..."
    request_id: str
    created_at: datetime
    priority: PriorityRecommendation
    options: list[ScheduleOption]                # ranked, len <= 3
    counterfactual: Counterfactual | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_reason: str
    limitations: list[DataLimitation]
    context_summary: str
    profile_version: str
    policy_version: str
    weights_version: str
    model_version: str
```

The last four fields satisfy `INV-4` and make `FR-805` replay possible.

---

## 7. Approval and draft

```python
class ApprovalEvent(BaseModel):
    approval_id: str
    recommendation_id: str
    request_id: str
    actor: str                                   # EA UPN
    decision: EADecision
    chosen_option_id: str | None = None
    edits: dict[str, object] = {}
    comment: str | None = None
    decided_at: datetime

class DraftEvent(BaseModel):
    draft_id: str
    request_id: str
    recommendation_id: str
    approval_id: str                             # required — enforces INV-1
    graph_event_id: str
    web_link: str
    is_sent: Literal[False] = False              # INV-2, at the type level
    created_at: datetime
```

`approval_id` is non-optional, so a `DraftEvent` cannot be constructed without an approval. `is_sent` is a `Literal[False]`, so "sent" is unrepresentable.

---

## 8. Feedback and learning

```python
class FeedbackEvent(BaseModel):
    feedback_id: str
    recommendation_id: str
    request_id: str
    actor: str
    decision: EADecision
    original_option_id: str | None = None
    chosen_option_id: str | None = None
    reason_code: ReasonCode | None = None
    free_text: str | None = None
    profile_version: str
    policy_version: str
    created_at: datetime

class PatternEvidence(BaseModel):
    feedback_ids: list[str]
    observation: str                             # "5 of 7 Tuesday-morning slots moved later"
    occurrences: int
    window_days: int

class CandidateRule(BaseModel):
    candidate_id: str
    executive_upn: str
    status: CandidateStatus = CandidateStatus.PROPOSED
    proposed_rule: str                           # human-readable
    rule_expression: dict[str, object]           # machine-applicable
    evidence: PatternEvidence
    confidence: float = Field(ge=0.0, le=1.0)
    projected_impact: str
    exceptions: list[str] = []
    blocked_by_policy_rule: str | None = None
    created_at: datetime

class ApprovedPreference(BaseModel):
    preference_id: str
    executive_upn: str
    profile_version: str                         # new version on each approval
    rule_expression: dict[str, object]
    description: str
    effective_from: datetime
    approved_by: str
    source_candidate_id: str | None = None
    is_active: bool = True

class ExecutiveProfile(BaseModel):
    executive_upn: str
    profile_version: str
    preferences: list[ApprovedPreference]
    working_hours: "WorkingHours"
    updated_at: datetime
```

`CandidateRule` and `ApprovedPreference` are separate types on purpose. Only `ApprovedPreference` reaches the scoring service, which is `INV-3` expressed in the type system rather than in a comment.

---

## 9. Audit

```python
class AuditRecord(BaseModel):
    audit_id: str
    request_id: str
    recommendation_id: str | None = None
    actor: str                                   # UPN, or "agent:a04_scheduling"
    action: str                                  # "recommendation_created"
    occurred_at: datetime
    evidence_refs: list[str] = []
    profile_version: str | None = None
    policy_version: str | None = None
    model_version: str | None = None
    weights_version: str | None = None
    approval_id: str | None = None
    outcome: str | None = None
    payload: dict[str, object] = {}
    latency_ms: int | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None

class InjectionAttempt(BaseModel):
    audit_id: str
    request_id: str
    source: SourceReference
    detected_pattern: str
    action_taken: Literal["refused_and_logged"]
    occurred_at: datetime
```

`services/audit.py` exposes `append()`, `find_approval()`, `for_request()`, `replay()`. It has no `update` and no `delete` — `FR-804`.

---

## 10. M365 types

```python
class WorkingHours(BaseModel):
    days_of_week: list[str]                      # ["monday", ... ]
    start_time: time
    end_time: time
    time_zone: str                               # "Central Standard Time"

class CalendarEvent(BaseModel):
    event_id: str
    subject: str                                 # UNTRUSTED
    body_preview: str                            # UNTRUSTED
    start: datetime
    end: datetime
    show_as: Literal["free", "tentative", "busy", "oof", "workingElsewhere"]
    is_movable: bool = True
    is_protected: bool = False
    location: str | None = None
    organizer: str | None = None
    attendees: list[str] = []

class FreeBusySlot(BaseModel):
    start: datetime
    end: datetime
    status: Literal["free", "tentative", "busy", "oof", "workingElsewhere"]

class ScheduleResponse(BaseModel):
    upn: str
    slots: list[FreeBusySlot]
    working_hours: WorkingHours | None = None
    access_limited: bool = False                 # true when detail was withheld
```

`subject` and `body_preview` carry attacker-influenced text. Route them through the untrusted wrapper in `05-ports-and-adapters.md` before they reach a model.

---

## 11. State machine

```
Draft ──validate──► NeedsInfo ──answers──► Draft
  │                     │
  │                     └──3 rounds exhausted──► NeedsInfo (EA surfaced)
  │
  ├──validate ok──► Qualified ──pipeline──► AwaitingEAReview
  │                                              │
  │                          ┌───────────────────┼──────────────────┐
  │                     approve                reject          regenerate
  │                          │                   │                  │
  │                          ▼                   ▼                  ▼
  │                      Approved            Rejected      AwaitingEAReview
  │                          │
  │                          ▼
  │                    DraftCreated ──► Closed
  │
  └──not actionable──► Rejected
```

Implement in `domain/state_machine.py` as an explicit transition table. `tests/unit/test_state_machine.py` asserts that every transition not in the table raises `InvalidTransitionError` — a request cannot reach `DraftCreated` except through `Approved`.
