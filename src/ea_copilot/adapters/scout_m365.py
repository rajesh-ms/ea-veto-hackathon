"""Scout-supplied snapshot adapter for FR-903, FR-907, and FR-908."""

from __future__ import annotations

from datetime import timedelta

from ea_copilot.domain.errors import CalendarWritesDisabledError, FixtureMissingError
from ea_copilot.domain.live_models import DraftAuthorization, DraftCommand, ScoutCalendarSnapshot
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
from ea_copilot.ports.clock import ClockPort
from ea_copilot.services.draft_commands import DraftCommandStore
from ea_copilot.services.ids import stable_id


class ScoutM365Adapter:
    """Implement M365 reads from one authenticated, bounded Scout snapshot."""

    def __init__(
        self,
        clock: ClockPort,
        *,
        draft_commands: DraftCommandStore | None = None,
        self_identifier: str | None = None,
    ) -> None:
        self._clock = clock
        self._snapshot: ScoutCalendarSnapshot | None = None
        self.read_log: list[tuple[str, dict[str, object]]] = []
        self.network_calls = 0
        self.write_log: list[tuple[str, dict[str, object]]] = []
        self._draft_commands = draft_commands
        self._self_identifier = self_identifier

    def ingest(self, snapshot: ScoutCalendarSnapshot) -> ScoutCalendarSnapshot:
        self._snapshot = snapshot
        return snapshot

    def _current(self) -> ScoutCalendarSnapshot:
        if self._snapshot is None:
            raise FixtureMissingError("Scout calendar snapshot has not been ingested")
        return self._snapshot

    def get_schedule(self, upns: list[str], window: TimeSlot) -> list[ScheduleResponse]:
        self.read_log.append(("get_schedule", {"upns": upns, "window": window}))
        by_upn = {item.upn.casefold(): item for item in self._current().schedules}
        missing = [upn for upn in upns if upn.casefold() not in by_upn]
        if missing:
            raise FixtureMissingError(f"Scout calendar snapshot missing: {', '.join(missing)}")
        return [by_upn[upn.casefold()] for upn in upns]

    def get_working_hours(self, upn: str) -> WorkingHours:
        self.read_log.append(("get_working_hours", {"upn": upn}))
        schedule = self.get_schedule(
            [upn], TimeSlot(start=self._clock.now(), end=self._clock.now() + timedelta(days=1))
        )[0]
        if schedule.working_hours is None:
            raise FixtureMissingError(f"Scout snapshot has no working hours for {upn}")
        return schedule.working_hours

    @staticmethod
    def _overlaps(event: CalendarEvent, window: TimeSlot) -> bool:
        return event.start < window.end and window.start < event.end

    def get_calendar_view(self, upn: str, window: TimeSlot) -> list[CalendarEvent]:
        self.read_log.append(("get_calendar_view", {"upn": upn, "window": window}))
        events = self._current().events.get(upn)
        if events is None:
            raise FixtureMissingError(f"Scout calendar snapshot missing events for {upn}")
        return [event for event in events if self._overlaps(event, window)]

    def find_meeting_times(
        self,
        upns: list[str],
        duration: timedelta,
        window: TimeSlot,
    ) -> list[TimeSlot]:
        self.read_log.append(
            (
                "find_meeting_times",
                {"upns": upns, "duration": duration, "window": window},
            )
        )
        schedules = self.get_schedule(upns, window)
        if not schedules:
            return []
        candidates: list[TimeSlot] = []
        for slot in schedules[0].slots:
            end = slot.start + duration
            outside_window = slot.start < window.start or end > window.end
            if slot.status != "free" or end > slot.end or outside_window:
                continue
            if all(
                any(
                    other.status == "free" and other.start <= slot.start and other.end >= end
                    for other in schedule.slots
                )
                for schedule in schedules[1:]
            ):
                candidates.append(TimeSlot(start=slot.start, end=end))
        return candidates

    @staticmethod
    def _matches(query: str, *values: str) -> bool:
        needle = query.casefold()
        return any(needle in value.casefold() for value in values)

    def search_mail(self, query: str, limit: int = 10) -> list[MailMessage]:
        self.read_log.append(("search_mail", {"query": query, "limit": limit}))
        return [
            item
            for item in self._current().mail
            if self._matches(query, item.subject, item.body_preview)
        ][:limit]

    def search_teams(self, query: str, limit: int = 10) -> list[ChatMessage]:
        self.read_log.append(("search_teams", {"query": query, "limit": limit}))
        return [
            item
            for item in self._current().teams
            if self._matches(query, item.topic, item.body)
        ][:limit]

    def search_files(self, query: str, limit: int = 10) -> list[FileReference]:
        self.read_log.append(("search_files", {"query": query, "limit": limit}))
        return [
            item
            for item in self._current().files
            if self._matches(query, item.name, item.excerpt)
        ][:limit]

    def delta_events(
        self, upn: str, delta_token: str | None
    ) -> tuple[list[CalendarEvent], str]:
        self.read_log.append(("delta_events", {"upn": upn, "delta_token": delta_token}))
        events = self._current().events.get(upn)
        if events is None:
            raise FixtureMissingError(f"Scout calendar snapshot missing events for {upn}")
        token = stable_id("DELTA", self._current().request_id, upn, self._current().captured_at)
        return list(events), token

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
    ) -> DraftEvent | DraftCommand:
        del organiser, subject, required, optional
        if self._draft_commands is None or self._self_identifier is None:
            raise CalendarWritesDisabledError("Scout draft bridge is not configured")
        transaction_id = stable_id(
            "TX",
            authorization.request_id,
            authorization.recommendation_id,
            authorization.approval_id,
        )
        command = DraftCommand(
            command_id=stable_id("CMD", transaction_id),
            transaction_id=transaction_id,
            request_id=authorization.request_id,
            recommendation_id=authorization.recommendation_id,
            approval_id=authorization.approval_id,
            subject="[DEMO] Executive scheduling prototype",
            body=body,
            slot=slot,
            attendee=self._self_identifier,
            location=location,
            draft=True,
            created_at=self._clock.now(),
        )
        stored = self._draft_commands.append(command)
        if not self.write_log:
            self.write_log.append(
                (
                    "create_draft_event",
                    {
                        "command_id": command.command_id,
                        "transaction_id": command.transaction_id,
                        "draft": True,
                        "attendee_count": 1,
                    },
                )
            )
        return stored
