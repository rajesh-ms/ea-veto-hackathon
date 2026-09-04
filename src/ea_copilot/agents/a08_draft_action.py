"""Approval-preconditioned draft action for FR-604..FR-608, FR-906, INV-1..INV-2."""

from __future__ import annotations

from ea_copilot.config import Settings
from ea_copilot.domain.errors import ApprovalRequiredError, CalendarWritesDisabledError
from ea_copilot.domain.live_models import (
    DraftAuthorization,
    DraftCommand,
    DraftCompletion,
    DraftSubmission,
)
from ea_copilot.domain.models import AuditRecord, DraftEvent, MeetingRequest, RecommendationPacket
from ea_copilot.ports.clock import ClockPort
from ea_copilot.ports.m365 import M365Port
from ea_copilot.services.audit import AuditStore
from ea_copilot.services.draft_commands import DraftCommandStore
from ea_copilot.services.ids import stable_id


class DraftActionAgent:
    def __init__(
        self,
        m365: M365Port,
        audit: AuditStore,
        clock: ClockPort,
        settings: Settings,
        draft_commands: DraftCommandStore,
    ) -> None:
        self._m365 = m365
        self._audit = audit
        self._clock = clock
        self._settings = settings
        self._draft_commands = draft_commands
        self._packets: dict[str, RecommendationPacket] = {}
        self._requests: dict[str, MeetingRequest] = {}

    def register(self, packet: RecommendationPacket, request: MeetingRequest) -> None:
        self._packets[packet.recommendation_id] = packet
        self._requests[packet.recommendation_id] = request

    def create_draft(self, recommendation_id: str, actor: str) -> DraftSubmission:
        approval = self._audit.find_approval(recommendation_id)
        if approval is None:
            raise ApprovalRequiredError(recommendation_id)
        if not self._settings.calendar_writes_enabled:
            raise CalendarWritesDisabledError("Calendar drafting is disabled")
        packet = self._packets[recommendation_id]
        request = self._requests[recommendation_id]
        option = next(
            item for item in packet.options if item.option_id == approval.chosen_option_id
        )
        edits = approval.edits
        subject = str(edits.get("subject", request.objective or "Executive meeting"))
        required = edits.get("required_attendees", request.required_attendees)
        optional = edits.get("optional_attendees", request.optional_attendees)
        location = edits.get("location", request.location)
        if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
            raise TypeError("required_attendees edit must be a list of strings")
        if not isinstance(optional, list) or not all(isinstance(item, str) for item in optional):
            raise TypeError("optional_attendees edit must be a list of strings")
        if location is not None and not isinstance(location, str):
            raise TypeError("location edit must be a string")
        raw = self._m365.create_draft_event(
            organiser=actor,
            subject=subject,
            body=f"Draft only. {option.rationale}",
            slot=option.slot,
            required=required,
            optional=optional,
            location=location,
            authorization=DraftAuthorization(
                request_id=request.request_id,
                recommendation_id=recommendation_id,
                approval_id=approval.approval_id,
            ),
        )
        if isinstance(raw, DraftCommand):
            records = self._audit.for_request(request.request_id)
            if not any(
                record.action == "draft_command_created"
                and record.payload.get("command_id") == raw.command_id
                for record in records
            ):
                self._audit.append(
                    AuditRecord(
                        audit_id=stable_id(
                            "AUD", request.request_id, "draft_command", len(records)
                        ),
                        request_id=request.request_id,
                        recommendation_id=recommendation_id,
                        actor=actor,
                        action="draft_command_created",
                        occurred_at=self._clock.now(),
                        profile_version=packet.profile_version,
                        policy_version=packet.policy_version,
                        model_version=packet.model_version,
                        weights_version=packet.weights_version,
                        approval_id=approval.approval_id,
                        outcome="pending_execution",
                        payload={
                            "command_id": raw.command_id,
                            "transaction_id": raw.transaction_id,
                            "subject": raw.subject,
                            "draft": True,
                            "attendee_count": 1,
                        },
                    )
                )
            return raw
        return self._record_sync_draft(raw, request, packet, approval.approval_id, actor)

    def _record_sync_draft(
        self,
        raw: DraftEvent,
        request: MeetingRequest,
        packet: RecommendationPacket,
        approval_id: str,
        actor: str,
    ) -> DraftEvent:
        draft = raw.model_copy(
            update={
                "request_id": request.request_id,
                "recommendation_id": packet.recommendation_id,
                "approval_id": approval_id,
                "created_at": self._clock.now(),
            }
        )
        records = self._audit.for_request(request.request_id)
        self._audit.append(
            AuditRecord(
                audit_id=stable_id("AUD", request.request_id, "draft", len(records)),
                request_id=request.request_id,
                recommendation_id=packet.recommendation_id,
                actor=actor,
                action="draft_created",
                occurred_at=self._clock.now(),
                profile_version=packet.profile_version,
                policy_version=packet.policy_version,
                model_version=packet.model_version,
                weights_version=packet.weights_version,
                approval_id=approval_id,
                outcome="unsent",
                payload={"draft": draft.model_dump(mode="json")},
            )
        )
        return draft

    def complete_draft(self, completion: DraftCompletion) -> DraftEvent:
        draft = self._draft_commands.complete(completion)
        records = self._audit.for_request(draft.request_id)
        if any(
            record.action == "draft_created"
            and record.payload.get("graph_event_id") == draft.graph_event_id
            for record in records
        ):
            return draft
        packet = self._packets[draft.recommendation_id]
        self._audit.append(
            AuditRecord(
                audit_id=stable_id("AUD", draft.request_id, "draft", len(records)),
                request_id=draft.request_id,
                recommendation_id=draft.recommendation_id,
                actor="scout:m365",
                action="draft_created",
                occurred_at=completion.completed_at,
                profile_version=packet.profile_version,
                policy_version=packet.policy_version,
                model_version=packet.model_version,
                weights_version=packet.weights_version,
                approval_id=draft.approval_id,
                outcome="unsent",
                payload={
                    "draft": draft.model_dump(mode="json"),
                    "graph_event_id": draft.graph_event_id,
                },
            )
        )
        return draft
