# Scout, Microsoft 365, and Obsidian Live Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the governed scheduling prototype with personal Teams intake through Microsoft Scout, aliased live calendar context, a visible three-layer Obsidian memory projection, a two-phase draft-only bridge, and a complete validated desktop demo recording.

**Architecture:** Scout remains the owner of Microsoft 365 authentication and calls a local Python stdio MCP server. The existing deterministic orchestrator remains authoritative; a Scout-backed adapter accepts structured Graph snapshots and emits a one-time draft command only after Agent 8 finds an approval. Browser and Obsidian views receive only aliased, privacy-filtered projections.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2, OR-Tools, MCP Python SDK 1.29.0, vanilla HTML/CSS/JavaScript, pytest, Playwright, PowerShell, Microsoft Scout, Teams, Obsidian.

**Spec:** `docs/superpowers/specs/2026-09-04-scout-m365-obsidian-live-demo-design.md`

## Global Constraints

- Preserve `INV-1` through `INV-6`; do not weaken or remove their current tests.
- Visible executive names are exactly `Exec A` and `Exec B`.
- Mailbox identities live only in `.local/live-identities.json`, which is ignored by Git.
- The signed-in user is the sole explicit attendee for live drafts.
- Live subjects begin with `[DEMO]`; `draft` is always the literal boolean `true`.
- Do not expose accept, decline, cancel, move, update, send, or delete operations.
- Teams, mail, documents, event bodies, and Graph summaries are untrusted data.
- Graph observations are evidence and cannot influence ranking before preference approval.
- Obsidian is a one-way projection and never a scheduling input.
- Default `pytest` uses fakes only and has zero skipped E2E tests.
- A failed live preflight never falls back to fixture data while labelled live.
- Do not copy or persist Scout authentication tokens.
- Preserve unrelated working-tree changes and the existing `.phoenix/trace.jsonl`.

## File and Module Map

- `src/ea_copilot/domain/live_models.py`: frozen alias, calendar-board, Graph-evidence, and two-phase draft contracts.
- `src/ea_copilot/services/aliases.py`: alias lookup and recursive redaction without file I/O.
- `src/ea_copilot/services/live_evidence.py`: append/read Graph-derived evidence outside the request path.
- `src/ea_copilot/services/presentation.py`: build safe calendar and memory view models.
- `src/ea_copilot/adapters/scout_m365.py`: snapshot-backed `M365Port` and draft-command outbox.
- `src/ea_copilot/adapters/obsidian_vault.py`: atomic Markdown projection into three folders.
- `src/ea_copilot/integrations/scout_server.py`: FastMCP tools backed by one application runtime.
- `integrations/scout/ea-copilot/SKILL.md`: Scout tool-order and safety instructions.
- `integrations/scout/mcp-server.json`: registration template consumed by the installer.
- `tools/install_scout_integration.ps1`: backup, skill install, MCP config merge, and preflight.
- `tools/run_live_scout_e2e.py`: sanitized live-evidence verifier and human confirmation coordinator.
- `tools/verify_demo_privacy.py`: fail-closed scan for identity leakage and missing scenario markers.
- `src/ea_copilot/api/routes_live.py`: aliased calendar, memory, snapshot, and draft-completion endpoints.
- `src/ea_copilot/api/static/demo.*`: calendar board, memory layers, Scout status, and visible learning loop.

---

### Task 1: Formalize Extension Requirements and a Failure-First Gate

**Files:**
- Modify: `docs/01-requirements.md`
- Modify: `docs/03-data-contracts.md`
- Modify: `docs/05-ports-and-adapters.md`
- Modify: `docs/06-e2e-test-cases.md`
- Modify: `docs/07-build-plan.md`
- Modify: `docs/08-e2e-test-catalogue.md`
- Regenerate: `docs/08-test-cases.csv`
- Create: `tools/acceptance_live_extension.ps1`
- Create: `tests/e2e/test_live_extension_contract.py`

**Interfaces:**
- Consumes: the approved design and existing requirement/test traceability rules.
- Produces: requirements `FR-901` through `FR-909` and one command whose exit code is the Phoenix completion signal.

- [ ] **Step 1: Add the nine requirements and exact acceptance cases**

Add these requirements to `docs/01-requirements.md`:

```markdown
| FR-901 | Accept a personal Teams request through Scout and correlate it to one local request ID. |
| FR-902 | Show only `Exec A` and `Exec B`; redact configured mailbox identities from public surfaces. |
| FR-903 | Show two privacy-filtered live calendar lanes or an explicit delegated-access limitation. |
| FR-904 | Project Current Session, Evidence History, and Governed Memory as one-way Obsidian notes. |
| FR-905 | Keep Graph preference evidence inert until an EA-approved profile version activates it. |
| FR-906 | Execute a live draft as approval → command → `draft:true` → matching completion. |
| FR-907 | Integrate through Scout's authenticated custom MCP path without an Entra app registration. |
| FR-908 | Keep the default suite fake-only and fail closed when live preflight is unavailable. |
| FR-909 | Record and verify a redacted desktop demo containing all three scenarios. |
```

