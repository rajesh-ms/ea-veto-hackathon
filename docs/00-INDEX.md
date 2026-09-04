# 00 — Index

Specification set for the Executive Time Management Copilot. Written for a coding agent: every requirement carries a stable ID, every ID has a test.

## Reading order

| # | Document | Read it to answer |
|---|---|---|
| 1 | [`01-requirements.md`](01-requirements.md) | What must be true. Functional requirements, non-functional requirements, and the six invariants. |
| 2 | [`02-architecture.md`](02-architecture.md) | Why the module boundaries fall where they do. Two planes, the gate, the deterministic core. |
| 3 | [`03-data-contracts.md`](03-data-contracts.md) | Exact Pydantic models and the request state machine. Copy these signatures. |
| 4 | [`04-component-specs.md`](04-component-specs.md) | Per-agent contract: inputs, outputs, permitted effects. One section per agent 1–12. |
| 5 | [`05-ports-and-adapters.md`](05-ports-and-adapters.md) | The three ports, their fakes, and how untrusted content is handled. |
| 6 | [`06-e2e-test-cases.md`](06-e2e-test-cases.md) | The acceptance suite. Given/When/Then with exact assertions. |
| 7 | [`07-build-plan.md`](07-build-plan.md) | Milestone order and the gate that closes each one. |

Start at `07-build-plan.md` Milestone 0 once you have read 1–5.

## Rules that outrank everything else

1. **The gate holds.** No calendar write without a recorded approval event. `INV-1`.
2. **Draft is terminal.** `create_draft_event` is the only write on `M365Port`. `INV-2`.
3. **Learning proposes.** A candidate rule changes no recommendation until approved. `INV-3`.
4. **Fakes are the default.** `pytest` passes on a clean clone with no network.
5. **Traceability.** Module docstrings and test names carry requirement IDs.

## Scope

Three MVP scenarios, in build order:

- **S1** Qualified single-executive scheduling
- **S2** Multi-executive strategic scheduling
- **S3** EA feedback-to-preference learning

Out of scope for the MVP: autonomous accept/decline/cancel/reschedule/send, silent preference changes, travel booking, CRM/HR/ERP integration, cross-company assistant negotiation, model fine-tuning on executive data.

## Diagrams

| File | Shows |
|---|---|
| [`diagrams/01-functional-architecture.png`](diagrams/01-functional-architecture.png) | Twelve components, two planes, the gate, governed stores |
| [`diagrams/02-reference-architecture.png`](diagrams/02-reference-architecture.png) | Azure service mapping and the approval boundary |
| [`diagrams/03-request-lifecycle.png`](diagrams/03-request-lifecycle.png) | Fourteen-message sequence for one request |
| [`diagrams/04-governed-learning.png`](diagrams/04-governed-learning.png) | Feedback → evidence → candidate → approval → versioned rule |
| [`diagrams/05-integration-topology.png`](diagrams/05-integration-topology.png) | Local prototype today, Foundry target state |

`Executive-Time-Management-Copilot-Architecture-MVP.docx` is the human review copy. The markdown in this folder is authoritative for the build.

`brainstorm/executive-timemgmt-copilot.md` is the originating brief — background, superseded by these specs where they differ.
