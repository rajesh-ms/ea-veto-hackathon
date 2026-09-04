# 07 — Build plan

Nine milestones. Each names the files to create, the requirements it closes, and a **gate** — a command whose green output is the completion criterion. Run the gate and read its output before reporting a milestone done.

Build in order. Each milestone leaves the suite green, so a regression is always attributable to the milestone that introduced it.

---

## M0 — Skeleton and domain

**Create**

```
pyproject.toml                 # deps pinned, ruff + mypy strict, pytest config
config/{weights,policy,locations,settings}.yaml
src/ea_copilot/__init__.py
src/ea_copilot/config.py       # Settings via pydantic-settings
src/ea_copilot/domain/{__init__,models,enums,errors,untrusted,state_machine}.py
src/ea_copilot/ports/{__init__,m365,llm,clock}.py
tests/conftest.py
tests/unit/test_layering.py
tests/unit/test_no_wall_clock.py
tests/unit/test_state_machine.py
```

Transcribe `03-data-contracts.md` §1–§10 exactly. Declare the three protocols from `05-ports-and-adapters.md` §1–§3 — signatures only.

`errors.py` defines `ApprovalRequiredError`, `CalendarWritesDisabledError`, `InvalidTransitionError`, `PermissionDeniedError`, `FixtureMissingError`, `InjectionRefusedError`.

**Closes** NFR-03, NFR-04, NFR-05

**Gate**

```bash
pytest tests/unit -v && mypy src && ruff check src tests
```

Green means: models import, the state machine rejects every transition outside its table, `src/` holds no wall-clock call, and `domain/` imports nothing from `adapters/`.

---

## M1 — Fakes and fixtures

**Create**

```
src/ea_copilot/adapters/{__init__,factory,clock_fixed,clock_system,m365_fake,llm_fake}.py
tests/fixtures/calendars/week_2026_09_14/{ceo,cfo,coo}.json
tests/fixtures/requests/{s1_incomplete,s1_complete,s2_strategic}.json
tests/fixtures/profiles/{cfo_baseline,cfo_learned}.json
tests/fixtures/llm/responses.json
tests/fixtures/injection/*.json
tests/unit/test_fakes.py
```

Build the fixture world from `06-e2e-test-cases.md` §1. Get the calendars right now — every later milestone asserts against them.

`cfo.json` must admit **at least three** feasible 30-minute slots in the week, and include a movable Tuesday 09:00 recurring block. `ceo.json` needs a protected Tuesday-morning board-prep block and Thursday travel. `coo.json` is heavily booked Wednesday, free Thursday afternoon.

`FakeM365Adapter` carries `write_log`, `read_log`, and `deny_access()`.

**Closes** NFR-01

**Gate**

```bash
pytest tests/unit/test_fakes.py -v
```

Asserts the CFO fixture yields ≥3 feasible slots, `write_log` starts empty, and `deny_access` produces a `PermissionDeniedError`.

---

## M2 — Intake and qualification

**Create**

```
src/ea_copilot/services/{__init__,validation,requests}.py
src/ea_copilot/services/audit.py
src/ea_copilot/agents/{__init__,a01_intake}.py
src/ea_copilot/orchestrator.py          # submit + answer only
tests/e2e/test_scenario_1_single_exec.py    # S1-01, S1-06 only
```

`services/validation.py` is pure: `MeetingRequest` in, missing-field list out, ordered as `01-requirements.md` §2.1.1. The model extracts values; the validator decides completeness.

`AuditStore` gets `append`, `find_approval`, `for_request` now; `replay` in M6.

**Closes** FR-101…FR-107, FR-801…FR-804

**Gate**

```bash
pytest -k "E2E_S1_01 or E2E_S1_06 or LAY_03" -v
```

---

## M3 — Context and injection defence

**Create**

```
src/ea_copilot/agents/a02_context.py
tests/e2e/test_prompt_injection.py
```

Wrap every external string as `UntrustedText` at the port boundary. Agent 2 holds no write capability — that separation, not the wrapper text, is what actually contains an attack.

Write all six injection cases including the benign control. A detector that flags "please ignore my earlier email" is unusable in an EA's inbox.

**Closes** FR-201…FR-205, INV-6

**Gate**

```bash
pytest -k "E2E_S1_02 or E2E_S1_07 or E2E_SEC" -v
```

