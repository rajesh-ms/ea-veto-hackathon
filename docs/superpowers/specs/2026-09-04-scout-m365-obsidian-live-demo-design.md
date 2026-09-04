# Scout, Microsoft 365, and Obsidian Live Demo Design

**Status:** Approved in chat on 2026-09-04; awaiting written-spec review
**Scope:** Extend the existing deterministic Executive Time Management Copilot prototype without weakening `INV-1` through `INV-6`.

## Objective

Demonstrate the three MVP scheduling scenarios through a real Microsoft Teams intake path, Scout-authenticated Microsoft 365 context, a calendar view for two aliased executives, and an Obsidian vault that exposes the system's three memory layers. The copilot continues to recommend and draft only; the EA remains the decision-maker.

The prototype must preserve the existing offline suite. Real Microsoft 365 access is an opt-in demonstration path and must not become a prerequisite for `pytest`.

## Fixed Decisions

1. The only visible executive identities are `Exec A` and `Exec B`. Names, UPNs, and email addresses never appear in the browser, Obsidian, screenshots, videos, ordinary logs, or committed fixtures.
2. Actual mailbox mappings live only in an ignored local file. The signed-in user's UPN is discovered through Scout and is never committed.
3. A live test calendar item is always an unsent draft whose subject begins with `[DEMO]`. The signed-in user is its only explicit attendee.
4. A draft may be requested only after the corresponding EA approval event is durably recorded. Scout must pass `draft: true` literally; the agent cannot choose the flag.
5. No workflow accepts, declines, cancels, moves, updates, sends, or deletes a calendar event.
6. Obsidian is a privacy-filtered projection of governed stores, not a new source of truth.
7. Graph-derived preferences are evidence or candidate rules. They influence ranking only after the existing preference-approval path creates a versioned `ApprovedPreference`.

## Approaches Considered

### 1. Scout relay plus local EA Copilot MCP server — selected

Scout already owns the authenticated Microsoft 365 session and personal Teams relay. A repository-owned Scout skill coordinates Scout's Graph/Work IQ tools with a local stdio MCP server backed by the existing Python orchestrator. This avoids a new Entra application while preserving the deterministic core and fake adapters.

Trade-off: Scout is the client, so the integration is a governed handshake rather than the Python process directly invoking Scout tools. The handshake is made observable and testable with approval receipts, one-time draft commands, fixed tool arguments, and an append-only result record.

### 2. Windows UI automation around Scout

This could demonstrate the happy path quickly but would make the integration depend on window focus, layout, and natural-language responses. It is retained only for driving and recording the final demo, not as the application integration boundary.

### 3. Direct Microsoft Graph adapter

This would provide the strongest programmatic boundary but requires app registration, OAuth configuration, or copied credentials. It conflicts with the explicit no-app-registration requirement and is rejected.

## Architecture

```text
Personal Teams chat with Microsoft Scout
        |
        v
Scout EA skill -- Scout-authenticated Graph/Work IQ reads
        |                         |
        | structured intake      | privacy-filtered evidence
        +------------+------------+
                     v
          Local EA Copilot MCP server
                     |
                     v
      Existing deterministic orchestrator
       |          |            |
       |          |            +--> three-layer vault projection
       |          +--> browser calendar/workbench
       +--> append-only audit and approval gate
                     |
          approved one-time draft command
                     |
                     v
  Scout workiq_create_event(draft=true, attendee=self)
                     |
                     v
       draft result recorded; invitation never sent
```

### Repository-owned Scout integration

The integration package lives under `integrations/scout/` and contains:

- an EA scheduling skill that constrains the tool sequence;
- the custom stdio MCP registration template;
- a local installation/preflight script that detects Scout configuration without copying tokens;
- example Teams prompts using only `Exec A` and `Exec B`.

The MCP server exposes narrow tools for structured intake, context attachment, recommendation retrieval, EA decision recording, approved-draft preparation, draft-result recording, and demo-state inspection. It exposes no generic shell, Graph, or calendar-write tool.

Every Teams message is still wrapped as untrusted content at the EA Copilot boundary, even though Scout's relay is personal-scope. Language output may extract fields but cannot grant permissions, approve a recommendation, or select a calendar action.

### Two-phase live `M365Port` adapter

The live `M365Port` implementation spans the local server and the Scout skill because Scout, not Python, owns the authenticated Graph tool. Its sole write method remains `create_draft_event`; no second calendar mutation is added to the port.

After Agent 8 verifies the approval, `create_draft_event` persists an append-only `DraftCommand` containing a transaction ID and the fixed draft contract. The Scout skill consumes that command, calls `workiq_create_event`, and submits a `DraftCompletion` containing the returned event ID and link. The request remains approved but not draft-created while the command is pending. Only a valid, matching completion transitions it to `DraftCreated` and produces the domain `DraftEvent`.

