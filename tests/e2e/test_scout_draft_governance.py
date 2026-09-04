"""Scout draft approval-command-completion governance for FR-906 and INV-1..INV-2."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ea_copilot.adapters.clock_fixed import FixedClock
from ea_copilot.adapters.m365_fake import FakeM365Adapter
from ea_copilot.adapters.scout_m365 import ScoutM365Adapter
from ea_copilot.bootstrap import build_live_runtime
from ea_copilot.domain.enums import EADecision, RequestStatus
from ea_copilot.domain.errors import ApprovalRequiredError
from ea_copilot.domain.live_models import DraftCommand, DraftCompletion, ScoutCalendarSnapshot
from ea_copilot.domain.models import Requester, TimeSlot
from ea_copilot.services.aliases import AliasDirectory

ROOT = Path(__file__).parents[2]
NOW = datetime(2026, 9, 14, 13, 0, tzinfo=UTC)
EXEC_A = "cfo@humana-demo.com"
EXEC_B = "coo@humana-demo.com"
SELF = "demo-user-id"
EA = "ea@humana-demo.com"


def live_runtime():  # type: ignore[no-untyped-def]
    clock = FixedClock(NOW)
    aliases = AliasDirectory({"Exec A": EXEC_A, "Exec B": EXEC_B})
    runtime = build_live_runtime(
        ROOT,
        aliases=aliases,
        self_identifier=SELF,
        clock=clock,
    )
    assert isinstance(runtime.m365, ScoutM365Adapter)
    fake = FakeM365Adapter(
        ROOT / "tests" / "fixtures" / "calendars" / "week_2026_09_14",
        clock,
    )
    window = TimeSlot(start=NOW, end=NOW + timedelta(days=3))
    runtime.m365.ingest(
        ScoutCalendarSnapshot(
            request_id="REQ-SNAPSHOT",
            captured_at=NOW,
            schedules=fake.get_schedule([EXEC_A, EXEC_B], window),
            events={
                EXEC_A: fake.get_calendar_view(EXEC_A, window),
                EXEC_B: fake.get_calendar_view(EXEC_B, window),
            },
        )
    )
    return runtime


def recommendation(runtime):  # type: ignore[no-untyped-def]
    request = runtime.orchestrator.submit(
        "Meet Marcus for 30 minutes Tuesday about the Q4 forecast decision.",
        Requester(entra_object_id="requester@humana-demo.com", display_name="Alex Chen"),
    )
    return request, runtime.orchestrator.build_recommendation(request.request_id)


def test_FR_906_INV_1_no_approval_means_no_scout_draft_command() -> None:
    runtime = live_runtime()
    _, packet = recommendation(runtime)

    with pytest.raises(ApprovalRequiredError):
        runtime.orchestrator.create_draft(packet.recommendation_id, EA)
    assert runtime.draft_commands.all() == []


def test_FR_906_approval_command_completion_is_ordered_draft_only_and_idempotent() -> None:
    runtime = live_runtime()
    request, packet = recommendation(runtime)
    approval = runtime.orchestrator.decide(
        packet.recommendation_id,
        EA,
        EADecision.APPROVE,
        chosen_option_id=packet.options[0].option_id,
    )

    submission = runtime.orchestrator.create_draft(packet.recommendation_id, EA)
    assert isinstance(submission, DraftCommand)
    assert submission.approval_id == approval.approval_id
    assert submission.subject == "[DEMO] Executive scheduling prototype"
    assert submission.attendee == SELF
    assert submission.draft is True
    assert runtime.orchestrator.request(request.request_id).status is RequestStatus.DRAFT_PENDING
    draft_records = [
        record.action
        for record in runtime.orchestrator.audit.for_request(request.request_id)
        if record.action.startswith("draft")
    ]
    assert draft_records == ["draft_command_created"]

    completion = DraftCompletion(
        command_id=submission.command_id,
        transaction_id=submission.transaction_id,
        graph_event_id="GRAPH-DRAFT-LIVE-1",
        web_link="https://example.invalid/drafts/live-1",
        draft=True,
        completed_at=NOW + timedelta(seconds=1),
    )
    event = runtime.orchestrator.complete_draft(completion)
    duplicate = runtime.orchestrator.complete_draft(completion)

    assert duplicate == event
    assert event.approval_id == approval.approval_id
    assert event.is_sent is False
    assert runtime.orchestrator.request(request.request_id).status is RequestStatus.DRAFT_CREATED
    draft_actions = [
        record.action
        for record in runtime.orchestrator.audit.for_request(request.request_id)
        if record.action in {"ea_decision", "draft_command_created", "draft_created"}
    ]
    assert draft_actions == ["ea_decision", "draft_command_created", "draft_created"]


def test_INV_2_scout_bridge_adds_no_second_m365_write_method() -> None:
    from ea_copilot.ports.m365 import M365Port

    prefixes = ("create", "update", "delete", "send", "accept", "decline", "cancel", "move")
    assert {
        name for name in M365Port.__protocol_attrs__ if name.startswith(prefixes)
    } == {"create_draft_event"}