Add matching model definitions, port behavior, milestone acceptance text, and human-executable catalogue cases. Regenerate the CSV with `python tools/gen_test_csv.py`.

- [ ] **Step 2: Write the failing contract tests**

Create `tests/e2e/test_live_extension_contract.py` with imports that do not exist yet and tests named for every new ID. The supporting fixtures construct synthetic adapters and never access a tenant:

```python
def test_FR_901_scout_intake_correlates_one_request(scout_harness):
    result = scout_harness.submit_message(
        teams_message_id="teams-message-1",
        text="Schedule Exec A and Exec B for a 30-minute decision meeting.",
    )
    assert scout_harness.request_for_message("teams-message-1") == result.request_id


def test_FR_902_public_projection_contains_aliases_not_upns(alias_projection):
    encoded = json.dumps(alias_projection.public_payload)
    assert "Exec A" in encoded and "Exec B" in encoded
    assert alias_projection.internal_a not in encoded
    assert alias_projection.internal_b not in encoded


def test_FR_903_calendar_board_has_two_aliased_lanes(calendar_board):
    assert [lane.alias for lane in calendar_board.lanes] == ["Exec A", "Exec B"]
    assert all(block.label in {"Busy", "Protected", "Travel", "Preparation"}
               for lane in calendar_board.lanes for block in lane.blocks)


def test_FR_904_vault_has_exactly_three_memory_layers(projected_vault):
    assert projected_vault.root_names == {
        "01 Current Session", "02 Evidence History", "03 Governed Memory"
    }
    assert not projected_vault.identity_leaks


def test_FR_905_graph_candidate_is_inert_until_approved(graph_learning_world):
    assert graph_learning_world.before == graph_learning_world.with_candidate
    assert graph_learning_world.after_approval != graph_learning_world.before


def test_FR_906_draft_sequence_is_approval_command_completion(draft_world):
    assert draft_world.actions == ["ea_decision", "draft_command_created", "draft_created"]
    assert draft_world.command.draft is True
    assert draft_world.event.is_sent is False


def test_FR_907_scout_package_uses_stdio_without_credentials(scout_package):
    assert scout_package.transport == "stdio"
    assert scout_package.environment == {}
    assert not scout_package.contains_auth_material


def test_FR_908_default_runtime_has_no_live_dependency(runtime):
    assert isinstance(runtime.m365, FakeM365Adapter)
    assert runtime.live_mode is False


def test_FR_909_demo_manifest_requires_three_scenarios(valid_demo_manifest):
    assert {"scenario-1-complete", "scenario-2-complete", "scenario-3-complete"} <= set(
        valid_demo_manifest.scenes
    )
```

- [ ] **Step 3: Create the composite acceptance command**

`tools/acceptance_live_extension.ps1` must call the existing `tools/acceptance.ps1`, the new privacy verifier, the MCP transcript test, and media verification for `artifacts/ea-copilot-scout-demo.webm`. Each child process is invoked with an argument array and a non-zero exit immediately fails the script.

- [ ] **Step 4: Run the gate and record the required red result**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/acceptance_live_extension.ps1
```

Expected: non-zero because the new live contracts and artifacts are absent. Record this exact command as the new Phoenix failure-first check without replacing `.phoenix/trace.jsonl`.

- [ ] **Step 5: Verify documentation consistency**

Run `python tools/check_docs.py`.

Expected: success with 96 defined and 96 covered requirement IDs, and the catalogue/CSV totals equal.

- [ ] **Step 6: Commit the contract**

```powershell
git add -- docs/01-requirements.md docs/03-data-contracts.md docs/05-ports-and-adapters.md docs/06-e2e-test-cases.md docs/07-build-plan.md docs/08-e2e-test-catalogue.md docs/08-test-cases.csv tools/acceptance_live_extension.ps1 tests/e2e/test_live_extension_contract.py
git commit -m "test: define Scout live-demo acceptance contract"
```

### Task 2: Alias Directory and Privacy-Safe Calendar Models

**Files:**
- Create: `src/ea_copilot/domain/live_models.py`
- Create: `src/ea_copilot/services/aliases.py`
- Create: `src/ea_copilot/services/presentation.py`
- Modify: `src/ea_copilot/domain/__init__.py`
- Modify: `.gitignore`
- Test: `tests/unit/test_aliases.py`
- Test: `tests/unit/test_calendar_presentation.py`

**Interfaces:**
- Consumes: `CalendarEvent`, `ScheduleResponse`, `TimeSlot`, and a mapping loaded by an outer adapter.
- Produces: `AliasDirectory.resolve(alias) -> str`, `AliasDirectory.alias_for(identifier) -> ExecutiveAlias`, `AliasDirectory.redact(value) -> object`, and `build_calendar_board(request_id: str, source: Literal["fixture", "live_via_scout"], aliases: AliasDirectory, schedules: list[ScheduleResponse], events: dict[str, list[CalendarEvent]], candidate_slots: list[TimeSlot]) -> CalendarBoard`.

- [ ] **Step 1: Write failing alias and presentation tests**

Use only synthetic identifiers in tests:

```python
directory = AliasDirectory({"Exec A": "mailbox-alpha", "Exec B": "mailbox-beta"})
payload = {"people": ["mailbox-alpha", "mailbox-beta"], "note": "mailbox-alpha busy"}
assert directory.redact(payload) == {
    "people": ["Exec A", "Exec B"],
    "note": "Exec A busy",
}
```

Assert a `CalendarBoard` has lane labels `['Exec A', 'Exec B']`, generic block labels such as `Busy` or `Protected`, and no original event subject/body/organizer/attendee values.

- [ ] **Step 2: Run the tests to verify red**

Run `pytest tests/unit/test_aliases.py tests/unit/test_calendar_presentation.py -v`.

Expected: import failure for `ea_copilot.services.aliases`.

- [ ] **Step 3: Add frozen view contracts**

Define:

```python
ExecutiveAlias = Literal["Exec A", "Exec B"]

