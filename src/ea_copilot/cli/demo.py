"""Three-scenario leadership walkthrough for AC-S1-1..5, AC-S2-1..5, and AC-S3-1..6."""

from __future__ import annotations

import argparse
import json
from zoneinfo import ZoneInfo

from ea_copilot.adapters.m365_fake import FakeM365Adapter
from ea_copilot.bootstrap import ApplicationRuntime, build_runtime
from ea_copilot.config import project_root
from ea_copilot.domain.enums import EADecision
from ea_copilot.domain.errors import ApprovalRequiredError
from ea_copilot.domain.models import DraftEvent, FeedbackEvent, Requester

REQUESTER = Requester(
    entra_object_id="requester@humana-demo.com",
    display_name="Alex Chen",
)
EA = "ea@humana-demo.com"
CENTRAL = ZoneInfo("America/Chicago")


def _runtime() -> ApplicationRuntime:
    return build_runtime(project_root())


def scenario_one() -> None:
    runtime = _runtime()
    app = runtime.orchestrator
    request = app.submit("Can I get 30 minutes with Marcus this week?", REQUESTER)
    qualification = app.qualification_for(request.request_id)
    print(f"S1 · NeedsInfo: {', '.join(qualification.missing_fields)}")
    request = app.answer(
        request.request_id,
        {
            "objective": "Choose the Q4 forecast scenario.",
            "business_justification": "Finance needs a decision before planning closes.",
            "deadline": "2026-09-16T22:00:00Z",
        },
    )
    packet = app.build_recommendation(request.request_id)
    print(f"S1 · Qualified · {len(app.context_for(request.request_id).items)} sourced items")
    print(f"S1 · {len(packet.options)} ranked options · {packet.priority.tier.value}")
    try:
        app.create_draft(packet.recommendation_id, EA)
    except ApprovalRequiredError:
        print("S1 · Gate held · zero writes before approval")
    else:
        raise AssertionError("Draft succeeded without approval")
    approval = app.decide(
        packet.recommendation_id,
        EA,
        EADecision.APPROVE,
        chosen_option_id=packet.options[0].option_id,
    )
    draft = app.create_draft(packet.recommendation_id, EA)
    assert isinstance(draft, DraftEvent)
    assert draft.approval_id == approval.approval_id and draft.is_sent is False
    print(f"S1 COMPLETE · {draft.draft_id} created unsent")


def scenario_two() -> None:
    runtime = _runtime()
    app = runtime.orchestrator
    request = app.submit(
        "Schedule a 45 minute strategic operating-plan decision with Dana, Marcus, "
        "and Priya before Friday.",
        REQUESTER,
    )
    packet = app.build_recommendation(request.request_id)
    feasible = app.feasible_for(request.request_id)
    assert len(feasible.evaluated_executives) == 3
    assert any(option.trade_offs for option in packet.options)
    chosen = next(option for option in packet.options if option.trade_offs)
    affected = chosen.trade_offs[0].affected_event_id
    app.decide(
        packet.recommendation_id,
        EA,
        EADecision.APPROVE,
        chosen_option_id=chosen.option_id,
    )
    draft = app.create_draft(packet.recommendation_id, EA)
    assert isinstance(draft, DraftEvent)
    assert isinstance(runtime.m365, FakeM365Adapter)
    assert affected is None or affected not in str(runtime.m365.write_log)
    print(
        f"S2 · {len(feasible.evaluated_executives)} calendars · "
        f"{len(feasible.blocked)} blocked starts"
    )
    print(f"S2 COMPLETE · {draft.draft_id} only; affected commitment was not moved")


def _seed_feedback(runtime: ApplicationRuntime) -> None:
    path = project_root() / "tests" / "fixtures" / "feedback" / "cfo_tuesday_pattern.json"
    for value in json.loads(path.read_text(encoding="utf-8")):
        runtime.evidence.append(FeedbackEvent.model_validate(value))


def scenario_three() -> None:
    runtime = _runtime()
    app = runtime.orchestrator
    request = app.submit(
        "Meet Marcus for 30 minutes Tuesday about the Q4 forecast decision.",
        REQUESTER,
    )
    baseline = app.build_recommendation(request.request_id)
    baseline_hour = baseline.options[0].slot.start.astimezone(CENTRAL).hour
    _seed_feedback(runtime)
    candidate = app.detect_patterns("cfo@humana-demo.com")[0]
    pending = app.build_recommendation(request.request_id)
    assert [option.option_id for option in pending.options] == [
        option.option_id for option in baseline.options
    ]
    preference = app.decide_candidate(candidate.candidate_id, EA, "approve")
    assert preference is not None
    learned = app.build_recommendation(request.request_id)
    learned_hour = learned.options[0].slot.start.astimezone(CENTRAL).hour
    assert baseline_hour < 12 <= learned_hour
    assert learned.profile_version == "v2"
    print(
        f"S3 · Candidate proposed from {candidate.evidence.occurrences} corrections · still inert"
    )
    print(f"S3 · Before {baseline_hour:02d}:00 / v1 -> after {learned_hour:02d}:00 / v2")
    print("S3 COMPLETE · approved preference changed the next recommendation")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the governed scheduling prototype demo")
    parser.add_argument(
        "--verify", action="store_true", help="fail fast if a scenario invariant breaks"
    )
    parser.parse_args()
    print("Executive Time Management Copilot · deterministic offline demo")
    scenario_one()
    scenario_two()
    scenario_three()
    print("ALL THREE SCENARIOS COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
