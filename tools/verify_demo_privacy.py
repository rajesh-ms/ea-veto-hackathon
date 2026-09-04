"""Verify complete demo scenes, alias-only identity, and three-layer memory."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verify_live_evidence import validate_evidence  # noqa: E402

_EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_SENT_CLAIM = re.compile(
    r"\b(?:invitation sent|sent invitation|event was sent|meeting was sent)\b",
    re.IGNORECASE,
)
_SCENES = {
    "teams-intake",
    "calendar-exec-a-b",
    "memory-three-layers",
    "approval-gate",
    "demo-unsent-draft",
    "learning-before-after",
    "quality-gates",
    "scenario-1-complete",
    "scenario-2-complete",
    "scenario-3-complete",
}
_LAYERS = ["01 Current Session", "02 Evidence History", "03 Governed Memory"]


class DemoPrivacyError(ValueError):
    """The demo is incomplete or exposes prohibited identity/action text."""


def _load_object(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise DemoPrivacyError(f"{label} does not exist: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DemoPrivacyError(f"{label} is invalid JSON: {error}") from error
    if not isinstance(value, dict):
        raise DemoPrivacyError(f"{label} must be a JSON object")
    return value


def validate_demo_privacy(
    manifest_path: Path,
    evidence_path: Path,
    vault_path: Path,
) -> dict[str, Any]:
    """Validate the demo's required scenes and privacy-filtered artifacts."""

    manifest = _load_object(manifest_path, "Demo manifest")
    validate_evidence(evidence_path)
    scenes = manifest.get("scenes")
    if not isinstance(scenes, list) or set(scenes) != _SCENES:
        missing = sorted(_SCENES - set(scenes if isinstance(scenes, list) else []))
        raise DemoPrivacyError(f"Demo scene set is incomplete: {', '.join(missing)}")
    if manifest.get("aliases") != ["Exec A", "Exec B"]:
        raise DemoPrivacyError("Demo identities are not the approved aliases")
    if manifest.get("recording_type") != "desktop":
        raise DemoPrivacyError("Demo manifest does not describe a desktop recording")
    for layer in _LAYERS:
        if not (vault_path / layer).is_dir():
            raise DemoPrivacyError(f"Demo memory layer is missing: {layer}")
    texts = [
        json.dumps(manifest, sort_keys=True),
        evidence_path.read_text(encoding="utf-8"),
        *[
            note.read_text(encoding="utf-8")
            for note in sorted(vault_path.rglob("*.md"))
        ],
    ]
    combined = "\n".join(texts)
    leaks = sorted(set(_EMAIL.findall(combined)))
    if leaks:
        raise DemoPrivacyError("Demo contains an identity email")
    if _SENT_CLAIM.search(combined):
        raise DemoPrivacyError("Demo incorrectly claims the invitation was sent")
    return {
        "scene_count": len(scenes),
        "identity_leaks": [],
        "memory_layers": len(_LAYERS),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("vault", type=Path)
    args = parser.parse_args()
    try:
        result = validate_demo_privacy(
            args.manifest.resolve(),
            args.evidence.resolve(),
            args.vault.resolve(),
        )
    except (DemoPrivacyError, ValueError) as error:
        parser.exit(1, f"demo privacy invalid: {error}\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
