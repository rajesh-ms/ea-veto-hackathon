# 01 — Requirements

Every requirement has a stable ID. Implement it, name it in the module docstring, and name it in the test that proves it.

Priority: **M** must-have for the MVP demo · **S** should-have · **C** could-have if time allows.

---

## 1. Invariants

Six properties that hold on every code path. Each has a dedicated test in `tests/e2e/test_governance_invariants.py`. A change that fails one of these is wrong, regardless of what else it improves.

| ID | Invariant | How it is proven |
|---|---|---|
| **INV-1** | No calendar write occurs without a preceding `ApprovalEvent` for that recommendation in the audit store. | Drive the pipeline to a recommendation, call the draft endpoint without approving, assert `ApprovalRequiredError` and that `FakeM365Adapter.write_log` is empty. |
| **INV-2** | `create_draft_event` is the only write operation on `M365Port`. The protocol exposes no accept, decline, cancel, move, or send. | Reflect over `M365Port.__protocol_attrs__`; assert the write surface is exactly `{"create_draft_event"}`. |
| **INV-3** | A `CandidateRule` influences no recommendation until an `ApprovedPreference` exists for it. | Generate a candidate, re-run the same request, assert the ranking is byte-identical. Approve it, re-run, assert the ranking changed. |
| **INV-4** | Every `Recommendation` has an audit record carrying `profile_version`, `policy_version`, `model_version`, and `weights_version`. | Property test over generated requests: for each recommendation, all four fields are non-null. |
| **INV-5** | The solver is preference-blind. `FeasibleSet` depends only on hard constraints. | Run the solver twice with preference profiles that differ on every soft field; assert identical `FeasibleSet`. |
| **INV-6** | Text retrieved from mail, Teams, documents, or invitation bodies never becomes an instruction. | Inject the fixture corpus in `tests/fixtures/injection/`; assert no tool call outside the allow-list and an `InjectionAttempt` audit record per payload. |

---

## 2. Functional requirements

### 2.1 Intake and qualification — agent 1

| ID | Pri | Requirement |
|---|---|---|
| FR-101 | M | Accept a meeting request through `POST /requests` carrying free text plus optional structured fields, and persist it with status `Draft`. |
| FR-102 | M | Validate a request against the eight qualification fields in §2.1.1 and compute a list of missing field names. |
| FR-103 | M | When fields are missing, set status `NeedsInfo` and emit a `ClarificationQuestion` per missing field, phrased for the requester. |
| FR-104 | M | Accept requester answers through `POST /requests/{id}/answers`, merge them, and re-run validation. |
| FR-105 | M | Set status `Qualified` only when every required field in §2.1.1 is populated. |
| FR-106 | M | Reject a request that is not actionable — no executive named, or a past deadline — with status `Rejected` and a stated reason. |
| FR-107 | S | Cap clarification rounds at 3; on exhaustion set `NeedsInfo` and surface to the EA with the outstanding fields listed. |

#### 2.1.1 Required qualification fields

`objective` · `business_justification` · `requested_executives` (≥1) · `required_attendees` · `duration_minutes` · `deadline` · `format` (Virtual | InPerson | Hybrid) · `supporting_artifacts` (list, or an explicit `no_artifacts_reason`)

### 2.2 Context intelligence — agent 2

| ID | Pri | Requirement |
|---|---|---|
| FR-201 | M | Retrieve related mail, Teams messages, prior meetings, and documents for a qualified request through `M365Port`. |
| FR-202 | M | Return a `ContextPackage` in which every claim carries a `SourceReference` with an ID and a URL. |
| FR-203 | M | Wrap all retrieved text as untrusted per `05-ports-and-adapters.md` §Untrusted content. |
| FR-204 | M | Retrieve only within the signed-in user's delegated permissions; record a `DataLimitation` where access is denied rather than failing the request. |
| FR-205 | S | Bound the package: at most 20 items, at most 8000 characters of quoted text, most-recent-first. |

### 2.3 Priority intelligence — agent 3

