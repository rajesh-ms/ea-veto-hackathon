"""Fail-closed live evidence and Obsidian preflight tests for FR-908 and FR-909."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from tools.verify_live_evidence import LiveEvidenceError, validate_evidence

ROOT = Path(__file__).parents[2]
VALID = ROOT / "tests" / "fixtures" / "live" / "scout-evidence-valid.json"


def load_valid() -> dict[str, Any]:
    return json.loads(VALID.read_text(encoding="utf-8"))


def test_FR_908_valid_live_evidence_proves_every_governed_scene() -> None:
    evidence = validate_evidence(VALID)

    assert evidence["aliases"] == ["Exec A", "Exec B"]
    assert evidence["calendar_source"] == "live_via_scout"
    assert evidence["draft"]["draft"] is True


def set_missing_layer(value: dict[str, Any]) -> None:
    value["memory_layers"] = ["Current Session", "Evidence History"]


def set_false_draft(value: dict[str, Any]) -> None:
    value["draft"]["draft"] = False


def set_two_attendees(value: dict[str, Any]) -> None:
    value["draft"]["attendee_count"] = 2


def add_forbidden_tool(value: dict[str, Any]) -> None:
    value["forbidden_calendar_tools"] = ["workiq_update_event"]


def add_identity_leak(value: dict[str, Any]) -> None:
    value["debug"] = "someone@example.invalid"


@pytest.mark.parametrize(
    "mutate, message",
    [
        (set_missing_layer, "memory layers"),
        (set_false_draft, "draft=true"),
        (set_two_attendees, "one attendee"),
        (add_forbidden_tool, "forbidden calendar"),
        (add_identity_leak, "identity"),
    ],
)
def test_FR_908_live_evidence_rejects_unsafe_or_incomplete_runs(
    tmp_path: Path,
    mutate: Callable[[dict[str, Any]], None],
    message: str,
) -> None:
    value = deepcopy(load_valid())
    mutate(value)
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(LiveEvidenceError, match=message):
        validate_evidence(path)


def test_FR_904_obsidian_installer_whatif_is_non_mutating(tmp_path: Path) -> None:
    marker = tmp_path / "not-installed"
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "tools" / "install_obsidian.ps1"),
            "-WhatIf",
            "-ProbePath",
            str(marker),
            "-ProbeOnly",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert "would install Obsidian.Obsidian" in completed.stdout
    assert not marker.exists()