The offline fake remains synchronous. The live adapter may return a pending receipt, so the data contract and API explicitly distinguish `pending_execution` from `draft_created`. A duplicate consume or completion returns the original transaction result and never repeats the Graph call. Tests cover the port's unchanged write surface, approval-before-command ordering, and command-before-completion ordering.

### Scout-authenticated Microsoft Graph context

Scout performs reads through the user's existing delegated session. It may retrieve:

- schedule/free-busy and working-hours information;
- related Teams and mail context;
- prior meetings and documents;
- preference signals such as recurring time choices or preparation patterns.

Scout passes only structured, source-referenced results to the local MCP server. Private event subjects and message bodies are not copied into the visible calendar or vault. Access failures become `DataLimitation` records; the live demo must never substitute fixtures while claiming a successful live read.

Graph observations enter Evidence History. Pattern detection can propose a `CandidateRule`, but request-time ranking reads only approved profile and policy versions.

### Alias and identity boundary

An ignored local mapping associates `Exec A` and `Exec B` with live mailbox identities. The mapping is loaded only by the live integration composition root. Responses and telemetry pass through an alias/redaction layer before reaching the browser, vault, logs, or recorder.

The signed-in user is resolved separately as `Demo User`. It is used as the organizer context and the sole explicit attendee of any live test draft. The event subject is generated by code as `[DEMO] Executive scheduling prototype`; neither the LLM nor Teams input controls the prefix.

## Three-Layer Agent Memory

The demo vault is a plain Markdown vault created under an ignored local runtime directory and opened in Obsidian. The exporter writes atomically and never reads notes back into the scheduling pipeline.

### Layer 1 — Current Session

Path shape: `01 Current Session/<request-id>.md`

Shows the aliased intake, sanitized context summary, current calendar window, hard constraints, candidate slots, score contributions, and active profile/policy versions. The note is replaced as the request advances and is cleared by demo reset.

### Layer 2 — Evidence History

Path shape: `02 Evidence History/<date>/<evidence-id>.md`

Shows append-only audit events, EA feedback, redacted Graph observations, candidate-rule formation, and provenance references. This layer is never read during recommendation generation. Corrections and observed patterns remain inert here.

### Layer 3 — Governed Memory

Path shape: `03 Governed Memory/<alias>/profile-v<version>.md`

Shows approved, versioned profile preferences and policies, including who approved them, their evidence references, and their effective version. Only this layer represents memory that may influence ranking. Approval creates a new note/version; rollback creates another version rather than mutating history.

Obsidian will be installed through the local Windows package manager if absent. Vault creation remains useful without the application because the output is ordinary Markdown.

## Governed Data Flow

1. The user sends Scout a personal Teams message requesting a meeting with `Exec A` and `Exec B`.
2. The Scout skill converts it to structured intake and asks its authenticated Microsoft 365 tools for delegated context.
3. The local MCP server validates aliases, wraps external text as untrusted, stores source-referenced evidence, and invokes the existing deterministic solver and ranker.
4. The browser displays two free/busy calendar lanes, protected/travel blocks, rejected constraints, and ranked candidates. It reveals no private subjects.
5. The Current Session note is projected to Obsidian; Graph observations and audit records appear only in Evidence History.
6. An EA decision is submitted through the workbench. The append-only audit record is committed before draft preparation can succeed.
7. Agent 8 invokes the two-phase live `M365Port.create_draft_event`; its local half emits a single-use draft command bound to the recommendation, approval ID, chosen slot, `[DEMO]` subject, self attendee, and `draft=true` contract.
8. Immediately before the real draft action, the demo pauses for explicit human confirmation. Automation must not click or answer this confirmation.
9. Scout calls `workiq_create_event` with `draft: true`. A missing or false value is a hard failure because Scout's underlying tool otherwise defaults to sending invitations.
10. Scout returns the draft ID and web link as a matching completion. The local server records the result idempotently, transitions the request to `DraftCreated`, and states that the draft remains unsent.
11. Three consistent EA corrections create a candidate preference in Evidence History. Re-running the request proves the candidate is inert.
12. EA approval of the candidate creates a new Governed Memory profile version. Re-running the same request shows the learned preference and changed ranking; rollback is demonstrated as a new version.

## Calendar Workbench

The browser demo gains a weekly calendar board with lanes for `Exec A` and `Exec B`. It displays:

- working hours and free time;
- busy, protected, travel, and preparation blocks using category labels only;
- candidate slots aligned across lanes;
- the selected recommendation and score explanation;
- the approval receipt and unsent-draft status.

