"""Real stdio MCP handshake tests for FR-901, FR-906, and FR-907."""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from ea_copilot.adapters.clock_fixed import FixedClock
from ea_copilot.bootstrap import build_live_runtime
from ea_copilot.domain.live_models import GraphPreferenceEvidence, ScoutCalendarSnapshot
from ea_copilot.domain.models import SourceReference
from ea_copilot.integrations.scout_server import ScoutToolService
from ea_copilot.services.aliases import AliasDirectory

ROOT = Path(__file__).parents[2]
EXPECTED_TOOLS = {
    "ea_submit_request",
    "ea_attach_snapshot",
    "ea_get_recommendation",
    "ea_record_decision",
    "ea_prepare_draft",
    "ea_complete_draft",
    "ea_get_demo_state",
}


async def listed_tool_names() -> set[str]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src")
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "ea_copilot.integrations"],
        cwd=ROOT,
        env=environment,
    )
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            response = await session.list_tools()
            return {tool.name for tool in response.tools}


def test_FR_907_stdio_mcp_exposes_only_the_governed_ea_tool_allowlist() -> None:
    names = asyncio.run(listed_tool_names())

    assert names == EXPECTED_TOOLS
    forbidden = ("send", "update", "move", "delete", "accept", "decline", "shell")
    assert not any(word in name for name in names for word in forbidden)


def test_FR_905_scout_snapshot_places_graph_observations_in_evidence_history() -> None:
    now = datetime(2026, 9, 14, 13, 0, tzinfo=UTC)
    runtime = build_live_runtime(
        ROOT,
        aliases=AliasDirectory({"Exec A": "alpha-id", "Exec B": "beta-id"}),
        self_identifier="self-id",
        clock=FixedClock(now),
    )
    evidence = GraphPreferenceEvidence(
        evidence_id="GRAPH-FROM-SCOUT-1",
        executive_upn="alpha-id",
        dimension="time_of_day",
        value="tuesday_after_12",
        source=SourceReference(
            source_id="source-1",
            source_type="event",
            title="Calendar pattern",
            retrieved_at=now,
        ),
        confidence=0.8,
        observed_at=now,
    )
    snapshot = ScoutCalendarSnapshot(
        request_id="REQ-SNAPSHOT",
        captured_at=now,
        schedules=[],
        events={},
        preference_evidence=[evidence],
    )

    ScoutToolService(runtime).attach_snapshot(snapshot.model_dump(mode="json"))

    assert runtime.live_evidence.for_executive("alpha-id") == [evidence]
