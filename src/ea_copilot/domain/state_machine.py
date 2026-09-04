"""Explicit request lifecycle for FR-105, FR-106, FR-605, FR-607, and INV-1."""

from __future__ import annotations

from ea_copilot.domain.enums import RequestStatus
from ea_copilot.domain.errors import InvalidTransitionError

ALLOWED_TRANSITIONS: frozenset[tuple[RequestStatus, RequestStatus]] = frozenset(
    {
        (RequestStatus.DRAFT, RequestStatus.NEEDS_INFO),
        (RequestStatus.DRAFT, RequestStatus.QUALIFIED),
        (RequestStatus.DRAFT, RequestStatus.REJECTED),
        (RequestStatus.NEEDS_INFO, RequestStatus.DRAFT),
        (RequestStatus.QUALIFIED, RequestStatus.AWAITING_EA_REVIEW),
        (RequestStatus.AWAITING_EA_REVIEW, RequestStatus.APPROVED),
        (RequestStatus.AWAITING_EA_REVIEW, RequestStatus.REJECTED),
        (RequestStatus.AWAITING_EA_REVIEW, RequestStatus.NEEDS_INFO),
        (RequestStatus.AWAITING_EA_REVIEW, RequestStatus.AWAITING_EA_REVIEW),
        (RequestStatus.APPROVED, RequestStatus.DRAFT_PENDING),
        (RequestStatus.DRAFT_PENDING, RequestStatus.DRAFT_CREATED),
        (RequestStatus.APPROVED, RequestStatus.DRAFT_CREATED),
        (RequestStatus.DRAFT_CREATED, RequestStatus.CLOSED),
    }
)


def transition(current: RequestStatus, target: RequestStatus) -> RequestStatus:
    """Return the target only when the documented transition is legal."""

    if (current, target) not in ALLOWED_TRANSITIONS:
        raise InvalidTransitionError(current, target)
    return target