class CalendarBlock(DomainModel):
    block_id: str
    start: datetime
    end: datetime
    category: Literal["busy", "protected", "travel", "preparation", "candidate"]
    label: str

class CalendarLane(DomainModel):
    alias: ExecutiveAlias
    blocks: list[CalendarBlock]
    access_limited: bool = False
    limitation: str | None = None

class CalendarBoard(DomainModel):
    request_id: str
    source: Literal["fixture", "live_via_scout"]
    lanes: list[CalendarLane]
    candidate_slots: list[TimeSlot]
```

Implement `AliasDirectory` as a frozen in-memory service. Reject missing aliases, duplicate identifiers, extra aliases, and mappings other than exactly `Exec A`/`Exec B`. Recursively redact strings, lists, tuples, and dictionaries.

- [ ] **Step 4: Build the safe calendar projection**

`build_calendar_board` receives already-read schedules/events and emits only category labels. Use event flags and location presence to classify blocks; never copy `subject`, `body_preview`, `organizer`, or attendees.

- [ ] **Step 5: Ignore local runtime identity and vault data**

Append these exact entries to `.gitignore`:

```gitignore
.local/
demo-vault/
artifacts/live-scout-evidence.json
```

- [ ] **Step 6: Run focused and invariant tests**

Run:

```powershell
pytest tests/unit/test_aliases.py tests/unit/test_calendar_presentation.py tests/e2e/test_governance_invariants.py -v
ruff check src/ea_copilot/domain/live_models.py src/ea_copilot/services/aliases.py src/ea_copilot/services/presentation.py tests/unit/test_aliases.py tests/unit/test_calendar_presentation.py
mypy src
```

Expected: all green.

- [ ] **Step 7: Commit the alias boundary**

```powershell
git add -- .gitignore src/ea_copilot/domain/live_models.py src/ea_copilot/domain/__init__.py src/ea_copilot/services/aliases.py src/ea_copilot/services/presentation.py tests/unit/test_aliases.py tests/unit/test_calendar_presentation.py
git commit -m "feat: add aliased calendar presentation boundary"
```

### Task 3: Scout Snapshot Adapter and Graph Preference Evidence

**Files:**
- Modify: `src/ea_copilot/domain/live_models.py`
- Modify: `src/ea_copilot/domain/models.py`
- Modify: `src/ea_copilot/services/database.py`
- Create: `src/ea_copilot/services/live_evidence.py`
- Create: `src/ea_copilot/adapters/scout_m365.py`
- Modify: `src/ea_copilot/adapters/__init__.py`
- Modify: `src/ea_copilot/agents/a10_pattern.py`
- Modify: `src/ea_copilot/bootstrap.py`
- Test: `tests/unit/test_scout_m365.py`
- Test: `tests/e2e/test_scout_graph_learning.py`

**Interfaces:**
- Consumes: privacy-filtered `ScoutCalendarSnapshot` and `GraphPreferenceEvidence` submitted by Scout.
- Produces: a complete snapshot-backed `M365Port`, `LiveEvidenceStore.append/read`, and candidate generation that remains isolated from request-time profile reads.

- [ ] **Step 1: Write failing snapshot and evidence-isolation tests**

Define tests around these contracts:

```python
class GraphPreferenceEvidence(DomainModel):
    evidence_id: str
    executive_upn: str
    dimension: Literal["weekday", "time_of_day", "meeting_gap", "preparation"]
    value: str
    source: SourceReference
    confidence: float = Field(ge=0.0, le=1.0)
    observed_at: datetime

class ScoutCalendarSnapshot(DomainModel):
    request_id: str
    captured_at: datetime
    schedules: list[ScheduleResponse]
    events: dict[str, list[CalendarEvent]]
    mail: list[MailMessage] = Field(default_factory=list)
    teams: list[ChatMessage] = Field(default_factory=list)
    files: list[FileReference] = Field(default_factory=list)
    limitations: list[DataLimitation] = Field(default_factory=list)
