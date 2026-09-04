"""Resolve live aliases through Scout's Work IQ CLI without printing mailbox identities."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NODE = Path(r"C:\Program Files\Microsoft Scout\resources\node\node.exe")
DEFAULT_WORKIQ = Path(
    r"C:\Program Files\Microsoft Scout\resources\app.asar.unpacked"
    r"\node_modules\@microsoft\workiq\bin\workiq.js"
)
_EMAIL = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.IGNORECASE)


class IdentitySetupError(RuntimeError):
    """Scout could not resolve a complete safe local identity mapping."""


def _run(node: Path, workiq: Path, arguments: list[str]) -> str:
    completed = subprocess.run(
        [str(node), str(workiq), *arguments],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if completed.returncode != 0:
        raise IdentitySetupError("Scout Work IQ lookup failed")
    return completed.stdout


def _first_email(text: str) -> str:
    match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, re.IGNORECASE)
    if match is None:
        raise IdentitySetupError("Signed-in Scout account was not found")
    return match.group(0).casefold()


def _response_object(raw: str) -> dict[str, Any]:
    outer = json.loads(raw)
    response = outer.get("response")
    if not isinstance(response, str):
        raise IdentitySetupError("Scout Work IQ returned no response text")
    fenced = re.search(r"\{[\s\S]*\}", response)
    if fenced is None:
        raise IdentitySetupError("Scout Work IQ response did not contain JSON")
    value = json.loads(fenced.group(0))
    if not isinstance(value, dict):
        raise IdentitySetupError("Scout Work IQ identity result was not an object")
    return value


def configure(
    *,
    exec_a_name: str,
    exec_b_name: str,
    output: Path,
    node: Path = DEFAULT_NODE,
    workiq: Path = DEFAULT_WORKIQ,
) -> None:
    if not node.is_file() or not workiq.is_file():
        raise IdentitySetupError("Microsoft Scout Work IQ runtime was not found")
    self_identifier = _first_email(_run(node, workiq, ["config", "show"]))
    question = (
        "Resolve the Microsoft 365 work email addresses for the following two people in my "
        "organization. Return only a compact JSON object with keys exec_a and exec_b. "
        f"Exec A person: {exec_a_name}. Exec B person: {exec_b_name}."
    )
    identities = _response_object(
        _run(
            node,
            workiq,
            ["ask", "--json", "--log-level", "Error", "--question", question],
        )
    )
    exec_a = identities.get("exec_a")
    exec_b = identities.get("exec_b")
    if not isinstance(exec_a, str) or not _EMAIL.fullmatch(exec_a):
        raise IdentitySetupError("Scout did not return a valid Exec A mailbox")
    if not isinstance(exec_b, str) or not _EMAIL.fullmatch(exec_b):
        raise IdentitySetupError("Scout did not return a valid Exec B mailbox")
    if exec_a.casefold() == exec_b.casefold():
        raise IdentitySetupError("Exec A and Exec B resolved to the same mailbox")
    payload = {
        "aliases": {"Exec A": exec_a.casefold(), "Exec B": exec_b.casefold()},
        "self_identifier": self_identifier,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exec-a-name", required=True)
    parser.add_argument("--exec-b-name", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / ".local" / "live-identities.json")
    args = parser.parse_args()
    try:
        configure(
            exec_a_name=args.exec_a_name,
            exec_b_name=args.exec_b_name,
            output=args.output.resolve(),
        )
    except (IdentitySetupError, OSError, ValueError, json.JSONDecodeError) as error:
        parser.exit(1, f"identity setup failed: {error}\n")
    print(json.dumps({"configured": True, "aliases": ["Exec A", "Exec B"], "self": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
