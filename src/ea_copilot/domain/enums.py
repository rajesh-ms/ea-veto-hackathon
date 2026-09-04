"""Closed vocabularies for FR-101..FR-709 and INV-1..INV-5."""

from enum import StrEnum


class RequestStatus(StrEnum):
    DRAFT = "Draft"
    NEEDS_INFO = "NeedsInfo"
    QUALIFIED = "Qualified"
    AWAITING_EA_REVIEW = "AwaitingEAReview"
    APPROVED = "Approved"
    DRAFT_PENDING = "DraftPending"
    DRAFT_CREATED = "DraftCreated"
    REJECTED = "Rejected"
    CLOSED = "Closed"


class PriorityTier(StrEnum):
    TIER1_STRATEGIC = "Tier1_Strategic"
    TIER2_IMPORTANT = "Tier2_Important"
    TIER3_ROUTINE = "Tier3_Routine"


class MeetingFormat(StrEnum):
    VIRTUAL = "Virtual"
    IN_PERSON = "InPerson"
    HYBRID = "Hybrid"


class EADecision(StrEnum):
    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"
    RETURN_FOR_INFO = "return_for_info"
    REGENERATE = "regenerate"


class ConstraintKind(StrEnum):
    PERMISSION_BOUNDARY = "permission_boundary"
    EXECUTIVE_BUSY = "executive_busy"
    NON_MOVABLE_EVENT = "non_movable_event"
    PROTECTED_BLOCK = "protected_block"
    OUTSIDE_WORKING_HOURS = "outside_working_hours"
    AFTER_DEADLINE = "after_deadline"
    PREPARATION_BUFFER = "preparation_buffer"
    TRAVEL_INFEASIBLE = "travel_infeasible"


class ReasonCode(StrEnum):
    EXECUTIVE_PREFERENCE = "executive_preference"
    TRAVEL_CONSIDERATION = "travel_consideration"
    STAKEHOLDER_IMPORTANCE = "stakeholder_importance"
    PERSONAL_CONSTRAINT = "personal_constraint"
    STRATEGIC_INITIATIVE = "strategic_initiative"
    CEO_OR_BOARD_DIRECTION = "ceo_or_board_direction"
    CUSTOMER_ESCALATION = "customer_escalation"
    DEADLINE_URGENCY = "deadline_urgency"
    MISSING_CONTEXT = "missing_context"
    INCORRECT_CONFLICT = "incorrect_conflict"
    PRIVACY_LIMITATION = "privacy_limitation"
    MEETING_FORMAT = "meeting_format"


class CandidateStatus(StrEnum):
    PROPOSED = "Proposed"
    BLOCKED = "Blocked"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    PAUSED = "Paused"
    DEFERRED = "Deferred"
