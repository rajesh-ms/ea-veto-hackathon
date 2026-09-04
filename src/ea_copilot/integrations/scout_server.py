"""Microsoft Scout stdio MCP integration for FR-901, FR-906, and FR-907."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal, cast

from mcp.server.fastmcp import FastMCP

from ea_copilot.adapters.scout_m365 import ScoutM365Adapter
from ea_copilot.bootstrap import ApplicationRuntime, build_live_runtime
from ea_copilot.config import project_root
from ea_copilot.domain.enums import EADecision
from ea_copilot.domain.live_models import DraftCompletion, ScoutCalendarSnapshot
from ea_copilot.domain.models import DraftEvent, Requester
from ea_copilot.services.aliases import AliasDirectory


class ScoutToolService:
    """Translate narrow Scout tools into the existing governed orchestrator."""

    def __init__(self, runtime: ApplicationRuntime) -> None:
        if not runtime.live_mode or runtime.aliases is None:
            raise ValueError("ScoutToolService requires a live runtime")
        self.runtime = runtime
        self._correlations: dict[str, str] = {}

    @property
    def aliases(self) -> AliasDirectory:
        aliases = self.runtime.aliases
        if aliases is None:
            raise RuntimeError("Live aliases are not configured")
        return aliases

    def _redact_mapping(self, value: dict[str, Any]) -> dict[str, Any]:
        redacted = self.aliases.redact(value)
        if not isinstance(redacted, dict):
            raise TypeError("Redaction changed a mapping into another value")
        return cast(dict[str, Any], redacted)

    def submit_request(
        self,
        teams_message_id: str,
        raw_text: str,
        structured_fields: dict[str, Any],
    ) -> dict[str, Any]:
        if teams_message_id in self._correlations:
            request_id = self._correlations[teams_message_id]
            request = self.runtime.orchestrator.request(request_id)
            return self._redact_mapping(request.model_dump(mode="json"))
        fields = dict(structured_fields)
        requested = fields.get("requested_executives", [])
        if not isinstance(requested, list) or not requested:
            raise ValueError("requested_executives must contain Exec A or Exec B")
        fields["requested_executives"] = [
            self.aliases.resolve(alias) for alias in requested if alias in self.aliases.aliases
        ]
        if len(fields["requested_executives"]) != len(requested):
            raise ValueError("Only Exec A and Exec B are valid executive aliases")
        request = self.runtime.orchestrator.submit(
            raw_text,
            Requester(entra_object_id="scout-owner", display_name="EA"),
            structured_fields=fields,
        )
        self._correlations[teams_message_id] = request.request_id
        result = self._redact_mapping(request.model_dump(mode="json"))
        result["teams_message_id"] = teams_message_id
        return result

    def attach_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        adapter = self.runtime.m365
        if not isinstance(adapter, ScoutM365Adapter):
            raise RuntimeError("Live Scout M365 adapter is not active")
        accepted = adapter.ingest(ScoutCalendarSnapshot.model_validate(snapshot))
        return {
            "request_id": accepted.request_id,
            "schedule_count": len(accepted.schedules),
            "limitation_count": len(accepted.limitations),
            "source": "live_via_scout",
        }

    def get_recommendation(self, request_id: str) -> dict[str, Any]:
        packet = self.runtime.orchestrator.build_recommendation(request_id)
        feasible = self.runtime.orchestrator.feasible_for(request_id)
        return self._redact_mapping(
            {
                "packet": packet.model_dump(mode="json"),
                "feasible_set": feasible.model_dump(mode="json"),
            }
        )

    def record_decision(
        self,
        recommendation_id: str,
        decision: Literal["approve", "edit", "reject", "return_for_info", "regenerate"],
        chosen_option_id: str | None,
        edits: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        approval = self.runtime.orchestrator.decide(
            recommendation_id,
            "EA",
            EADecision(decision),
            chosen_option_id=chosen_option_id,
            edits=edits,
        )
        return {
            "approval_id": approval.approval_id,
            "recommendation_id": recommendation_id,
            "decision": approval.decision.value,
        }

    def prepare_draft(self, recommendation_id: str) -> dict[str, Any]:
        result = self.runtime.orchestrator.create_draft(recommendation_id, "EA")
        if isinstance(result, DraftEvent):
            raise RuntimeError("Live Scout draft unexpectedly completed synchronously")
        payload = result.model_dump(mode="json")
        payload["confirmation_required"] = True
        return payload

    def complete_draft(
        self,
        *,
        command_id: str,
        transaction_id: str,
        graph_event_id: str,
        web_link: str,
        draft: bool,
    ) -> dict[str, Any]:
        completion = DraftCompletion.model_validate(
            {
                "command_id": command_id,
                "transaction_id": transaction_id,
                "graph_event_id": graph_event_id,
                "web_link": web_link,
                "draft": draft,
                "completed_at": self.runtime.clock.now(),
            }
        )
        event = self.runtime.orchestrator.complete_draft(completion)
        return {
            "draft_id": event.draft_id,
            "graph_event_id": event.graph_event_id,
            "web_link": event.web_link,
            "is_sent": False,
        }

    def demo_state(self) -> dict[str, Any]:
        return {
            "configured": True,
            "live_mode": True,
            "aliases": list(self.aliases.aliases),
            "correlations": len(self._correlations),
            "pending_commands": [
                command.command_id for command in self.runtime.draft_commands.pending()
            ],
        }


def _load_local_service() -> ScoutToolService:
    root = project_root()
    configured = os.environ.get("EA_COPILOT_IDENTITIES")
    path = Path(configured) if configured else root / ".local" / "live-identities.json"
    if not path.is_file():
        raise RuntimeError(f"Live identity configuration is missing: {path}")
    values = json.loads(path.read_text(encoding="utf-8"))
    aliases = AliasDirectory(values["aliases"])
    self_identifier = values["self_identifier"]
    if not isinstance(self_identifier, str) or not self_identifier:
        raise ValueError("self_identifier must be a non-empty string")
    runtime = build_live_runtime(
        root,
        aliases=aliases,
        self_identifier=self_identifier,
        vault_path=root / "demo-vault",
    )
    return ScoutToolService(runtime)


_SERVICE: ScoutToolService | None = None


def _service() -> ScoutToolService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = _load_local_service()
    return _SERVICE


def create_server() -> FastMCP[None]:
    """Create the stdio server without loading local identities until tool use."""

    server: FastMCP[None] = FastMCP(
        "EA Copilot",
        instructions="Governed executive scheduling through Scout delegated Microsoft 365 access.",
        log_level="ERROR",
    )

    @server.tool(name="ea_submit_request")
    def submit_request(
        teams_message_id: str,
        raw_text: str,
        structured_fields: dict[str, Any],
    ) -> dict[str, Any]:
        return _service().submit_request(teams_message_id, raw_text, structured_fields)

    @server.tool(name="ea_attach_snapshot")
    def attach_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
        return _service().attach_snapshot(snapshot)

    @server.tool(name="ea_get_recommendation")
    def get_recommendation(request_id: str) -> dict[str, Any]:
        return _service().get_recommendation(request_id)

    @server.tool(name="ea_record_decision")
    def record_decision(
        recommendation_id: str,
        decision: Literal["approve", "edit", "reject", "return_for_info", "regenerate"],
        chosen_option_id: str | None = None,
        edits: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return _service().record_decision(
            recommendation_id,
            decision,
            chosen_option_id,
            edits,
        )

    @server.tool(name="ea_prepare_draft")
    def prepare_draft(recommendation_id: str) -> dict[str, Any]:
        return _service().prepare_draft(recommendation_id)

    @server.tool(name="ea_complete_draft")
    def complete_draft(
        command_id: str,
        transaction_id: str,
        graph_event_id: str,
        web_link: str,
        draft: bool,
    ) -> dict[str, Any]:
        return _service().complete_draft(
            command_id=command_id,
            transaction_id=transaction_id,
            graph_event_id=graph_event_id,
            web_link=web_link,
            draft=draft,
        )

    @server.tool(name="ea_get_demo_state")
    def get_demo_state() -> dict[str, Any]:
        try:
            return _service().demo_state()
        except (OSError, ValueError, RuntimeError) as error:
            return {"configured": False, "reason": str(error)}

    return server


def main() -> None:
    """Run the integration over stdio for Scout."""

    create_server().run(transport="stdio")
