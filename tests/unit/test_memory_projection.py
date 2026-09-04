"""Obsidian vault adapter tests for FR-902 and FR-904."""

from __future__ import annotations

from pathlib import Path

import pytest

from ea_copilot.adapters.obsidian_vault import ObsidianVaultAdapter
from ea_copilot.domain.live_models import MemoryNote, MemoryProjection


def projection(current_body: str = "Current body") -> MemoryProjection:
    return MemoryProjection(
        request_id="REQ-MEMORY-1",
        notes=[
            MemoryNote(
                layer="Current Session",
                relative_path="01 Current Session/REQ-MEMORY-1.md",
                title="Current Session",
                markdown=current_body,
                append_only=False,
            ),
            MemoryNote(
                layer="Evidence History",
                relative_path="02 Evidence History/2026-09-14/AUD-1.md",
                title="Evidence AUD-1",
                markdown="Evidence body",
                append_only=True,
            ),
            MemoryNote(
                layer="Governed Memory",
                relative_path="03 Governed Memory/Exec A/profile-v1.md",
                title="Exec A profile v1",
                markdown="Governed body",
                append_only=True,
            ),
        ],
    )


def test_FR_904_vault_adapter_creates_exactly_three_layers(tmp_path: Path) -> None:
    vault = ObsidianVaultAdapter(tmp_path / "demo-vault")

    result = vault.project(projection())

    assert result.layers == ["Current Session", "Evidence History", "Governed Memory"]
    assert {path.name for path in result.vault_path.iterdir()} == {
        "01 Current Session",
        "02 Evidence History",
        "03 Governed Memory",
    }
    assert len(result.written_files) == 3
    assert not hasattr(vault, "read")


def test_FR_904_current_session_replaces_but_evidence_and_governed_are_append_only(
    tmp_path: Path,
) -> None:
    vault = ObsidianVaultAdapter(tmp_path / "demo-vault")
    vault.project(projection())

    vault.project(projection("Updated current body"))
    current = tmp_path / "demo-vault" / "01 Current Session" / "REQ-MEMORY-1.md"
    assert current.read_text(encoding="utf-8") == "Updated current body"

    changed = projection().model_copy(
        update={
            "notes": [
                projection().notes[0],
                projection().notes[1].model_copy(update={"markdown": "Rewritten evidence"}),
                projection().notes[2],
            ]
        }
    )
    with pytest.raises(FileExistsError, match="append-only memory note"):
        vault.project(changed)
