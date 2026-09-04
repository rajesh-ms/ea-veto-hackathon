"""Narrow M365 read surface and sole draft write for FR-201, FR-401, FR-604, INV-1, INV-2."""

from datetime import timedelta
from typing import Protocol, runtime_checkable

from ea_copilot.domain.live_models import DraftAuthorization, DraftCommand
from ea_copilot.domain.models import (
    CalendarEvent,
    ChatMessage,
    DraftEvent,
    FileReference,
    MailMessage,
    ScheduleResponse,
    TimeSlot,
    WorkingHours,
)


@runtime_checkable
class M365Port(Protocol):
    def get_schedule(self, upns: list[str], window: TimeSlot) -> list[ScheduleResponse]: ...

    def get_working_hours(self, upn: str) -> WorkingHours: ...

    def get_calendar_view(self, upn: str, window: TimeSlot) -> list[CalendarEvent]: ...

    def find_meeting_times(
        self,
        upns: list[str],
        duration: timedelta,
        window: TimeSlot,
    ) -> list[TimeSlot]: ...

    def search_mail(self, query: str, limit: int = 10) -> list[MailMessage]: ...

    def search_teams(self, query: str, limit: int = 10) -> list[ChatMessage]: ...

    def search_files(self, query: str, limit: int = 10) -> list[FileReference]: ...

    def delta_events(
        self,
        upn: str,
        delta_token: str | None,
    ) -> tuple[list[CalendarEvent], str]: ...

    def create_draft_event(
        self,
        organiser: str,
        subject: str,
        body: str,
        slot: TimeSlot,
        required: list[str],
        optional: list[str],
        location: str | None,
        authorization: DraftAuthorization,
    ) -> DraftEvent | DraftCommand: ...