| ID | Pri | Requirement |
|---|---|---|
| FR-301 | M | Recommend one of `Tier1_Strategic`, `Tier2_Important`, `Tier3_Routine` from enterprise policy, org hierarchy, urgency, and the context package. |
| FR-302 | M | Return the policy factors that drove the tier, each with an evidence reference. |
| FR-303 | M | Read tier rules from `config/policy.yaml`; a tier is never invented by a language model. |
| FR-304 | M | Record an EA priority override as a `FeedbackEvent` without mutating the original recommendation. |

### 2.4 Scheduling orchestration — agent 4

| ID | Pri | Requirement |
|---|---|---|
| FR-401 | M | Retrieve free/busy for every required executive over the window `[now, deadline]` through `M365Port`. |
| FR-402 | M | Retrieve working hours from mailbox settings and treat time outside them as infeasible. |
| FR-403 | M | Enumerate every feasible slot under the hard constraints in §2.4.1 using CP-SAT. |
| FR-404 | M | Return each rejected candidate slot with the specific constraint that eliminated it. |
| FR-405 | M | Apply no preference or soft signal at this stage — see `INV-5`. |
| FR-406 | M | Return an empty `FeasibleSet` with the binding constraint stated when no slot exists, rather than relaxing a constraint. |
| FR-407 | S | Support in-person requests by adding a travel-buffer constraint from the location reference data in `config/locations.yaml`. |

#### 2.4.1 Hard constraints

Permission boundary · executive marked busy · non-movable event (`is_movable = false`) · protected focus block · outside working hours · after the deadline · violates minimum preparation buffer · travel infeasible between consecutive locations

### 2.5 Option ranking and explanation — agents 5 and 6

| ID | Pri | Requirement |
|---|---|---|
| FR-501 | M | Score every feasible slot with `score = wp·P + wu·U + wf·F + wl·L + wc·C − wd·D`. |
| FR-502 | M | Read the six weights from `config/weights.yaml`; never hard-code them. |
| FR-503 | M | Return the top 3 options ranked, or all of them when fewer than 3 are feasible. |
| FR-504 | M | Return each option's per-term score contribution, so a ranking can be explained arithmetically. |
| FR-505 | M | Produce for each option: the constraints considered, the conflicts avoided, the preferences applied, and the trade-off accepted. |
| FR-506 | M | Produce a confidence value in `[0,1]` with a stated reason. |
| FR-507 | M | List the data limitations that applied, including calendars that were not fully visible. |
| FR-508 | S | Produce a counterfactual for the top option: the next-best slot and the term that decided against it. |

### 2.6 Review gate and draft action — agents 7 and 8

| ID | Pri | Requirement |
|---|---|---|
| FR-601 | M | Present the recommendation packet through `GET /requests/{id}/recommendation`. |
| FR-602 | M | Accept exactly one EA decision — `approve`, `edit`, `reject`, `return_for_info`, `regenerate` — through `POST /requests/{id}/decision`. |
| FR-603 | M | Write an `ApprovalEvent` to the audit store carrying actor, timestamp, chosen option, and any edits. |
| FR-604 | M | Create a draft calendar event through `M365Port.create_draft_event` only when an `ApprovalEvent` exists for that recommendation. |
| FR-605 | M | Leave the draft unsent, and return its ID and web link so the EA can send it from Outlook. |
| FR-606 | M | Raise `ApprovalRequiredError` on any attempt to draft without an approval event. |
| FR-607 | M | Support `regenerate` by re-running agents 4–6 with an EA-supplied constraint hint, producing a new recommendation version. |
| FR-608 | S | Offer a kill switch — `settings.calendar_writes_enabled = false` disables drafting while recommendations continue to work. |

### 2.7 Governed learning — agents 9 to 12

