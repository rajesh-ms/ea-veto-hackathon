"""State-machine contract tests for FR-105, FR-106, FR-605, and INV-1."""

from __future__ import annotations

import pytest

from ea_copilot.domain.enums import RequestStatus
from ea_copilot.domain.errors import InvalidTransitionError
from ea_copilot.domain.state_machine import transition


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (RequestStatus.DRAFT, RequestStatus.NEEDS_INFO),
        (RequestStatus.DRAFT, RequestStatus.QUALIFIED),
        (RequestStatus.DRAFT, RequestStatus.REJECTED),
        (RequestStatus.NEEDS_INFO, RequestStatus.DRAFT),
        (RequestStatus.QUALIFIED, RequestStatus.AWAITING_EA_REVIEW),
        (RequestStatus.AWAITING_EA_REVIEW, RequestStatus.APPROVED),
        (RequestStatus.AWAITING_EA_REVIEW, RequestStatus.REJECTED),
        (RequestStatus.APPROVED, RequestStatus.DRAFT_PENDING),
        (RequestStatus.DRAFT_PENDING, RequestStatus.DRAFT_CREATED),
        (RequestStatus.APPROVED, RequestStatus.DRAFT_CREATED),
        (RequestStatus.DRAFT_CREATED, RequestStatus.CLOSED),
    ],
)
def test_documented_transitions_are_allowed_FR_105_FR_605(
    current: RequestStatus,
    target: RequestStatus,
) -> None:
    assert transition(current, target) is target


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (RequestStatus.QUALIFIED, RequestStatus.DRAFT_CREATED),
        (RequestStatus.AWAITING_EA_REVIEW, RequestStatus.DRAFT_CREATED),
        (RequestStatus.REJECTED, RequestStatus.APPROVED),
        (RequestStatus.DRAFT, RequestStatus.DRAFT_CREATED),
    ],
)
def test_status_cannot_skip_the_approval_gate_INV_1_FR_605(
    current: RequestStatus,
    target: RequestStatus,
) -> None:
    with pytest.raises(InvalidTransitionError):
        transition(current, target)
