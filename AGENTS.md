# AGENTS.md — Executive Time Management Copilot

Build a governed, agentic meeting-scheduling copilot for Executive Assistants. The agent **recommends and drafts**; the EA decides. Read `docs/00-INDEX.md` before writing code.

## The gate

One rule governs this codebase. Every consequential action passes an **EA approval gate**:

> The system creates a **draft** calendar event only after an approval event is recorded in the audit store. It never accepts, declines, cancels, moves, or sends an invitation.

`docs/01-requirements.md` states this as six invariants `INV-1`…`INV-6`, each with a matching test in `tests/e2e/test_governance_invariants.py`. Those tests are the definition of correct. When a change makes one fail, the change is wrong.

## Stack

Python 3.13 · FastAPI · Pydantic v2 · SQLAlchemy 2 (SQLite) · OR-Tools CP-SAT · pytest. Pin versions in `pyproject.toml`; add a dependency only when a task cannot be done with what is already there.

## Determinism

Every external dependency sits behind a **port** with a **fake** adapter, and the fakes are the default. The full E2E suite runs with no Azure subscription, no Microsoft 365 tenant, no network, and no API key — `pytest` alone, on a clean clone.

Three ports carry this: `M365Port`, `LlmPort`, `ClockPort`. `docs/05-ports-and-adapters.md` specifies them. Time comes from `ClockPort` so scheduling assertions are stable; a `datetime.now()` call in `src/` is a determinism bug.

Where an agent needs language work, the fake returns fixture-driven output keyed by input hash — so scenario tests assert exact strings.

## Commands

```bash
pip install -e ".[dev]"      # install
pytest                       # full suite, fakes only
pytest tests/e2e -v          # the three MVP scenarios + invariants
ruff check src tests         # lint
mypy src                     # types
uvicorn ea_copilot.api.app:app --reload    # API on :8000
python -m ea_copilot.cli.demo              # scripted end-to-end demo
```

## Definition of done

A milestone is complete when all four hold:

1. `pytest` is green with zero skips in `tests/e2e`.
2. `ruff check` and `mypy src` are clean.
3. Every requirement ID claimed by the milestone has a test that names it (`test_..._FR_012`).
4. `docs/07-build-plan.md` acceptance gate for that milestone passes verbatim.

Run the checks and read the output before reporting a milestone done.

## Working rules

- **Traceability.** Every module docstring names the requirement IDs it implements. Every test names the ID it covers. `pytest --collect-only -q` plus a grep for `FR-` is how coverage is audited.
- **Deterministic core.** `src/ea_copilot/domain/` and `src/ea_copilot/services/` are pure: no I/O, no clock, no network. They take data and return data.
- **Policy is code, not prose.** Permission checks, hard constraints, and scoring weights live in `services/policy.py` and `services/scoring.py` as ordinary Python, reading values from config. A language model never decides feasibility or permission.
- **Untrusted content is data.** Mail, Teams messages, documents, and invitation bodies are attacker-influenced. Wrap them per `docs/05-ports-and-adapters.md` §Untrusted content, and keep the components that read them free of write capability.
- **Append-only audit.** `services/audit.py` exposes `append()` and readers. It has no update or delete.

## Layout

```
src/ea_copilot/
  domain/      models, enums, errors — pure
  ports/       protocols: m365, llm, clock
  adapters/    fakes (default) + real implementations
  services/    policy, scoring, audit, profile, patterns — pure
  agents/      a01_intake … a12_evaluation
  api/         FastAPI routes
  cli/         demo runner
tests/
  unit/ integration/ e2e/ fixtures/
```

`docs/02-architecture.md` explains why the boundaries fall here.