| ID | Pri | Requirement |
|---|---|---|
| FR-701 | M | Capture every EA decision as a `FeedbackEvent` with reason code, free text, chosen outcome, and the profile and policy versions in force. |
| FR-702 | M | Store feedback in an evidence store that no recommendation reads. |
| FR-703 | M | Detect a repeated correction — the default threshold is 3 consistent corrections within 30 days — and emit a `CandidateRule`. |
| FR-704 | M | Validate a candidate against higher-priority enterprise policy and mark it `Blocked` on conflict, with the conflicting rule named. |
| FR-705 | M | Present candidates for approval through `GET /candidates`, showing evidence, confidence, projected impact, and exceptions. |
| FR-706 | M | Accept `approve`, `edit`, `reject`, `pause`, `defer` through `POST /candidates/{id}/decision`. |
| FR-707 | M | On approval, write an `ApprovedPreference` to the profile store with a new version number and an effective date. |
| FR-708 | M | Name, in every later recommendation, each approved preference that influenced it. |
| FR-709 | M | Support rollback to any prior profile version, recorded as its own audit event. |
| FR-710 | S | Report acceptance rate, override rate, latency, and token cost per request through `GET /metrics/summary`. |
| FR-711 | S | Keep candidates scoped to a single executive; cross-executive generalisation needs a policy-owner approval step. |

### 2.8 Audit

| ID | Pri | Requirement |
|---|---|---|
| FR-801 | M | Append every recommendation, approval, feedback event, policy change, and draft action to an append-only store. |
| FR-802 | M | Record for each: actor, action, timestamp, request ID, recommendation ID, evidence references, profile version, policy version, model version, approval ID, outcome. |
| FR-803 | M | Expose the audit trail for a request through `GET /requests/{id}/audit`. |
| FR-804 | M | Offer no update or delete operation on the audit store. |
| FR-805 | S | Replay a recommendation from its audit record and reproduce the identical ranking. |

---

## 3. Non-functional requirements

| ID | Pri | Requirement |
|---|---|---|
| NFR-01 | M | The full test suite runs offline with fakes: no tenant, no API key, no network. |
| NFR-02 | M | Deterministic output — the same fixtures and the same seed produce byte-identical recommendations. |
| NFR-03 | M | Time is injected through `ClockPort`; `src/` contains no `datetime.now()` call. |
| NFR-04 | M | `mypy src` passes in strict mode. |
| NFR-05 | M | `ruff check src tests` passes. |
| NFR-06 | M | Every requirement ID above appears in at least one test name or test docstring. |
| NFR-07 | S | A single-executive recommendation completes in under 5 seconds with fakes. |
| NFR-08 | S | Structured JSON logs, one line per agent invocation, carrying the request ID. |
| NFR-09 | S | Secrets come from environment variables, never from committed files. |
| NFR-10 | C | OpenTelemetry spans per agent, exportable to Application Insights. |

---

## 4. Scenario acceptance criteria

These come from the MVP brief and are the demo's pass conditions. `06-e2e-test-cases.md` turns each into an executable case.

### S1 — Qualified single-executive scheduling

- **AC-S1-1** An incomplete request is identified and qualified without EA intervention.
- **AC-S1-2** The EA receives a context package in which every item has a source reference.
- **AC-S1-3** At least three feasible options are produced when three exist.
- **AC-S1-4** Each option shows constraints considered, conflicts avoided, and priority rationale.
- **AC-S1-5** No event is created before a recorded EA approval.

### S2 — Multi-executive strategic scheduling

- **AC-S2-1** At least three executive calendars are evaluated through authorised access.
- **AC-S2-2** Infeasible options are returned with the blocking constraint named.
- **AC-S2-3** At least three ranked alternatives are offered when they exist.
- **AC-S2-4** Affected commitments and disruption trade-offs are shown explicitly.
- **AC-S2-5** No existing meeting is rescheduled automatically.

### S3 — EA feedback-to-preference learning

- **AC-S3-1** Structured and free-text feedback can be supplied for every recommendation.
- **AC-S3-2** Every feedback event links to its recommendation, policy version, and profile version.
- **AC-S3-3** A repeated pattern generates a candidate preference.
- **AC-S3-4** Candidates change no recommendation until an authorised person approves.
- **AC-S3-5** Approved rules are versioned, explainable, and reversible.
- **AC-S3-6** A before-and-after pair shows a recommendation changed by an approved preference.
