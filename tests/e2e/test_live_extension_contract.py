"""End-to-end extension contract for FR-901..FR-909."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def live_extension_report(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    root = Path(__file__).resolve().parents[2]
    output_dir = tmp_path_factory.mktemp("live-extension")
    report_path = output_dir / "report.json"
    vault_path = output_dir / "vault"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ea_copilot.cli.live_demo",
            "--offline",
            "--output",
            str(report_path),
            "--vault",
            str(vault_path),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return json.loads(report_path.read_text(encoding="utf-8"))


def test_FR_901_scout_intake_correlates_one_request(
    live_extension_report: dict[str, object],
) -> None:
    assert live_extension_report["intake_source"] == "teams_via_scout_fixture"
    assert live_extension_report["teams_message_id"]
    assert live_extension_report["request_id"]
    assert live_extension_report["correlated"] is True


def test_FR_902_public_projection_contains_aliases_not_upns(
    live_extension_report: dict[str, object],
) -> None:
    assert live_extension_report["aliases"] == ["Exec A", "Exec B"]
    assert live_extension_report["identity_leaks"] == []


def test_FR_903_calendar_board_has_two_aliased_lanes(
    live_extension_report: dict[str, object],
) -> None:
    board = live_extension_report["calendar"]
    assert isinstance(board, dict)
    assert board["source"] == "fixture"
    assert [lane["alias"] for lane in board["lanes"]] == ["Exec A", "Exec B"]


def test_FR_904_vault_has_exactly_three_memory_layers(
    live_extension_report: dict[str, object],
) -> None:
    assert live_extension_report["memory_layers"] == [
        "Current Session",
        "Evidence History",
        "Governed Memory",
    ]
    assert live_extension_report["vault_projected"] is True


def test_FR_905_graph_candidate_is_inert_until_approved(
    live_extension_report: dict[str, object],
) -> None:
    learning = live_extension_report["learning"]
    assert isinstance(learning, dict)
    assert learning["before"] == learning["with_candidate"]
    assert learning["after_approval"] != learning["before"]
    assert learning["profile_versions"] == ["v1", "v2"]


def test_FR_906_draft_sequence_is_approval_command_completion(
    live_extension_report: dict[str, object],
) -> None:
    draft = live_extension_report["draft"]
    assert isinstance(draft, dict)
    assert draft["actions"] == ["ea_decision", "draft_command_created", "draft_created"]
    assert draft["subject"] == "[DEMO] Executive scheduling prototype"
    assert draft["draft"] is True
    assert draft["attendee_count"] == 1
    assert draft["is_sent"] is False


def test_FR_907_scout_package_uses_stdio_without_credentials(
    live_extension_report: dict[str, object],
) -> None:
    integration = live_extension_report["integration"]
    assert isinstance(integration, dict)
    assert integration == {
        "transport": "stdio",
        "uses_scout_auth": True,
        "entra_app_registration": False,
        "credential_material": False,
    }


def test_FR_908_default_runtime_has_no_live_dependency(
    live_extension_report: dict[str, object],
) -> None:
    assert live_extension_report["mode"] == "offline"
    assert live_extension_report["live_dependency"] is False


def test_FR_909_demo_manifest_requires_three_scenarios(
    live_extension_report: dict[str, object],
) -> None:
    assert live_extension_report["scenarios"] == [
        "scenario-1-complete",
        "scenario-2-complete",
        "scenario-3-complete",
    ]
