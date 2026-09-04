# 04 — Component specifications

One section per agent. Each gives the module path, constructor dependencies, the method signature, and the requirement IDs to name in the docstring.

Every agent takes its dependencies through `__init__` and reaches nothing global.

---

## Agent 1 — Intake and qualification

**Module** `agents/a01_intake.py` · **Implements** FR-101…FR-107

```python
class IntakeAgent:
    def __init__(self, llm: LlmPort, clock: ClockPort, audit: AuditStore) -> None: ...

    def qualify(self, request: MeetingRequest) -> QualificationResult: ...
    def merge_answers(self, request: MeetingRequest, answers: dict[str, str]) -> MeetingRequest: ...
```

Field extraction from `raw_text` uses `LlmPort.extract()` with the `MeetingRequest` schema. Field *validation* is deterministic in `services/validation.py` — the model proposes values, the validator decides completeness.

Not actionable when: no executive named, or the deadline is in the past per `ClockPort`. Both give `RequestStatus.REJECTED` with a stated reason.

Question phrasing comes from `LlmPort.generate()`; the fake returns a fixed template per field so tests assert exact text.

---

## Agent 2 — Context intelligence

**Module** `agents/a02_context.py` · **Implements** FR-201…FR-205

```python
class ContextAgent:
    def __init__(self, m365: M365Port, llm: LlmPort, clock: ClockPort, audit: AuditStore) -> None: ...

    def build(self, request: MeetingRequest) -> ContextPackage: ...
```

Retrieval order: prior events with the same executives → mail matching the objective → Teams messages → linked documents. Stop at 20 items or 8000 characters of quoted text.

Every retrieved string is wrapped as untrusted before summarisation. A `PermissionDeniedError` from the port becomes a `DataLimitation`, never a failed request — the EA should see "one executive's detail was not visible", not a stack trace.

This agent has no write capability. It is the component most exposed to hostile text, so it holds the least authority.

---

## Agent 3 — Priority intelligence

**Module** `agents/a03_priority.py` · **Implements** FR-301…FR-304

```python
class PriorityAgent:
    def __init__(self, policy: PolicyService, audit: AuditStore) -> None: ...

    def recommend(self, request: MeetingRequest, context: ContextPackage) -> PriorityRecommendation: ...
```

No `LlmPort`. The tier comes from rules in `config/policy.yaml` evaluated by `services/policy.py`, so it is reproducible and a reviewer can point at the rule that fired. Every returned `PolicyFactor` carries the `rule_id` that produced it.

---

## Agent 4 — Scheduling orchestration

**Module** `agents/a04_scheduling.py` · **Implements** FR-401…FR-407, INV-5

```python
class SchedulingAgent:
    def __init__(self, m365: M365Port, solver: ConstraintSolver, clock: ClockPort, audit: AuditStore) -> None: ...

    def solve(self, request: MeetingRequest) -> FeasibleSet: ...
```

Fetch `get_schedule()` and `get_working_hours()` for every required executive, build the constraint model, and enumerate feasible slots on a 15-minute grid.

The solver takes **no** `ExecutiveProfile` and no preference data. Its signature is the enforcement point for `INV-5`:

```python
def solve(self, window: TimeSlot, duration: timedelta,
          schedules: list[ScheduleResponse],
          hard_constraints: list[HardConstraint]) -> FeasibleSet: ...
```

Record every rejected slot with its blocking `ConstraintKind`. When nothing is feasible, return an empty list with `binding_constraint` set — never relax a constraint to produce an answer.

CP-SAT lives in `services/solver.py`. Keep it pure: schedules and constraints in, slots out.

---

## Agent 5 — Option ranking

**Module** `agents/a05_ranking.py` · **Implements** FR-501…FR-504

```python
class RankingAgent:
    def __init__(self, scoring: ScoringService, profile_store: ProfileStore, audit: AuditStore) -> None: ...

    def rank(self, feasible: FeasibleSet, request: MeetingRequest,
             priority: PriorityRecommendation, context: ContextPackage) -> list[ScheduleOption]: ...
```

This is where preference enters, and only through `ProfileStore.get_active(executive_upn)` which returns `ApprovedPreference` values. A `CandidateRule` is not readable from here — `INV-3` holds because the store offers no method to fetch one.

Scoring is arithmetic in `services/scoring.py`, weights from `config/weights.yaml`. Return the full `ScoreBreakdown` so a rank is explainable term by term. Ties break by earlier start time, so ordering is stable.

---

## Agent 6 — Explanation

**Module** `agents/a06_explanation.py` · **Implements** FR-505…FR-508

```python
class ExplanationAgent:
    def __init__(self, llm: LlmPort, clock: ClockPort, audit: AuditStore) -> None: ...

    def compose(self, options: list[ScheduleOption], feasible: FeasibleSet,
                priority: PriorityRecommendation, context: ContextPackage) -> RecommendationPacket: ...
```

Prose only. Every number in the output comes from the `ScoreBreakdown` and `BlockedSlot` data it is given — the model narrates, it does not compute.

Confidence is deterministic, from `services/scoring.py`: the score margin between rank 1 and rank 2, damped by the count of `DataLimitation` entries. The model supplies the *reason* string, not the value.

The counterfactual names the next-best slot and the single term with the largest delta.

---

## Agent 7 — EA review workbench

**Module** `agents/a07_workbench.py` · **Implements** FR-601…FR-603, INV-1