```

Assert that reads fail before ingestion, preserve `access_limited`, and never call a network API. Append three matching Graph observations, detect one candidate, rerun the same request, and assert byte-identical ranking until candidate approval.

- [ ] **Step 2: Run focused tests to verify red**

Run `pytest tests/unit/test_scout_m365.py tests/e2e/test_scout_graph_learning.py -v`.

Expected: missing `ScoutM365Adapter` and `LiveEvidenceStore`.

- [ ] **Step 3: Add append-only Graph evidence storage**

Add `graph_preference_evidence` with an autoincrement sequence, unique evidence ID, executive ID index, captured timestamp, and JSON data. `LiveEvidenceStore` exposes `append`, `for_executive`, and `all`; it exposes no update/delete.

Extend `PatternEvidence` with `graph_evidence_ids: list[str] = Field(default_factory=list)`. Keep `feedback_ids` unchanged so existing serialized evidence and tests remain compatible.

- [ ] **Step 4: Implement the snapshot-backed read adapter**

`ScoutM365Adapter.ingest(snapshot)` stores one bounded snapshot and its read methods implement the existing `M365Port` without network access. It must return explicit `PermissionDeniedError` or access-limited schedules when the submitted snapshot says access is limited. Its write method remains unimplemented until Task 5 and raises `CalendarWritesDisabledError`.

Add `build_live_runtime(root: Path, *, aliases: AliasDirectory, self_identifier: str, database: Database | None = None, clock: ClockPort | None = None, vault_path: Path | None = None) -> ApplicationRuntime`. Generalize `ApplicationRuntime.m365` to `M365Port`, add `live_mode: bool`, and set it to `False` in `build_runtime` and `True` in `build_live_runtime`.

- [ ] **Step 5: Extend candidate detection without activating candidates**

Add `PatternAgent.detect_graph(executive_id)` that groups approved-shape observations by `(dimension, value)`, applies the existing threshold/window policy, and writes `CandidateRule` with Graph evidence IDs. Do not add any Graph evidence read to `RankingAgent`, `ScoringService`, or `ProfileStore`.

- [ ] **Step 6: Run focused, isolation, and determinism gates**

Run:

```powershell
pytest tests/unit/test_scout_m365.py tests/e2e/test_scout_graph_learning.py tests/e2e/test_scenario_3_learning.py tests/e2e/test_governance_invariants.py -v
pytest tests/unit/test_determinism.py tests/unit/test_layering.py -v
ruff check src tests
mypy src
```

- [ ] **Step 7: Commit the Scout read path**

```powershell
git add -- src/ea_copilot/domain/live_models.py src/ea_copilot/domain/models.py src/ea_copilot/services/database.py src/ea_copilot/services/live_evidence.py src/ea_copilot/adapters/scout_m365.py src/ea_copilot/adapters/__init__.py src/ea_copilot/agents/a10_pattern.py src/ea_copilot/bootstrap.py tests/unit/test_scout_m365.py tests/e2e/test_scout_graph_learning.py
git commit -m "feat: ingest Scout calendar and Graph evidence"
```

### Task 4: Three-Layer Obsidian Projection

**Files:**
- Modify: `src/ea_copilot/domain/live_models.py`
- Modify: `src/ea_copilot/services/presentation.py`
- Create: `src/ea_copilot/adapters/obsidian_vault.py`
- Modify: `src/ea_copilot/bootstrap.py`
- Test: `tests/unit/test_memory_projection.py`
- Test: `tests/e2e/test_obsidian_memory_layers.py`

**Interfaces:**
- Consumes: aliased request/recommendation state, audit records, feedback/Graph evidence, candidate rules, and approved profile versions.
- Produces: `MemoryProjection` plus `ObsidianVaultAdapter.project(projection) -> VaultProjectionResult`.

- [ ] **Step 1: Write failing projection tests**

Tests create a temporary vault, project one request, and assert these exact roots:

```text
01 Current Session/
02 Evidence History/
03 Governed Memory/
```

Assert the current note contains candidate slots and versions, evidence notes contain audit/feedback/candidate provenance, governed notes contain only approved profiles, and no note contains either synthetic mailbox identifier.

- [ ] **Step 2: Run tests to verify red**

Run `pytest tests/unit/test_memory_projection.py tests/e2e/test_obsidian_memory_layers.py -v`.

Expected: missing `ObsidianVaultAdapter`.

- [ ] **Step 3: Define one-way projection contracts**

Create frozen `MemoryNote`, `MemoryLayer`, `MemoryProjection`, and `VaultProjectionResult` models. The presentation service accepts store values and returns Markdown-ready safe notes; it performs no file I/O.

- [ ] **Step 4: Implement atomic vault writes**

`ObsidianVaultAdapter` creates the three roots, writes a same-directory temporary file, then replaces the target. It may overwrite Current Session notes, must create uniquely named Evidence History notes, and must create versioned Governed Memory notes. It exposes no read method.

- [ ] **Step 5: Wire optional projection into the runtime**

Add an optional vault adapter to `ApplicationRuntime`; default builds use an in-memory/no-op projection. Demo/live builds receive `root / 'demo-vault'`. Projection failures append an audit outcome and do not fail scheduling.

- [ ] **Step 6: Verify memory governance**

Run:

```powershell
pytest tests/unit/test_memory_projection.py tests/e2e/test_obsidian_memory_layers.py tests/e2e/test_scenario_3_learning.py -v
ruff check src tests
mypy src
```

- [ ] **Step 7: Commit the vault projection**

```powershell
git add -- src/ea_copilot/domain/live_models.py src/ea_copilot/services/presentation.py src/ea_copilot/adapters/obsidian_vault.py src/ea_copilot/bootstrap.py tests/unit/test_memory_projection.py tests/e2e/test_obsidian_memory_layers.py
git commit -m "feat: project three governed memory layers"
```

### Task 5: Approval-Bound Two-Phase Draft Bridge

**Files:**
- Modify: `src/ea_copilot/domain/live_models.py`
- Modify: `src/ea_copilot/domain/enums.py`
- Modify: `src/ea_copilot/domain/state_machine.py`
- Modify: `src/ea_copilot/ports/m365.py`
- Modify: `src/ea_copilot/adapters/scout_m365.py`
- Modify: `src/ea_copilot/agents/a08_draft_action.py`
- Modify: `src/ea_copilot/orchestrator.py`
- Modify: `src/ea_copilot/services/database.py`
- Create: `src/ea_copilot/services/draft_commands.py`
- Test: `tests/unit/test_draft_commands.py`
- Test: `tests/e2e/test_scout_draft_governance.py`

**Interfaces:**
- Consumes: a recorded `ApprovalEvent` and the selected option.
- Produces: `DraftCommand | DraftEvent`, `DraftCommandStore.pending(command_id)`, and `complete_draft(completion) -> DraftEvent`.

- [ ] **Step 1: Write failure-first governance tests**

Define exact contracts:

```python
class DraftCommand(DomainModel):
    command_id: str
    transaction_id: str
    request_id: str
    recommendation_id: str
    approval_id: str
    subject: str
    body: str
    slot: TimeSlot
    attendee: str
    location: str | None = None
    draft: Literal[True] = True
    created_at: datetime