The board supports a deterministic fixture mode and an explicitly labelled `LIVE VIA SCOUT` mode. A failed live preflight cannot silently fall back to fixture data.

## Failure and Recovery Behavior

- **Scout or Teams disconnected:** fail the live preflight and leave the offline demo available.
- **Alias missing or ambiguous:** block the request before Graph access.
- **Calendar access denied:** retain the request, show an aliased data limitation, and do not fabricate availability.
- **Prompt injection in external text:** audit and ignore it while retaining safe metadata.
- **No matching approval:** issue no draft command and perform no calendar write.
- **Draft flag unsupported, missing, or false:** block the live write.
- **Duplicate execution:** reuse the command transaction ID and record one result; never blindly retry a calendar write.
- **Obsidian unavailable or vault write fails:** scheduling remains operational, the UI reports projection lag, and a bounded retry may refresh the projection.
- **Profile candidate rejected or deferred:** ranking remains byte-identical.

## Test Strategy

### Default offline gates

`pytest` remains credential-free and has zero skipped E2E tests. New deterministic coverage includes:

- alias redaction across API payloads, logs, vault notes, and recording fixtures;
- calendar-board data for `Exec A` and `Exec B`;
- all three memory layers and the one-way projection rule;
- Graph-derived evidence remaining inert before approval;
- candidate approval creating a new profile version and changing ranking;
- draft preparation failing without a recorded approval;
- the fixed `[DEMO]`, self-attendee, and literal `draft:true` command contract;
- duplicate-result idempotency and forbidden calendar operations;
- Teams-to-MCP transcript fixtures for all three scenarios.

The existing invariant, Ruff, mypy, documentation, and browser E2E gates remain mandatory.

### Opt-in live validation

Live checks run through a separate `tools/run_live_scout_e2e.py` entry point so normal `pytest` never skips or requires credentials. The script:

1. verifies Scout and Teams relay health;
2. resolves the signed-in user without printing the UPN;
3. validates both alias mappings and delegated read access;
4. submits the Teams intake and correlates it with the local request ID;
5. checks that the calendar view is labelled live and contains no private subjects;
6. verifies the three vault layers and governed reranking;
7. stops before the real draft unless the human confirms in the workbench;
8. after confirmation, asserts the Scout tool call used `draft:true`, `[DEMO]`, and only the signed-in user as attendee;
9. verifies the result is an unsent draft and that no update/send/move/delete operation occurred.

## Demonstration and Recording

The complete recording is a Windows desktop capture, not merely a browser video. It shows:

1. the request for `Exec A` and `Exec B` entering through the personal Microsoft Scout Teams chat;
2. the browser's live two-calendar view and ranked slots;
3. Obsidian's Current Session, Evidence History, and Governed Memory folders;
4. the blocked pre-approval draft attempt and recorded EA approval;
5. the explicit human confirmation and resulting `[DEMO]` unsent draft;
6. three feedback events, an inert candidate, preference approval, profile version change, and reranked result;
7. final automated E2E and quality-gate evidence.

The recorder uses a dedicated demo window arrangement and a redaction preflight. Recording stops immediately if an email address, real name, token, or private subject is detected on a captured surface. The output is written under `artifacts/` and verified for video stream, duration, dimensions, and the presence of all scenario completion markers.

## Acceptance Criteria

The extension is complete only when all of the following are objectively green:

1. Existing `INV-1` through `INV-6` tests remain unchanged and pass.
2. Default `pytest`, Ruff, mypy, documentation consistency, and browser E2E checks pass with no E2E skips.
3. Visible artifacts contain `Exec A` and `Exec B` and contain no configured mailbox identity.
4. A Teams/Scout intake produces a correlated local request and real delegated calendar result or an honest `DataLimitation`.
5. The browser visibly shows both executive calendar lanes and candidate alignment.
6. Obsidian visibly shows all three memory layers with their distinct read/write rules.
7. Candidate evidence does not affect ranking; its approved governed profile version does.
8. No draft command exists before approval, and the live command is fixed to `[DEMO]`, self attendee, and `draft:true`.
9. No invitation is sent and no event is accepted, declined, cancelled, moved, updated, or deleted.
10. The complete desktop video demonstrates all three scenarios and passes automated media verification.

## Out of Scope

- Production deployment or tenant-wide rollout.
- A new Entra application registration or copied OAuth credentials.
- Group/channel Teams installation; Scout's personal chat is the intake surface.
- Autonomous approval or autonomous sending.
- Editing Obsidian notes to change agent behavior.
- Exposing private calendar subjects or raw mailbox content.