```python
class WorkbenchAgent:
    def __init__(self, audit: AuditStore, clock: ClockPort) -> None: ...

    def present(self, recommendation_id: str) -> RecommendationPacket: ...
    def decide(self, recommendation_id: str, actor: str, decision: EADecision,
               chosen_option_id: str | None = None,
               edits: dict[str, object] | None = None,
               comment: str | None = None) -> ApprovalEvent: ...
```

`decide()` writes the `ApprovalEvent` and returns it. It performs no calendar action — that belongs to agent 8, and the split is what makes the gate a boundary rather than a formality.

An `approve` decision requires a `chosen_option_id` that exists in the packet; otherwise raise `ValidationError`.

---

## Agent 8 — Draft action

**Module** `agents/a08_draft_action.py` · **Implements** FR-604…FR-608, INV-1, INV-2

```python
class DraftActionAgent:
    def __init__(self, m365: M365Port, audit: AuditStore, clock: ClockPort, settings: Settings) -> None: ...

    def create_draft(self, recommendation_id: str, actor: str) -> DraftEvent: ...
```

Order of operations, and it matters:

1. `audit.find_approval(recommendation_id)` → `None` raises `ApprovalRequiredError`.
2. `settings.calendar_writes_enabled` is false → raise `CalendarWritesDisabledError` (FR-608).
3. `m365.create_draft_event(...)` → returns an unsent draft.
4. `audit.append(...)` with `approval_id` populated.

The only write this system performs. It calls exactly one port method.

---

## Agent 9 — Feedback capture

**Module** `agents/a09_feedback.py` · **Implements** FR-701, FR-702

```python
class FeedbackAgent:
    def __init__(self, evidence: EvidenceStore, llm: LlmPort, clock: ClockPort, audit: AuditStore) -> None: ...

    def capture(self, approval: ApprovalEvent, packet: RecommendationPacket,
                reason_code: ReasonCode | None, free_text: str | None) -> FeedbackEvent: ...
```

Writes to the evidence store and the audit store. Nothing reads the evidence store during a request.

When `reason_code` is absent and `free_text` is present, `LlmPort.classify()` suggests one — recorded as `suggested_reason_code`, kept distinct from an EA-supplied value.

---

## Agent 10 — Pattern and candidate rule engine

**Module** `agents/a10_pattern.py` · **Implements** FR-703, FR-704, FR-711

```python
class PatternAgent:
    def __init__(self, evidence: EvidenceStore, policy: PolicyService,
                 clock: ClockPort, settings: Settings, audit: AuditStore) -> None: ...

    def detect(self, executive_upn: str) -> list[CandidateRule]: ...
```

Detection is pure and lives in `services/patterns.py`: group feedback by `(executive, reason_code, correction_dimension)`, count occurrences inside `settings.pattern_window_days` (30), emit a candidate at `settings.pattern_threshold` (3) or more.

Correction dimensions: time-of-day shift · day-of-week avoidance · duration change · format change · priority change.

Validate each candidate against enterprise policy. On conflict, set `Blocked` and populate `blocked_by_policy_rule` — surface the disagreement rather than silently discarding it.

Candidates are scoped to one executive (`FR-711`).

---

## Agent 11 — Preference review and approval

**Module** `agents/a11_preference_review.py` · **Implements** FR-705…FR-709, INV-3

```python
class PreferenceReviewAgent:
    def __init__(self, profile_store: ProfileStore, audit: AuditStore, clock: ClockPort) -> None: ...

    def list_candidates(self, executive_upn: str | None = None) -> list[CandidateRule]: ...
    def decide(self, candidate_id: str, actor: str, decision: str,
               edits: dict[str, object] | None = None) -> ApprovedPreference | None: ...
    def rollback(self, executive_upn: str, to_version: str, actor: str) -> ExecutiveProfile: ...
```

`decide("approve")` is the only path that writes an `ApprovedPreference`, and it increments `profile_version`. Every other decision leaves the profile untouched.

`rollback()` writes a new version whose content matches an earlier one — history is never rewritten.

---

## Agent 12 — Evaluation and monitoring

**Module** `agents/a12_evaluation.py` · **Implements** FR-710

```python
class EvaluationAgent:
    def __init__(self, audit: AuditStore, evidence: EvidenceStore, clock: ClockPort) -> None: ...

    def summary(self, since: datetime | None = None) -> EvaluationSummary: ...
```

Reads only. Computes acceptance rate, override rate, mean latency, token cost, and the count of recommendations lacking a version field (which should always be zero — it is a live check on `INV-4`).

---

## Orchestrator

**Module** `orchestrator.py`

```python
class RequestOrchestrator:
    def __init__(self, intake, context, priority, scheduling, ranking,
                 explanation, workbench, draft_action, feedback, audit, clock) -> None: ...

    def submit(self, raw_text: str, requester: Requester) -> MeetingRequest: ...
    def answer(self, request_id: str, answers: dict[str, str]) -> MeetingRequest: ...
    def build_recommendation(self, request_id: str) -> RecommendationPacket: ...
    def decide(self, recommendation_id: str, actor: str, decision: EADecision, **kw) -> ApprovalEvent: ...
    def create_draft(self, recommendation_id: str, actor: str) -> DraftEvent: ...
```

`build_recommendation` runs agents 2→6 and stops at `AwaitingEAReview`. It never continues into agent 8: the pause is the product, and only a separate `decide()` call from a human resumes the flow.
