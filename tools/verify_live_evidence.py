"""Validate sanitized evidence from a real Scout/Teams/M365 demonstration."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

_EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_LAYERS = ["Current Session", "Evidence History", "Governed Memory"]
_SCENARIOS = ["scenario-1-complete", "scenario-2-complete", "scenario-3-complete"]


class LiveEvidenceError(ValueError):
    """Live evidence is missing a required proof or contains private identity."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise LiveEvidenceError(message)


def validate_evidence(path: Path) -> dict[str, Any]:
    """Return validated evidence or raise with a fail-closed reason."""

    if not path.is_file():
        raise LiveEvidenceError(f"Live evidence file does not exist: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LiveEvidenceError(f"Live evidence is not valid JSON: {error}") from error
    if not isinstance(value, dict):
        raise LiveEvidenceError("Live evidence must be a JSON object")
    encoded = json.dumps(value, sort_keys=True)
    _require(_EMAIL.search(encoded) is None, "Live evidence contains an identity email")
    _require(value.get("aliases") == ["Exec A", "Exec B"], "Live evidence aliases are invalid")
    _require(value.get("teams_intake_correlated") is True, "Teams intake is not correlated")
    _require(value.get("calendar_source") == "live_via_scout", "Calendar source is not live")
    _require(value.get("memory_layers") == _LAYERS, "Live evidence memory layers are incomplete")
    _require(
        value.get("candidate_inert_before_approval") is True,
        "Candidate inertia was not proven",
    )
    _require(value.get("profile_version_changed") is True, "Profile version change was not proven")
    draft = value.get("draft")
    _require(isinstance(draft, dict), "Live evidence draft record is missing")
    _require(draft.get("subject_prefix") == "[DEMO]", "Draft subject is missing [DEMO]")
    _require(draft.get("draft") is True, "Live calendar action did not prove draft=true")
    _require(draft.get("attendee_count") == 1, "Live draft must have exactly one attendee")
    _require(draft.get("is_sent") is False, "Live draft was reported as sent")
    _require(
        value.get("forbidden_calendar_tools") == [],
        "Live evidence contains a forbidden calendar tool",
    )
    _require(value.get("scenarios") == _SCENARIOS, "Live evidence scenarios are incomplete")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    try:
        value = validate_evidence(args.evidence.resolve())
    except LiveEvidenceError as error:
        parser.exit(1, f"live evidence invalid: {error}\n")
    print(
        json.dumps(
            {
                "aliases": value["aliases"],
                "calendar_source": value["calendar_source"],
                "draft": "unsent",
                "scenarios": len(value["scenarios"]),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
