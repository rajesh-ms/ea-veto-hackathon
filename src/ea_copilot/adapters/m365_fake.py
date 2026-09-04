"""Offline Microsoft 365 fixture adapter for FR-201..FR-205, FR-401..FR-407, FR-604."""

from __future__ import annotations

import json
import re
from datetime import timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from ea_copilot.domain.errors import PermissionDeniedError
from ea_copilot.domain.live_models import DraftAuthorization
from ea_copilot.domain.models import (
    CalendarEvent,
    ChatMessage,
    DraftEvent,
    FileReference,
    FreeBusySlot,
    MailMessage,
    ScheduleResponse,
    TimeSlot,
    WorkingHours,
)
from ea_copilot.ports.clock import ClockPort

_CENTRAL = ZoneInfo("America/Chicago")


class FakeM365Adapter:
    """Loads a fixed synthetic tenant and records every observable port call."""

    def __init__(self, fixture_dir: Path, clock: ClockPort) -> None:
        self._clock = clock
        self._people: dict[str, dict[str, Any]] = {}
        for path in sorted(fixture_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            self._people[str(data["upn"])] = data
        self._denials: dict[str, str] = {}
        self._injected_mail: list[MailMessage] = []
        self.write_log: list[tuple[str, dict[str, object]]] = []
        self.read_log: list[tuple[str, dict[str, object]]] = []

    def deny_access(self, upn: str, reason: str) -> None:
        self._denials[upn] = reason

    def inject_mail(self, payload: str, *, source_id: str) -> None:
        """Add attacker-influenced mail to the fake tenant for security scenarios."""

        self._injected_mail.append(
            MailMessage(
                message_id=source_id,
                subject=f"Fixture {source_id}",
                body_preview=payload,
                web_url=f"https://outlook.example.invalid/mail/{source_id}",
                received_at=self._clock.now(),
            )
        )

    def block_all(self, start: str, end: str) -> None:
        """Overlay a deterministic fully-booked window for no-feasibility scenarios."""

        for upn, person in self._people.items():
            person["events"].append(
                {
                    "event_id": f"FULL-{upn}",
                    "subject": "Calendar fully booked",
                    "body_preview": "Synthetic full-window commitment.",
                    "start": start,
                    "end": end,
                    "show_as": "busy",
                    "is_movable": False,
                    "is_protected": False,
                    "location": "Virtual",
                    "organizer": upn,
                    "attendees": [],
                }
            )

    def _person(self, upn: str) -> dict[str, Any]:
        try:
            return self._people[upn]
        except KeyError as exc:
            raise PermissionDeniedError(upn, f"No delegated fixture access for {upn}") from exc

    def _events(self, upn: str) -> list[CalendarEvent]:
        return [CalendarEvent.model_validate(item) for item in self._person(upn)["events"]]

    @staticmethod
    def _overlaps(first: TimeSlot, second: TimeSlot) -> bool:
        return first.start < second.end and second.start < first.end

    def get_schedule(self, upns: list[str], window: TimeSlot) -> list[ScheduleResponse]:
        self.read_log.append(("get_schedule", {"upns": list(upns), "window": window}))
        responses: list[ScheduleResponse] = []
        for upn in upns:
            person = self._person(upn)
            events = [
                event
                for event in self._events(upn)
                if self._overlaps(TimeSlot(start=event.start, end=event.end), window)
            ]
            responses.append(
                ScheduleResponse(
                    upn=upn,
                    slots=[
                        FreeBusySlot(start=event.start, end=event.end, status=event.show_as)
                        for event in events
                    ],
                    working_hours=WorkingHours.model_validate(person["working_hours"]),
                    access_limited=upn in self._denials,
                )
            )
        return responses

    def get_working_hours(self, upn: str) -> WorkingHours:
        self.read_log.append(("get_working_hours", {"upn": upn}))
        return WorkingHours.model_validate(self._person(upn)["working_hours"])

    def get_calendar_view(self, upn: str, window: TimeSlot) -> list[CalendarEvent]:
        self.read_log.append(("get_calendar_view", {"upn": upn, "window": window}))
        if upn in self._denials:
            raise PermissionDeniedError(upn, self._denials[upn])
        return [
            event
            for event in self._events(upn)
            if self._overlaps(TimeSlot(start=event.start, end=event.end), window)
        ]

    def find_meeting_times(
        self,
        upns: list[str],
        duration: timedelta,
        window: TimeSlot,
    ) -> list[TimeSlot]:
        self.read_log.append(
            (
                "find_meeting_times",
                {"upns": list(upns), "duration_minutes": duration.total_seconds() / 60},
            )
        )
        schedules = {response.upn: response for response in self.get_schedule(upns, window)}
        result: list[TimeSlot] = []
        cursor = window.start
        while cursor + duration <= window.end:
            slot = TimeSlot(start=cursor, end=cursor + duration)
            local = cursor.astimezone(_CENTRAL)
            within_hours = all(
                response.working_hours is not None
                and local.strftime("%A").lower() in response.working_hours.days_of_week
                and local.time() >= response.working_hours.start_time
                and slot.end.astimezone(_CENTRAL).time() <= response.working_hours.end_time
                for response in schedules.values()
            )
            busy = any(
                self._overlaps(slot, TimeSlot(start=item.start, end=item.end))
                and item.status in {"busy", "oof"}
                for response in schedules.values()
                for item in response.slots
            )
            if within_hours and not busy:
                result.append(slot)
            cursor += timedelta(minutes=15)
        return result

    def _all(self, key: str) -> list[dict[str, Any]]:
        return [item for person in self._people.values() for item in person.get(key, [])]

    @staticmethod
    def _matches(query: str, *values: str) -> bool:
        tokens = {
            token
            for token in re.findall(r"[a-z0-9]+", query.lower())
            if len(token) >= 2 and token not in {"the", "and", "for", "with", "choose"}
        }
        corpus = " ".join(values).lower()
        return not tokens or any(token in corpus for token in tokens)

    def search_mail(self, query: str, limit: int = 10) -> list[MailMessage]:
        self.read_log.append(("search_mail", {"query": query, "limit": limit}))
        regular = [MailMessage.model_validate(item) for item in self._all("mail")]
        items = [
            *self._injected_mail,
            *[item for item in regular if self._matches(query, item.subject, item.body_preview)],
        ]
        return sorted(items, key=lambda item: item.received_at, reverse=True)[:limit]

    def search_teams(self, query: str, limit: int = 10) -> list[ChatMessage]:
        self.read_log.append(("search_teams", {"query": query, "limit": limit}))
        items = [ChatMessage.model_validate(item) for item in self._all("teams")]
        matched = [item for item in items if self._matches(query, item.topic, item.body)]
        return sorted(matched, key=lambda item: item.created_at, reverse=True)[:limit]

    def search_files(self, query: str, limit: int = 10) -> list[FileReference]:
        self.read_log.append(("search_files", {"query": query, "limit": limit}))
        items = [FileReference.model_validate(item) for item in self._all("files")]
        matched = [item for item in items if self._matches(query, item.name, item.excerpt)]
        return sorted(matched, key=lambda item: item.modified_at, reverse=True)[:limit]

    def delta_events(
        self,
        upn: str,
        delta_token: str | None,
    ) -> tuple[list[CalendarEvent], str]:
        self.read_log.append(("delta_events", {"upn": upn, "delta_token": delta_token}))
        return self._events(upn), f"delta-{upn}-v1"

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
    ) -> DraftEvent:
        sequence = len(self.write_log) + 1
        payload: dict[str, object] = {
            "organiser": organiser,
            "subject": subject,
            "body": body,
            "slot": slot,
            "required": list(required),
            "optional": list(optional),
            "location": location,
            "authorization": authorization,
        }
        self.write_log.append(("create_draft_event", payload))
        return DraftEvent(
            draft_id=f"DRAFT-{sequence:04d}",
            request_id="PENDING",
            recommendation_id="PENDING",
            approval_id="PENDING",
            graph_event_id=f"GRAPH-DRAFT-{sequence:04d}",
            web_link=f"https://outlook.example.invalid/draft/{sequence:04d}",
            is_sent=False,
            created_at=self._clock.now(),
        )
