"""Graph evidence governance tests for FR-905 and INV-3."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from ea_copilot.bootstrap import build_runtime
from ea_copilot.domain.live_models import GraphPreferenceEvidence
from ea_copilot.domain.models import Requester, SourceReference

ROOT = Path(__file__).parents[2]
EXECUTIVE = "cfo@humana-demo.com"
EA = "ea@humana-demo.com"
REQUESTER = Requester(entra_object_id="requester@humana-demo.com", display_name="Alex Chen")


def graph_observation(index: int) -> GraphPreferenceEvidence:
    observed_at = datetime(2026, 9, 14, 13, 0, tzinfo=UTC) - timedelta(days=index)
    return GraphPreferenceEvidence(
        evidence_id=f"GRAPH-EVIDENCE-{index}",
        executive_upn=EXECUTIVE,
        dimension="time_of_day",
        value="tuesday_after_12",
        source=SourceReference(
            source_id=f"event-source-{index}",
            source_type="event",
            title="Recurring calendar choice",
            url=None,
            retrieved_at=observed_at,
        ),
        confidence=0.9,
        observed_at=observed_at,
    )


def test_FR_905_graph_evidence_is_not_read_during_request_and_candidate_is_inert_INV_3() -> None:
    runtime = build_runtime(ROOT)
    for index in range(3):
        runtime.live_evidence.append(graph_observation(index))

    request = runtime.orchestrator.submit(
        "Meet Marcus for 30 minutes Tuesday about the Q4 forecast decision.", REQUESTER
    )
    baseline = runtime.orchestrator.build_recommendation(request.request_id)
    assert runtime.live_evidence.read_log == []

    candidate = runtime.pattern.detect_graph(EXECUTIVE)[0]
    assert candidate.evidence.feedback_ids == []
    assert candidate.evidence.graph_evidence_ids == [
        "GRAPH-EVIDENCE-0",
        "GRAPH-EVIDENCE-1",
        "GRAPH-EVIDENCE-2",
    ]
    assert candidate.rule_expression == {
        "kind": "avoid_before",
        "day": "tuesday",
        "hour": 12,
    }

    pending = runtime.orchestrator.build_recommendation(request.request_id)
    assert [option.model_dump_json() for option in pending.options] == [
        option.model_dump_json() for option in baseline.options
    ]
    assert pending.profile_version == "v1"

    runtime.orchestrator.decide_candidate(candidate.candidate_id, EA, "approve")
    learned = runtime.orchestrator.build_recommendation(request.request_id)
    assert learned.profile_version == "v2"
    assert [option.slot for option in learned.options] != [
        option.slot for option in baseline.options
    ]
    assert learned.options[0].preferences_applied
