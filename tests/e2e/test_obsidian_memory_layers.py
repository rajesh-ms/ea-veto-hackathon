"""Three-layer governed memory projection for FR-902, FR-904, and FR-905."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from ea_copilot.adapters.obsidian_vault import ObsidianVaultAdapter
from ea_copilot.bootstrap import build_runtime
from ea_copilot.domain.live_models import GraphPreferenceEvidence
from ea_copilot.domain.models import Requester, SourceReference
from ea_copilot.services.aliases import AliasDirectory
from ea_copilot.services.presentation import build_memory_projection

ROOT = Path(__file__).parents[2]
EXEC_A = "cfo@humana-demo.com"
EXEC_B = "coo@humana-demo.com"
EA = "ea@humana-demo.com"


def test_FR_904_obsidian_shows_current_evidence_and_governed_memory_without_identity_leaks(
    tmp_path: Path,
) -> None:
    runtime = build_runtime(ROOT)
    aliases = AliasDirectory({"Exec A": EXEC_A, "Exec B": EXEC_B})
    request = runtime.orchestrator.submit(
        "Meet Marcus for 30 minutes Tuesday about the Q4 forecast decision.",
        Requester(entra_object_id="requester@humana-demo.com", display_name="Alex Chen"),
    )
    baseline = runtime.orchestrator.build_recommendation(request.request_id)
    for index in range(3):
        observed_at = datetime(2026, 9, 14, 13, 0, tzinfo=UTC) - timedelta(days=index)
        runtime.live_evidence.append(
            GraphPreferenceEvidence(
                evidence_id=f"GRAPH-MEMORY-{index}",
                executive_upn=EXEC_A,
                dimension="time_of_day",
                value="tuesday_after_12",
                source=SourceReference(
                    source_id=f"event-memory-{index}",
                    source_type="event",
                    title="Private title must not be copied",
                    retrieved_at=observed_at,
                ),
                confidence=0.9,
                observed_at=observed_at,
            )
        )
    candidate = runtime.pattern.detect_graph(EXEC_A)[0]
    runtime.orchestrator.decide_candidate(candidate.candidate_id, EA, "approve")
    learned = runtime.orchestrator.build_recommendation(request.request_id)
    assert baseline.profile_version == "v1"
    assert learned.profile_version == "v2"

    memory = build_memory_projection(
        request=runtime.orchestrator.request(request.request_id),
        recommendation=learned,
        audit_records=runtime.orchestrator.audit.for_request(request.request_id),
        graph_evidence=runtime.live_evidence.for_executive(EXEC_A),
        candidates=runtime.orchestrator.list_candidates(EXEC_A),
        profiles={
            EXEC_A: runtime.profiles.versions(EXEC_A),
            EXEC_B: runtime.profiles.versions(EXEC_B),
        },
        aliases=aliases,
    )
    result = ObsidianVaultAdapter(tmp_path / "demo-vault").project(memory)

    assert result.layers == ["Current Session", "Evidence History", "Governed Memory"]
    notes = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(result.vault_path.rglob("*.md"))
    )
    assert "Exec A" in notes
    assert "Exec B" in notes
    assert "GRAPH-MEMORY-0" in notes
    assert candidate.candidate_id in notes
    assert "profile v1" in notes
    assert "profile v2" in notes
    assert "Private title must not be copied" not in notes
    assert EXEC_A not in notes
    assert EXEC_B not in notes
    assert EA not in notes
