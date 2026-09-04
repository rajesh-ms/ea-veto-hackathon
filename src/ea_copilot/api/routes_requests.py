"""Request, recommendation, draft, and audit routes for FR-101, FR-104, FR-601, FR-604, FR-803."""

from __future__ import annotations

from fastapi import APIRouter, status

from ea_copilot.api.dependencies import RuntimeDependency
from ea_copilot.api.schemas import AnswersRequest, DraftRequest, SubmitRequest
from ea_copilot.bootstrap import ApplicationRuntime
from ea_copilot.domain.enums import RequestStatus
from ea_copilot.domain.live_models import DraftCommand
from ea_copilot.domain.models import AuditRecord, DraftEvent, RecommendationView

router = APIRouter()


def _request_response(runtime: ApplicationRuntime, request_id: str) -> dict[str, object]:
    request = runtime.orchestrator.request(request_id)
    return {
        "request": request.model_dump(mode="json"),
        "qualification": runtime.orchestrator.qualification_for(request_id).model_dump(mode="json"),
    }


@router.post("/requests", status_code=status.HTTP_201_CREATED)
def submit_request(
    body: SubmitRequest,
    runtime: RuntimeDependency,
) -> dict[str, object]:
    request = runtime.orchestrator.submit(
        body.raw_text,
        body.requester,
        structured_fields=body.structured_fields,
    )
    return _request_response(runtime, request.request_id)


@router.post("/requests/{request_id}/answers")
def answer_request(
    request_id: str,
    body: AnswersRequest,
    runtime: RuntimeDependency,
) -> dict[str, object]:
    runtime.orchestrator.answer(request_id, body.answers)
    return _request_response(runtime, request_id)


@router.get("/requests/{request_id}/recommendation")
def recommendation(
    request_id: str,
    runtime: RuntimeDependency,
) -> RecommendationView:
    request = runtime.orchestrator.request(request_id)
    if request.status in {RequestStatus.QUALIFIED, RequestStatus.AWAITING_EA_REVIEW}:
        packet = runtime.orchestrator.build_recommendation(request_id)
    else:
        packet = runtime.orchestrator.latest_recommendation(request_id)
    return RecommendationView(
        packet=packet,
        context=runtime.orchestrator.context_for(request_id),
        feasible_set=runtime.orchestrator.feasible_for(request_id),
    )


@router.post("/requests/{request_id}/draft")
def create_draft(
    request_id: str,
    body: DraftRequest,
    runtime: RuntimeDependency,
) -> DraftEvent | DraftCommand:
    packet = runtime.orchestrator.recommendation(body.recommendation_id)
    if packet.request_id != request_id:
        raise ValueError("Recommendation does not belong to request")
    return runtime.orchestrator.create_draft(body.recommendation_id, body.actor)


@router.get("/requests/{request_id}/audit")
def request_audit(
    request_id: str,
    runtime: RuntimeDependency,
) -> list[AuditRecord]:
    return runtime.orchestrator.audit.for_request(request_id)