All five hostile cases refused and logged; the benign control processed normally.

---

## M4 — Policy and solver

**Create**

```
src/ea_copilot/services/{policy,solver}.py
src/ea_copilot/agents/{a03_priority,a04_scheduling}.py
tests/unit/test_solver.py
tests/e2e/test_scenario_2_multi_exec.py     # S2-01, S2-02, S2-05, S2-06
```

CP-SAT in `services/solver.py`, pure: schedules and hard constraints in, `FeasibleSet` out. Its signature takes no profile — that is `INV-5` enforced by the type, not by discipline.

Every rejected slot records its `ConstraintKind`. An empty result sets `binding_constraint` rather than relaxing anything.

`services/policy.py` reads `config/policy.yaml`. No `LlmPort` anywhere in this milestone.

**Closes** FR-301…FR-304, FR-401…FR-407, INV-5

**Gate**

```bash
pytest -k "E2E_S1_04 or E2E_S2_01 or E2E_S2_02 or E2E_S2_05 or E2E_S2_06 or INV_5" -v
```

S2-06 is the important one: identical `FeasibleSet` across two different preference profiles.

---

## M5 — Ranking and explanation

**Create**

```
src/ea_copilot/services/{scoring,profile}.py
src/ea_copilot/agents/{a05_ranking,a06_explanation}.py
tests/unit/test_scoring.py
```

Scoring is arithmetic; weights come from `config/weights.yaml`. Return the full `ScoreBreakdown` so a rank is explainable term by term. Break ties by earlier start.

`ProfileStore.get_active()` returns `ApprovedPreference` only, and the class offers no method that returns a `CandidateRule`.

Confidence is computed in `services/scoring.py` from the rank-1/rank-2 margin damped by limitation count. The model writes the reason string, never the number.

**Closes** FR-501…FR-508

**Gate**

```bash
pytest -k "E2E_S1_03 or E2E_S2_03 or test_scoring" -v
```

Includes the arithmetic check: `total` matches the weighted sum to 6 decimal places.

---

## M6 — The gate and draft action

**Create**

```
src/ea_copilot/agents/{a07_workbench,a08_draft_action}.py
src/ea_copilot/services/audit.py        # add replay()
tests/e2e/test_governance_invariants.py
tests/unit/test_determinism.py
```

Check the approval **inside** `a08_draft_action.create_draft()`, before any port call. A caller reaching the agent directly meets the same wall — enforcing at the API layer would leave the invariant one refactor from lapsing.

`DraftEvent.approval_id` is non-optional and `is_sent` is `Literal[False]`, so an unapproved or sent draft is unrepresentable.

**Closes** FR-601…FR-608, FR-805, INV-1, INV-2, INV-4, NFR-02

**Gate**

```bash
pytest tests/e2e/test_governance_invariants.py tests/unit/test_determinism.py -v \
  && pytest -k "E2E_S1_05 or E2E_S2_04" -v
```

This is the milestone the whole design exists to protect. Every invariant test passes here and stays passing.

---

## M7 — Governed learning

**Create**

```
src/ea_copilot/services/{evidence,patterns}.py
src/ea_copilot/agents/{a09_feedback,a10_pattern,a11_preference_review,a12_evaluation}.py
tests/fixtures/feedback/cfo_tuesday_pattern.json
tests/e2e/test_scenario_3_learning.py
```

`services/patterns.py` is pure: feedback list in, candidates out. Threshold and window from settings.

Approval is the only path that writes an `ApprovedPreference` and increments `profile_version`. Rollback writes a *new* version matching an old one — history is appended to, never rewritten.

**Closes** FR-701…FR-711, INV-3

**Gate**

```bash
pytest tests/e2e/test_scenario_3_learning.py -v && pytest -k "INV_3" -v
```

S3-04 and S3-05 together are the demo's closing beat: identical rankings while a candidate is pending, changed rankings once approved.

---

## M8 — API, CLI, and the demo

**Create**

```
src/ea_copilot/api/{__init__,app,routes_requests,routes_review,routes_preferences,routes_metrics}.py
src/ea_copilot/cli/{__init__,demo}.py
tests/integration/test_api.py
README.md
```

Routes: `POST /requests`, `POST /requests/{id}/answers`, `GET /requests/{id}/recommendation`, `POST /requests/{id}/decision`, `POST /requests/{id}/draft`, `GET /requests/{id}/audit`, `GET /candidates`, `POST /candidates/{id}/decision`, `GET /metrics/summary`.

