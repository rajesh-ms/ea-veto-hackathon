"""Write-only Obsidian Markdown projection for FR-902 and FR-904."""

from __future__ import annotations

from pathlib import Path

from ea_copilot.domain.live_models import MemoryProjection, VaultProjectionResult

_LAYERS = {
    "Current Session": "01 Current Session",
    "Evidence History": "02 Evidence History",
    "Governed Memory": "03 Governed Memory",
}


class ObsidianVaultAdapter:
    """Project safe notes atomically; deliberately offers no read surface."""

    def __init__(self, vault_path: Path) -> None:
        self._vault_path = vault_path

    def _target(self, relative_path: str) -> Path:
        root = self._vault_path.resolve()
        target = (root / relative_path).resolve()
        if not target.is_relative_to(root):
            raise ValueError("Memory note must stay inside the configured vault")
        return target

    @staticmethod
    def _atomic_write(target: Path, content: str) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.tmp")
        try:
            temporary.write_text(content, encoding="utf-8", newline="\n")
            temporary.replace(target)
        finally:
            if temporary.exists():
                temporary.unlink()

    def project(self, projection: MemoryProjection) -> VaultProjectionResult:
        self._vault_path.mkdir(parents=True, exist_ok=True)
        for directory in _LAYERS.values():
            (self._vault_path / directory).mkdir(parents=True, exist_ok=True)

        written: list[str] = []
        for note in projection.notes:
            expected_root = _LAYERS[note.layer]
            if Path(note.relative_path).parts[0] != expected_root:
                raise ValueError(f"Memory note path does not match layer {note.layer}")
            target = self._target(note.relative_path)
            if note.append_only and target.exists():
                if target.read_text(encoding="utf-8") != note.markdown:
                    raise FileExistsError(f"Refusing to rewrite append-only memory note: {target}")
                continue
            self._atomic_write(target, note.markdown)
            written.append(note.relative_path)

        return VaultProjectionResult(
            vault_path=self._vault_path,
            layers=["Current Session", "Evidence History", "Governed Memory"],
            written_files=written,
        )