class DraftAuthorization(DomainModel):
    request_id: str
    recommendation_id: str
    approval_id: str

class DraftCompletion(DomainModel):
    command_id: str
    transaction_id: str
    graph_event_id: str
    web_link: str
    draft: Literal[True]
    completed_at: datetime
```

Tests must prove: no approval means no command row; non-approval decisions mean no command; command subject is `[DEMO] Executive scheduling prototype`; only self attendee exists; completion cannot precede command; `draft=False` fails Pydantic validation; duplicate completion returns the same `DraftEvent`; request status becomes `DRAFT_CREATED` only after completion.

- [ ] **Step 2: Run tests to verify red**

Run `pytest tests/unit/test_draft_commands.py tests/e2e/test_scout_draft_governance.py -v`.

- [ ] **Step 3: Add append-only command/result tables**

Create tables for draft commands and completions. `DraftCommandStore` exposes append/read/pending/complete; completion inserts once under a unique transaction ID and never updates/deletes a command.

- [ ] **Step 4: Extend the sole M365 write return type**

Change the return type of `M365Port.create_draft_event` to `DraftEvent | DraftCommand` and add required keyword `authorization: DraftAuthorization`. The method name set remains identical, preserving `INV-2`. Agent 8 constructs the authorization only after finding the recorded approval. The fake continues returning `DraftEvent`; `ScoutM365Adapter` returns a `DraftCommand` bound to those three IDs.

- [ ] **Step 5: Enforce the fixed live command in Agent 8**

The live adapter receives the already-validated approval context and ignores requester-controlled subject/attendee edits for live demo mode. It generates `[DEMO] Executive scheduling prototype`, the discovered self attendee, `draft=True`, and a stable transaction ID.

Agent 8 audits `draft_command_created` when it receives a command and audits `draft_created` only after `complete_draft`. `RequestOrchestrator.create_draft` leaves the request in an approved/pending state for a command and transitions only for a `DraftEvent`.

- [ ] **Step 6: Re-run invariant and bridge tests**

Run:

```powershell
pytest tests/e2e/test_governance_invariants.py tests/e2e/test_scout_draft_governance.py tests/unit/test_draft_commands.py -v
ruff check src tests
mypy src
```

- [ ] **Step 7: Commit the draft bridge**

```powershell
git add -- src/ea_copilot/domain/live_models.py src/ea_copilot/domain/enums.py src/ea_copilot/domain/state_machine.py src/ea_copilot/ports/m365.py src/ea_copilot/adapters/scout_m365.py src/ea_copilot/agents/a08_draft_action.py src/ea_copilot/orchestrator.py src/ea_copilot/services/database.py src/ea_copilot/services/draft_commands.py tests/unit/test_draft_commands.py tests/e2e/test_scout_draft_governance.py
git commit -m "feat: gate Scout drafts with two-phase completion"
```

### Task 6: Local MCP Server and Scout Integration Package

**Files:**
- Modify: `pyproject.toml`
- Create: `src/ea_copilot/integrations/__init__.py`
- Create: `src/ea_copilot/integrations/scout_server.py`
- Create: `src/ea_copilot/integrations/__main__.py`
- Create: `integrations/scout/ea-copilot/SKILL.md`
- Create: `integrations/scout/mcp-server.json`
- Create: `tools/install_scout_integration.ps1`
- Test: `tests/integration/test_scout_mcp.py`
- Test: `tests/unit/test_scout_package.py`

**Interfaces:**
- Consumes: `build_live_runtime`, `ScoutCalendarSnapshot`, approval decisions, draft commands, and completions.
- Produces: stdio MCP tools `ea_submit_request`, `ea_attach_snapshot`, `ea_get_recommendation`, `ea_record_decision`, `ea_prepare_draft`, `ea_complete_draft`, and `ea_get_demo_state`.

- [ ] **Step 1: Pin the required MCP dependency and write failing tests**

Add `mcp==1.29.0` to project dependencies. Write a real stdio-client test that starts `python -m ea_copilot.integrations`, initializes MCP, lists tools, and asserts the exact seven-tool allow-list. Assert no tool name contains `send`, `update`, `move`, `delete`, `accept`, `decline`, `shell`, or `graph`.

- [ ] **Step 2: Run the MCP tests to verify red**

Run `pytest tests/integration/test_scout_mcp.py tests/unit/test_scout_package.py -v`.

Expected: missing integration module.

- [ ] **Step 3: Implement FastMCP tools as thin translators**

Use `FastMCP('ea-copilot')`. Tool functions validate Pydantic input and call the same orchestrator/services as HTTP. They return model-dumped JSON and never log stdio protocol traffic to stdout. Runtime diagnostics go to stderr.

`ea_complete_draft` requires `draft: Literal[True]`; `ea_prepare_draft` returns `approval_required` unless the audit contains a valid approval.

- [ ] **Step 4: Write the Scout skill**

The skill must prescribe this sequence:

```text
extract alias-only intake
→ Work IQ delegated reads
→ ea_attach_snapshot
→ ea_get_recommendation
→ wait for explicit EA decision
→ ea_record_decision
→ ea_prepare_draft
→ wait for action-time human confirmation
→ workiq_create_event with draft:true
→ ea_complete_draft
```

It must state that `workiq_create_event` defaults to sending when `draft` is omitted, so omission/false is forbidden. It must forbid every other calendar mutation and require `[DEMO]` plus the signed-in user as sole attendee.

- [ ] **Step 5: Add registration and reversible installer**

`integrations/scout/mcp-server.json` contains a stdio command using the current Python executable and the absolute repository path supplied by the installer. The PowerShell installer:

1. verifies Scout is running or installed;
2. copies the skill to `$env:USERPROFILE\.scout\skills\ea-copilot\SKILL.md`;
3. backs up `$env:USERPROFILE\.scout\m-mcp-servers.json` with a timestamp;
4. merges only the `ea-copilot` entry;
5. never writes tokens or UPNs;
6. supports `-WhatIf` and `-Uninstall`.

- [ ] **Step 6: Verify the package and stdio protocol**

Run:

```powershell
pytest tests/integration/test_scout_mcp.py tests/unit/test_scout_package.py -v
powershell -NoProfile -ExecutionPolicy Bypass -File tools/install_scout_integration.ps1 -WhatIf
ruff check src tests
mypy src
```

- [ ] **Step 7: Commit the integration package**

```powershell
git add -- pyproject.toml src/ea_copilot/integrations integrations/scout tools/install_scout_integration.ps1 tests/integration/test_scout_mcp.py tests/unit/test_scout_package.py
git commit -m "feat: expose governed scheduling to Scout MCP"
```

### Task 7: Live API and Calendar/Memory Workbench

**Files:**
- Create: `src/ea_copilot/api/routes_live.py`
- Modify: `src/ea_copilot/api/app.py`
- Modify: `src/ea_copilot/api/schemas.py`
- Modify: `src/ea_copilot/api/static/demo.html`
- Modify: `src/ea_copilot/api/static/demo.css`
- Modify: `src/ea_copilot/api/static/demo.js`
- Test: `tests/integration/test_live_api.py`
- Test: `tests/integration/test_live_workbench.py`

**Interfaces:**
- Consumes: safe calendar/memory projections and Scout bridge state.
- Produces: `/live/status`, `/live/requests/{id}/calendar`, `/live/requests/{id}/memory`, `/live/snapshots`, `/live/drafts/{command_id}/complete`, and a browser UI containing all required visual states.

- [ ] **Step 1: Write failing API and browser-contract tests**

Assert API responses contain `Exec A`, `Exec B`, `source='live_via_scout'`, memory layer names, and no configured identifier. Assert the HTML contains stable test IDs:

```text
scout-status
calendar-lane-exec-a
calendar-lane-exec-b
memory-current-session
memory-evidence-history
memory-governed
candidate-inert-marker
profile-version-change
draft-pending-marker
draft-created-marker
```

- [ ] **Step 2: Run tests to verify red**

Run `pytest tests/integration/test_live_api.py tests/integration/test_live_workbench.py -v`.

- [ ] **Step 3: Implement live routes with redaction at the response boundary**

All public response objects pass through `AliasDirectory.redact`. Snapshot ingestion accepts internal identifiers but returns only alias counts and limitations. Completion validates command/transaction matching and `draft=True` before calling the orchestrator completion path.

- [ ] **Step 4: Build the calendar board**

Render a shared time axis with two lanes, generic category blocks, candidate overlays, access-limitation states, and a prominent `LIVE VIA SCOUT` or `DETERMINISTIC FIXTURE` source pill. Never render event subject text.

- [ ] **Step 5: Build the three-layer memory panel and learning animation**

Display Current Session, Evidence History, and Governed Memory side by side. Scenario 3 visibly adds three evidence items, creates an inert candidate, approves it, changes `v1` to `v2`, and reranks the same request. Reduced-motion mode shows the same states without animation.

- [ ] **Step 6: Keep approval and draft pending states distinct**

The draft button first demonstrates the pre-approval block. After approval it shows `Pending Scout execution`; only a valid completion shows `Unsent draft created`. No UI copy says an invitation was sent.

- [ ] **Step 7: Run API, browser, and accessibility gates**

Run:

```powershell
pytest tests/integration/test_live_api.py tests/integration/test_live_workbench.py tests/integration/test_api.py -v
python tools/run_browser_e2e.py
ruff check src tests
mypy src
```

- [ ] **Step 8: Commit the workbench**

```powershell
git add -- src/ea_copilot/api/routes_live.py src/ea_copilot/api/app.py src/ea_copilot/api/schemas.py src/ea_copilot/api/static/demo.html src/ea_copilot/api/static/demo.css src/ea_copilot/api/static/demo.js tests/integration/test_live_api.py tests/integration/test_live_workbench.py
git commit -m "feat: show live calendars and governed memory"
```

### Task 8: Live Preflight, Obsidian Setup, and Sanitized Evidence

**Files:**
- Create: `tools/run_live_scout_e2e.py`
- Create: `tools/verify_live_evidence.py`
- Create: `tools/install_obsidian.ps1`
- Create: `tests/integration/test_live_evidence.py`
- Create local only: `.local/live-identities.json`
- Create local only: `artifacts/live-scout-evidence.json`

**Interfaces:**
- Consumes: installed Scout integration, connected personal Teams relay, live MCP state, and explicit human confirmation.
- Produces: redacted evidence JSON proving intake correlation, live reads, memory projection, draft arguments/result, and forbidden-tool absence.

- [ ] **Step 1: Write failing evidence-verifier tests**

Valid evidence must contain:

```json
{
  "aliases": ["Exec A", "Exec B"],
  "teams_intake_correlated": true,
  "calendar_source": "live_via_scout",
  "memory_layers": ["Current Session", "Evidence History", "Governed Memory"],
  "candidate_inert_before_approval": true,
  "profile_version_changed": true,
  "draft": {"subject_prefix": "[DEMO]", "draft": true, "attendee_count": 1, "is_sent": false},
  "forbidden_calendar_tools": []
}
```

Tests reject any email-shaped string, missing layer, false draft flag, attendee count other than one, or forbidden tool entry.

- [ ] **Step 2: Run verifier tests to prove red**

Run `pytest tests/integration/test_live_evidence.py -v`.

- [ ] **Step 3: Implement fail-closed Scout preflight**

The runner checks Scout process presence, custom MCP registration, skill presence, Teams relay status evidence, alias mapping, and Obsidian availability. It prints aliases only. Missing prerequisites return non-zero and never switch the browser to live mode.

- [ ] **Step 4: Add reversible Obsidian installation**

`tools/install_obsidian.ps1` first tests for the executable, supports `-WhatIf`, uses `winget install --id Obsidian.Obsidian --exact --silent --accept-package-agreements --accept-source-agreements` only when absent, and exits non-zero if the executable still cannot be found. It never deletes an existing vault.

- [ ] **Step 5: Coordinate the live flow without automating confirmation**

`run_live_scout_e2e.py` validates state and waits at `awaiting_human_confirmation`. The human confirmation occurs in the Scout/workbench UI. Afterward the script reads only sanitized tool/audit evidence, validates `workiq_create_event` arguments and completion, and writes `artifacts/live-scout-evidence.json`.

- [ ] **Step 6: Run offline verifier tests**

Run:

```powershell
pytest tests/integration/test_live_evidence.py -v
python tools/verify_live_evidence.py tests/fixtures/live/scout-evidence-valid.json
powershell -NoProfile -ExecutionPolicy Bypass -File tools/install_obsidian.ps1 -WhatIf
```

- [ ] **Step 7: Install and configure local integrations**

Run the Scout installer, then the Obsidian installer if required. Create `.local/live-identities.json` through the setup prompt; do not print or commit its contents. Restart/refresh Scout so it discovers the skill and MCP server.

- [ ] **Step 8: Commit code and fixture evidence only**

```powershell
git add -- tools/run_live_scout_e2e.py tools/verify_live_evidence.py tools/install_obsidian.ps1 tests/integration/test_live_evidence.py tests/fixtures/live/scout-evidence-valid.json
git commit -m "test: add fail-closed Scout live validation"
```

### Task 9: Complete Desktop Recording and Privacy Verification

**Files:**
- Modify: `tools/run_browser_e2e.py`
- Modify: `tools/verify_demo_video.py`
- Create: `tools/verify_demo_privacy.py`
- Create: `tools/record_desktop_demo.ps1`
- Modify: `tests/integration/test_recording.py`
- Create: `artifacts/ea-copilot-scout-demo.webm`
- Create: `artifacts/ea-copilot-scout-demo.manifest.json`

**Interfaces:**
- Consumes: the live evidence file, browser scenario markers, arranged Teams/Scout/browser/Obsidian windows, and desktop recording capability.
- Produces: one playable redacted WebM and a manifest listing all three completed scenarios and required scenes.

- [ ] **Step 1: Write failing manifest/privacy/media tests**

The manifest schema requires scene IDs:

```text
teams-intake
calendar-exec-a-b
memory-three-layers
approval-gate
demo-unsent-draft
learning-before-after
quality-gates
scenario-1-complete
scenario-2-complete
scenario-3-complete
```

Tests reject missing scenes, zero-duration media, absent video dimensions, email-shaped text in extracted captions/manifest, configured identity strings, and any phrase claiming the invitation was sent.

- [ ] **Step 2: Run tests to verify red**

Run `pytest tests/integration/test_recording.py -v`.

- [ ] **Step 3: Extend the deterministic browser recorder**

Keep the existing fake-only recorder as a regression asset. Add stable markers for calendar lanes and the three memory layers so its Playwright assertions cover all three scenarios without tenant access.

- [ ] **Step 4: Add desktop capture orchestration**

`record_desktop_demo.ps1` verifies a supported recorder, creates a dedicated output path, starts capture, and stops it in a `finally` block. It does not log window titles or environment variables. If no supported capture backend exists, it fails with a bounded prerequisite message instead of creating a fake video.

- [ ] **Step 5: Run the redaction preflight and record**

Arrange only the personal Scout chat, demo browser, and demo vault. Run the privacy verifier before capture. Record the sequence from Task 8; pause at the real draft confirmation for the user. Stop capture after quality-gate evidence is visible.

- [ ] **Step 6: Verify the complete video and manifest**

Run:

```powershell
python tools/verify_demo_video.py artifacts/ea-copilot-scout-demo.webm
python tools/verify_demo_privacy.py artifacts/ea-copilot-scout-demo.manifest.json artifacts/live-scout-evidence.json demo-vault
```

- [ ] **Step 7: Commit verifiers and the sanitized demo artifact**

```powershell
git add -- tools/run_browser_e2e.py tools/verify_demo_video.py tools/verify_demo_privacy.py tools/record_desktop_demo.ps1 tests/integration/test_recording.py artifacts/ea-copilot-scout-demo.webm artifacts/ea-copilot-scout-demo.manifest.json
git commit -m "demo: record Scout calendar and memory scenarios"
```

### Task 10: Final Review, Phoenix Proof, and Handoff

**Files:**
- Modify: `README.md`
- Modify: `docs/00-INDEX.md`
- Modify: `.phoenix-ralph/progress.md` only if it already tracks this extension; otherwise leave it untouched.

**Interfaces:**
- Consumes: every preceding deliverable and the exact composite acceptance command.
- Produces: verified offline/live/demo instructions and a failure-first Phoenix acceptance result.

- [ ] **Step 1: Document both operating modes**

README commands must distinguish:

```powershell
# deterministic, no tenant
powershell -NoProfile -ExecutionPolicy Bypass -File tools/acceptance.ps1

