"""Fail-closed coordinator for the human-confirmed Scout live demonstration."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verify_live_evidence import LiveEvidenceError, validate_evidence  # noqa: E402


class LivePreflightError(RuntimeError):
    """One required local live-demo component is unavailable."""


def _process_names() -> set[str]:
    completed = subprocess.run(
        ["tasklist", "/fo", "csv", "/nh"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise LivePreflightError("Windows process inventory is unavailable")
    rows = csv.reader(io.StringIO(completed.stdout))
    return {row[0].casefold() for row in rows if row}


def _obsidian_path() -> Path | None:
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Obsidian" / "Obsidian.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Obsidian" / "Obsidian.exe",
    ]
    return next((path for path in candidates if path.is_file()), None)


def preflight(state_root: Path, identities: Path) -> dict[str, Any]:
    """Check prerequisites without returning identity values."""

    processes = _process_names()
    scout_running = any("scout" in name for name in processes)
    teams_running = any("teams" in name for name in processes)
    config_path = state_root / "m-mcp-servers.json"
    skill_path = state_root / "skills" / "ea-copilot" / "SKILL.md"
    if not config_path.is_file():
        raise LivePreflightError("Scout MCP configuration is missing")
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    mcp_configured = "ea-copilot" in config.get("servers", {})
    if not identities.is_file():
        raise LivePreflightError("Local live identity mapping is missing")
    identity_data = json.loads(identities.read_text(encoding="utf-8"))
    alias_mapping = identity_data.get("aliases")
    identities_valid = (
        isinstance(alias_mapping, dict)
        and set(alias_mapping) == {"Exec A", "Exec B"}
        and isinstance(identity_data.get("self_identifier"), str)
        and bool(identity_data["self_identifier"])
    )
    checks = {
        "scout_running": scout_running,
        "teams_running": teams_running,
        "mcp_configured": mcp_configured,
        "skill_installed": skill_path.is_file(),
        "identity_mapping": identities_valid,
        "obsidian_installed": _obsidian_path() is not None,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise LivePreflightError(f"Live preflight failed: {', '.join(failed)}")
    return {"ok": True, "aliases": ["Exec A", "Exec B"], "checks": checks}


def wait_for_evidence(path: Path, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if path.is_file():
            try:
                return validate_evidence(path)
            except LiveEvidenceError:
                pass
        time.sleep(1)
    raise LivePreflightError("Timed out waiting for complete sanitized live evidence")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state-root", type=Path, default=Path.home() / ".scout"
    )
    parser.add_argument(
        "--identities", type=Path, default=ROOT / ".local" / "live-identities.json"
    )
    parser.add_argument(
        "--evidence", type=Path, default=ROOT / "artifacts" / "live-scout-evidence.json"
    )
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    try:
        status = preflight(args.state_root.resolve(), args.identities.resolve())
        print(json.dumps(status, sort_keys=True))
        if args.preflight_only:
            return 0
        print(
            "Live preflight passed. Send the alias-only intake from the personal Scout Teams "
            "chat and confirm the draft in the workbench when prompted."
        )
        evidence = wait_for_evidence(args.evidence.resolve(), args.timeout)
    except (LivePreflightError, LiveEvidenceError, OSError, json.JSONDecodeError) as error:
        parser.exit(1, f"live E2E failed: {error}\n")
    print(
        json.dumps(
            {
                "aliases": evidence["aliases"],
                "draft": "unsent",
                "scenarios": evidence["scenarios"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
