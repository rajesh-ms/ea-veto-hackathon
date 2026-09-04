"""Recording and privacy validator tests for FR-902 and FR-909."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.verify_demo_privacy import DemoPrivacyError, validate_demo_privacy
from tools.verify_demo_video import VideoValidationError, validate_container

REQUIRED_SCENES = [
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
]


def test_video_validator_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(VideoValidationError, match="does not exist"):
        validate_container(tmp_path / "missing.webm")


def test_video_validator_rejects_non_webm_bytes(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.webm"
    path.write_bytes(b"not a video" * 20_000)
    with pytest.raises(VideoValidationError, match="EBML"):
        validate_container(path)


def write_privacy_world(tmp_path: Path) -> tuple[Path, Path, Path]:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "recording_type": "desktop",
                "aliases": ["Exec A", "Exec B"],
                "scenes": REQUIRED_SCENES,
                "calendar_action": "unsent draft",
            }
        ),
        encoding="utf-8",
    )
    evidence = tmp_path / "evidence.json"
    evidence.write_text(
        (Path(__file__).parents[2] / "tests/fixtures/live/scout-evidence-valid.json").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    vault = tmp_path / "vault"
    for layer in ("01 Current Session", "02 Evidence History", "03 Governed Memory"):
        directory = vault / layer
        directory.mkdir(parents=True)
        (directory / "note.md").write_text("Exec A and Exec B demo note", encoding="utf-8")
    return manifest, evidence, vault


def test_FR_909_privacy_validator_accepts_complete_redacted_demo(tmp_path: Path) -> None:
    manifest, evidence, vault = write_privacy_world(tmp_path)

    result = validate_demo_privacy(manifest, evidence, vault)

    assert result["scene_count"] == 10
    assert result["identity_leaks"] == []
    assert result["memory_layers"] == 3


@pytest.mark.parametrize(
    "mutation, message",
    [("missing", "scene"), ("email", "identity"), ("sent", "sent")],
)
def test_FR_909_privacy_validator_rejects_incomplete_or_unsafe_demo(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    manifest, evidence, vault = write_privacy_world(tmp_path)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if mutation == "missing":
        data["scenes"] = data["scenes"][:-1]
    elif mutation == "email":
        data["debug"] = "person@example.invalid"
    else:
        data["calendar_action"] = "invitation sent"
    manifest.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(DemoPrivacyError, match=message):
        validate_demo_privacy(manifest, evidence, vault)