# installed Scout/Teams/Obsidian demo; pauses before real draft
python tools/run_live_scout_e2e.py

# full extension proof using already-captured sanitized live evidence
powershell -NoProfile -ExecutionPolicy Bypass -File tools/acceptance_live_extension.ps1
```

- [ ] **Step 2: Run the complete quality suite**

Run:

```powershell
pytest --strict-markers -q
ruff check src tests
mypy src
python tools/check_docs.py
python tools/run_browser_e2e.py
python tools/verify_live_evidence.py artifacts/live-scout-evidence.json
python tools/verify_demo_video.py artifacts/ea-copilot-scout-demo.webm
python tools/verify_demo_privacy.py artifacts/ea-copilot-scout-demo.manifest.json artifacts/live-scout-evidence.json demo-vault
```

Expected: all commands succeed; `tests/e2e` has zero skips.

- [ ] **Step 3: Run the exact failure-first Phoenix acceptance check**

Run `powershell -NoProfile -ExecutionPolicy Bypass -File tools/acceptance_live_extension.ps1` through `phoenix_accept` using the same command digest recorded red in Task 1.

Expected: `saw_red=true`, `green_after_red=true`, `currently_green=true`, `trace_intact=true`, and `ok=true`.

- [ ] **Step 4: Inspect the final diff and prohibited data**

Run `git status --short`, `git diff --check`, and the privacy verifier. Confirm `.local/live-identities.json`, raw Scout logs, and authentication state are untracked and absent from the commit history.

- [ ] **Step 5: Commit documentation only**

```powershell
git add -- README.md docs/00-INDEX.md
git commit -m "docs: explain governed Scout live demo"
```

- [ ] **Step 6: Report objective evidence**

Provide the test counts, lint/type/doc results, Phoenix acceptance fields, live evidence summary, and clickable paths to the video, manifest, vault root, and integration instructions. State explicitly that the calendar item is an unsent `[DEMO]` draft and no invitation was sent.
