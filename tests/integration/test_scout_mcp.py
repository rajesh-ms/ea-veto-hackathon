"""Real stdio MCP handshake tests for FR-901, FR-906, and FR-907."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

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
