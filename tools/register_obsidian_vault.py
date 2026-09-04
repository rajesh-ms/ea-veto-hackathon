"""Register the generated demo vault in Obsidian with a backed-up local config edit."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def register(vault: Path, config: Path) -> str:
    resolved = vault.resolve()
    if not resolved.is_dir():
        raise ValueError(f"Vault directory does not exist: {resolved}")
    required = ["01 Current Session", "02 Evidence History", "03 Governed Memory"]
    if any(not (resolved / layer).is_dir() for layer in required):
        raise ValueError("Vault does not contain all three memory layers")
    config.parent.mkdir(parents=True, exist_ok=True)
    if config.is_file():
        backup = config.with_name(f"{config.name}.backup-{int(time.time() * 1000)}")
        shutil.copy2(config, backup)
        value = json.loads(config.read_text(encoding="utf-8-sig"))
    else:
        value = {"vaults": {}}
    vaults = value.setdefault("vaults", {})
    if not isinstance(vaults, dict):
        raise ValueError("Obsidian vault registry has an invalid shape")
    for entry in vaults.values():
        if isinstance(entry, dict):
            entry["open"] = False
    vault_id = hashlib.sha256(str(resolved).casefold().encode("utf-8")).hexdigest()[:16]
    vaults[vault_id] = {
        "path": str(resolved),
        "ts": int(time.time() * 1000),
        "open": True,
    }
    temporary = config.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, separators=(",", ":")), encoding="utf-8")
    temporary.replace(config)
    return vault_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=ROOT / "demo-vault")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(os.environ["APPDATA"]) / "obsidian" / "obsidian.json",
    )
    args = parser.parse_args()
    try:
        register(args.vault, args.config)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.exit(1, f"vault registration failed: {error}\n")
    print(json.dumps({"registered": True, "vault": "EA Copilot Demo"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
