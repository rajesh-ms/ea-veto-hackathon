"""Domain failures for FR-106, FR-204, FR-606, FR-608, and INV-6."""


class EACopilotError(Exception):
    """Base error for expected application failures."""


class ApprovalRequiredError(EACopilotError):
    def __init__(self, recommendation_id: str) -> None:
        super().__init__(f"EA approval is required for recommendation {recommendation_id}")
        self.recommendation_id = recommendation_id


class CalendarWritesDisabledError(EACopilotError):
    """The calendar-write kill switch is active."""


class InvalidTransitionError(EACopilotError):
    def __init__(self, current: object, target: object) -> None:
        super().__init__(f"Invalid request transition: {current} -> {target}")


class PermissionDeniedError(EACopilotError):
    def __init__(self, subject: str, reason: str) -> None:
        super().__init__(reason)
        self.subject = subject
        self.reason = reason


class FixtureMissingError(EACopilotError):
    """A fake adapter has no deterministic fixture for an input."""


class InjectionRefusedError(EACopilotError):
    """Untrusted content was classified as an instruction attempt."""


class ResourceNotFoundError(EACopilotError):
    """A requested local aggregate does not exist."""


class DecisionValidationError(EACopilotError):
    """An EA decision is incomplete or inconsistent with a recommendation."""


class DraftCompletionError(EACopilotError):
    """A Scout completion does not match an approved draft command."""


class ScoutSequenceError(EACopilotError):
    """A Scout transcript violates the governed tool sequence."""
