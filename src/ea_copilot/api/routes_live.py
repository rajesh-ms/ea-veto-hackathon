"""Aliased live calendar, memory, and Scout bridge routes for FR-902..FR-908."""

from __future__ import annotations

from fastapi import APIRouter

from ea_copilot.adapters.scout_m365 import ScoutM365Adapter
from ea_copilot.api.dependencies import RuntimeDependency
from ea_copilot.domain.live_models import (
    CalendarBoard,
    DraftCompletion,
    MemoryProjection,
    ScoutCalendarSnapshot,
)
from ea_copilot.domain.models import DraftEvent, TimeSlot
from ea_copilot.services.aliases import AliasDirectory
from ea_copilot.services.presentation import build_calendar_board, build_memory_projection

router = APIRouter(prefix="/live", tags=["Scout live demo"])


def _aliases(runtime: RuntimeDependency) -> AliasDirectory:
    return runtime.aliases or AliasDirectory(
        {
            "Exec A": "cfo@humana-demo.com",
            "Exec B": "coo@humana-demo.com",
        }
    )


@router.get("/status")
def live_status(runtime: RuntimeDependency) -> dict[str, object]:
    aliases = _aliases(runtime)
    return {
        "configured": runtime.live_mode,
        "source": "live_via_scout" if runtime.live_mode else "fixture",
        "aliases": list(aliases.aliases),
        "scout": "connected" if runtime.live_mode else "integration available",
    }


@router.get("/requests/{request_id}/calendar")
def calendar_board(request_id: str, runtime: RuntimeDependency) -> CalendarBoard:
    aliases = _aliases(runtime)
    request = runtime.orchestrator.request(request_id)
    packet = runtime.orchestrator.latest_recommendation(request_id)
    identifiers = [aliases.resolve(alias) for alias in aliases.aliases]
    window = TimeSlot(
        start=request.earliest or runtime.clock.now(),
        end=request.deadline or runtime.clock.now(),
    )
    schedules = runtime.m365.get_schedule(identifiers, window)
    events = {
        identifier: runtime.m365.get_calendar_view(identifier, window)
        for identifier in identifiers
    }
    return build_calendar_board(
        request_id=request_id,
        source="live_via_scout" if runtime.live_mode else "fixture",
        aliases=aliases,
        schedules=schedules,
        events=events,
        candidate_slots=[option.slot for option in packet.options],
    )


@router.get("/requests/{request_id}/memory")
def memory_projection(request_id: str, runtime: RuntimeDependency) -> MemoryProjection:
    aliases = _aliases(runtime)
    identifiers = [aliases.resolve(alias) for alias in aliases.aliases]
    projection = build_memory_projection(
        request=runtime.orchestrator.request(request_id),
        recommendation=runtime.orchestrator.latest_recommendation(request_id),
        audit_records=runtime.orchestrator.audit.for_request(request_id),
        graph_evidence=[
            evidence
            for identifier in identifiers
            for evidence in runtime.live_evidence.for_executive(identifier)
        ],
        candidates=[
            candidate
            for identifier in identifiers
            for candidate in runtime.orchestrator.list_candidates(identifier)
        ],
        profiles={
            identifier: runtime.profiles.versions(identifier) for identifier in identifiers
        },
        aliases=aliases,
    )
    if runtime.vault is not None:
        runtime.vault.project(projection)
    return projection


@router.post("/snapshots")
def attach_snapshot(
    body: ScoutCalendarSnapshot,
    runtime: RuntimeDependency,
) -> dict[str, object]:
    if not isinstance(runtime.m365, ScoutM365Adapter):
        raise ValueError("Snapshot ingestion requires live Scout mode")
    runtime.m365.ingest(body)
    return {
        "request_id": body.request_id,
        "source": "live_via_scout",
        "schedule_count": len(body.schedules),
        "limitation_count": len(body.limitations),
    }


@router.post("/drafts/{command_id}/complete")
def complete_draft(
    command_id: str,
    body: DraftCompletion,
    runtime: RuntimeDependency,
) -> DraftEvent:
    if body.command_id != command_id:
        raise ValueError("Draft completion does not match route command")
    return runtime.orchestrator.complete_draft(body)
