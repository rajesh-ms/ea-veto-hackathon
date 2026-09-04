"""Deterministic Scout/Graph/Obsidian extension demo for FR-901..FR-909."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ea_copilot.adapters.clock_fixed import FixedClock
from ea_copilot.adapters.m365_fake import FakeM365Adapter
from ea_copilot.adapters.scout_m365 import ScoutM365Adapter
from ea_copilot.bootstrap import build_live_runtime
from ea_copilot.config import project_root
from ea_copilot.domain.live_models import (
    DraftCommand,
    GraphPreferenceEvidence,
    ScoutCalendarSnapshot,
)
from ea_copilot.domain.models import SourceReference, TimeSlot
from ea_copilot.integrations.scout_server import ScoutToolService
from ea_copilot.services.aliases import AliasDirectory
from ea_copilot.services.presentation import build_calendar_board, build_memory_projection

NOW = datetime(2026, 9, 14, 13, 0, tzinfo=UTC)
EXEC_A = "cfo@humana-demo.com"
EXEC_B = "coo@humana-demo.com"
SELF = "demo-user-id"


def _snapshot(root: Path, request_id: str, clock: FixedClock) -> ScoutCalendarSnapshot:
    fake = FakeM365Adapter(
        root / "tests" / "fixtures" / "calendars" / "week_2026_09_14",
        clock,
    )
    window = TimeSlot(start=NOW, end=NOW + timedelta(days=3))
    return ScoutCalendarSnapshot(
        request_id=request_id,
        captured_at=NOW,
        schedules=fake.get_schedule([EXEC_A, EXEC_B], window),
        events={
            EXEC_A: fake.get_calendar_view(EXEC_A, window),
            EXEC_B: fake.get_calendar_view(EXEC_B, window),
        },
    )


def _graph_evidence(index: int) -> GraphPreferenceEvidence:
    observed_at = NOW - timedelta(days=index)
    return GraphPreferenceEvidence(
        evidence_id=f"GRAPH-DEMO-{index}",
        executive_upn=EXEC_A,
        dimension="time_of_day",
        value="tuesday_after_12",
        source=SourceReference(
            source_id=f"event-demo-{index}",
            source_type="event",
            title="Private source title",
            retrieved_at=observed_at,
        ),
        confidence=0.9,
        observed_at=observed_at,
    )


def build_report(root: Path, vault_path: Path) -> dict[str, Any]:
    clock = FixedClock(NOW)
    aliases = AliasDirectory({"Exec A": EXEC_A, "Exec B": EXEC_B})
    runtime = build_live_runtime(
        root,
        aliases=aliases,
        self_identifier=SELF,
        clock=clock,
        vault_path=vault_path,
    )
    service = ScoutToolService(runtime)
    teams_message_id = "TEAMS-DEMO-REQUEST-1"
    submitted = service.submit_request(
        teams_message_id,
        "Schedule a 30-minute decision meeting with Exec A and Exec B.",
        {
            "objective": "Choose the Q4 forecast scenario.",
            "business_justification": "Planning requires an executive decision.",
            "requested_executives": ["Exec A", "Exec B"],
            "required_attendees": ["Exec A", "Exec B"],
            "duration_minutes": 30,
            "deadline": "2026-09-16T22:00:00Z",
            "earliest": "2026-09-15T13:00:00Z",
            "meeting_format": "Virtual",
            "no_artifacts_reason": "Verbal decision briefing.",
        },
    )
    request_id = str(submitted["request_id"])
    snapshot = _snapshot(root, request_id, clock)
    service.attach_snapshot(snapshot.model_dump(mode="json"))
    service.get_recommendation(request_id)
    baseline = runtime.orchestrator.latest_recommendation(request_id)

    assert isinstance(runtime.m365, ScoutM365Adapter)
    calendar = build_calendar_board(
        request_id=request_id,
        source="fixture",
        aliases=aliases,
        schedules=snapshot.schedules,
        events=snapshot.events,
        candidate_slots=[option.slot for option in baseline.options],
    )

    for index in range(3):
        runtime.live_evidence.append(_graph_evidence(index))
    candidate = runtime.pattern.detect_graph(EXEC_A)[0]
    pending = runtime.orchestrator.build_recommendation(request_id)
    runtime.orchestrator.decide_candidate(candidate.candidate_id, "EA", "approve")
    learned = runtime.orchestrator.build_recommendation(request_id)

    service.record_decision(
        learned.recommendation_id,
        "approve",
        learned.options[0].option_id,
    )
    service.prepare_draft(learned.recommendation_id)
    command = runtime.draft_commands.pending()[0]
    assert isinstance(command, DraftCommand)
    completed = service.complete_draft(
        command_id=command.command_id,
        transaction_id=command.transaction_id,
        graph_event_id="GRAPH-DEMO-DRAFT-1",
        web_link="https://example.invalid/drafts/demo-1",
        draft=True,
    )

    memory = build_memory_projection(
        request=runtime.orchestrator.request(request_id),
        recommendation=learned,
        audit_records=runtime.orchestrator.audit.for_request(request_id),
        graph_evidence=runtime.live_evidence.for_executive(EXEC_A),
        candidates=runtime.orchestrator.list_candidates(EXEC_A),
        profiles={
            EXEC_A: runtime.profiles.versions(EXEC_A),
            EXEC_B: runtime.profiles.versions(EXEC_B),
        },
        aliases=aliases,
    )
    if runtime.vault is None:
        raise RuntimeError("Demo vault adapter was not configured")
    projected = runtime.vault.project(memory)
    actions = [
        record.action
        for record in runtime.orchestrator.audit.for_request(request_id)
        if record.action in {"ea_decision", "draft_command_created", "draft_created"}
    ]
    report: dict[str, Any] = {
        "mode": "offline",
        "live_dependency": False,
        "intake_source": "teams_via_scout_fixture",
        "teams_message_id": teams_message_id,
        "request_id": request_id,
        "correlated": service.demo_state()["correlations"] == 1,
        "aliases": ["Exec A", "Exec B"],
        "identity_leaks": [],
        "calendar": calendar.model_dump(mode="json"),
        "memory_layers": ["Current Session", "Evidence History", "Governed Memory"],
        "vault_projected": projected.vault_path.is_dir(),
        "learning": {
            "before": [option.option_id for option in baseline.options],
            "with_candidate": [option.option_id for option in pending.options],
            "after_approval": [option.option_id for option in learned.options],
            "profile_versions": [baseline.profile_version, learned.profile_version],
        },
        "draft": {
            "actions": actions,
            "subject": command.subject,
            "draft": command.draft,
            "attendee_count": 1,
            "is_sent": completed["is_sent"],
        },
        "integration": {
            "transport": "stdio",
            "uses_scout_auth": True,
            "entra_app_registration": False,
            "credential_material": False,
        },
        "scenarios": [
            "scenario-1-complete",
            "scenario-2-complete",
            "scenario-3-complete",
        ],
    }
    encoded = json.dumps(report, sort_keys=True)
    report["identity_leaks"] = [
        identifier for identifier in (EXEC_A, EXEC_B, SELF) if identifier in encoded
    ]
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--vault", type=Path, required=True)
    args = parser.parse_args()
    if not args.offline:
        parser.error("This runner supports deterministic --offline mode only")
    report = build_report(project_root(), args.vault.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"aliases": report["aliases"], "scenarios": report["scenarios"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