Routes translate HTTP to orchestrator calls and hold no business rules.

`cli/demo.py` runs the nine-beat storyline end to end, printing each step: incomplete request → clarification → context → priority → three options → EA approves → draft created (unsent) → repeated corrections → candidate proposed → approved → before/after recommendation.

**Closes** FR-710, NFR-07, NFR-08

**Gate**

```bash
pytest && python -m ea_copilot.cli.demo
```

Full suite green with zero skips in `tests/e2e`, and the demo runs start to finish without a traceback.

---

## M9 — Real adapters *(optional, after the demo works)*

**Create**

```
src/ea_copilot/adapters/{m365_workiq,llm_azure,m365_graph}.py
tests/integration/test_workiq_smoke.py    # marked `requires_tenant`
```

`WorkIqMcpAdapter` spawns `workiq mcp` through `cmd.exe /c` on Windows and holds one long-lived session. `m365_graph.py` stays a stub with its scopes documented.

Tenant-dependent tests are marked and deselected by default, so the offline guarantee survives.

Credentials come from environment variables read through `config.py` — `AZURE_OPENAI_ENDPOINT`, `AZURE_CLIENT_ID`. Real adapters use `DefaultAzureCredential`; no adapter reads a secret from a committed file, and `tests/unit/test_no_committed_secrets.py` greps `config/` for key-shaped strings.

**Closes** NFR-09

**Gate**

```bash
pytest -m "not requires_tenant"          # still fully green
pytest -m requires_tenant -v             # only with a signed-in tenant
```

---

## M10 — Scout live intake, visible memory, and complete recording

**Create or extend**

```
src/ea_copilot/domain/live_models.py
src/ea_copilot/services/{aliases,live_evidence,presentation,draft_commands}.py
src/ea_copilot/adapters/{scout_m365,obsidian_vault}.py
src/ea_copilot/integrations/scout_server.py
src/ea_copilot/api/routes_live.py
integrations/scout/ea-copilot/SKILL.md
tools/{install_scout_integration,install_obsidian}.ps1
tools/{run_live_scout_e2e,verify_live_evidence,verify_demo_privacy}.py
```

The live path accepts personal Teams intake through Scout, displays only `Exec A` and `Exec B`, ingests delegated Graph snapshots, and projects Current Session, Evidence History, and Governed Memory to Obsidian. Graph preference observations remain candidate evidence until the EA approves a new profile version.

Agent 8 remains the only path to the M365 write. Its Scout adapter emits a one-time command only after approval; Scout must call `workiq_create_event` with `[DEMO]`, the signed-in user as the sole explicit attendee, and literal `draft:true`. A matching completion is required before `DraftCreated`.

**Closes** FR-901, FR-902, FR-903, FR-904, FR-905, FR-906, FR-907, FR-908, FR-909

**Gate**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/acceptance_live_extension.ps1
```

The gate must have been observed red before implementation and must finish green with an intact Phoenix trace. Default `pytest` remains fake-only with zero E2E skips. Live execution pauses for human confirmation before the real draft and produces a sanitized evidence file plus a verified desktop WebM.

---

## Deferred

**NFR-10** — OpenTelemetry spans per agent, exported to Application Insights. Priority **C**, and deliberately outside the MVP: the audit store already answers "what did the system decide and why", which is the question this prototype exists to answer. Tracing becomes worthwhile when the system runs in Foundry, where the export target exists. Structured JSON logging (NFR-08, M8) covers the prototype's diagnostic need.

---

## Order and dependencies

```
M0 skeleton
 └─ M1 fakes
     ├─ M2 intake ──┐
     ├─ M3 context ─┤
     └─ M4 policy+solver
                    └─ M5 ranking
                        └─ M6 gate ◄── the invariants land here
                            └─ M7 learning
                                └─ M8 api + demo
                                    └─ M9 real adapters (optional)
                                        └─ M10 Scout + Obsidian live demo
```

M2, M3, and M4 are independent once M1 lands and can be built in any order. Everything from M5 on is strictly sequential.

## Reporting a milestone

State the milestone, paste the gate command's actual output, and list the requirement IDs closed. When a gate fails, fix the code — editing a test to make a gate pass is the one move that invalidates the whole exercise.
