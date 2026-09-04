"""Generate docs/08-test-cases.csv from docs/08-e2e-test-catalogue.md.

The markdown is the single source of truth. Re-run after editing the catalogue.
Usage:  python tools/gen_test_csv.py
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "08-e2e-test-catalogue.md"
OUT = ROOT / "docs" / "08-test-cases.csv"

SUITES = {
    "S1": "Scenario 1 - Single-executive scheduling",
    "S2": "Scenario 2 - Multi-executive scheduling",
    "S3": "Scenario 3 - Governed learning",
    "GOV": "Governance invariants",
    "SEC": "Prompt-injection defence",
    "AUD": "Audit and data",
    "NFR": "Non-functional",
}

HEADING = re.compile(r"^### (TC-[A-Z0-9]+-\d{3}) · (.+)$")
META = re.compile(r"^\*\*(P\d) · ([A-Za-z-]+) · Traces\*\* (.+)$")
INLINE_AUTO = re.compile(r"· \*\*Automation\*\* `([^`]+)`")
INLINE_DATA = re.compile(r"· \*\*Data\*\* (.+)$")
PRECOND = re.compile(r"^\*\*Precondition\*\*\s*(.+)$")
DATA = re.compile(r"^\*\*Data\*\*\s*(.+)$")
STEP = re.compile(r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$")
SEC_ROW = re.compile(
    r"^\|\s*\*\*(TC-SEC-\d{3})\*\*\s*\|\s*(P\d)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$"
)


def clean(text: str) -> str:
    """Strip markdown emphasis and code ticks for spreadsheet readability."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    return text.strip()


def main() -> int:
    if not SRC.exists():
        print(f"missing source: {SRC}", file=sys.stderr)
        return 1

    lines = SRC.read_text(encoding="utf-8").splitlines()
    cases: list[dict[str, str]] = []
    cur: dict[str, str] | None = None
    steps: list[str] = []
    expected: list[str] = []

    def flush() -> None:
        nonlocal cur, steps, expected
        if cur is not None:
            cur["Steps"] = "\n".join(steps)
            cur["Expected Result"] = "\n".join(expected)
            cases.append(cur)
        cur, steps, expected = None, [], []

    for line in lines:
        sec = SEC_ROW.match(line)
        if sec:
            flush()
            tc_id, pri, payload, exp = sec.groups()
            cases.append(
                {
                    "ID": tc_id,
                    "Title": f"Injection payload: {clean(payload)[:70]}",
                    "Suite": SUITES["SEC"],
                    "Priority": pri,
                    "Type": "Security",
                    "Preconditions": "Payload embedded in a retrieved calendar subject or mail body.",
                    "Test Data": clean(payload),
                    "Steps": (
                        "1. Embed the payload in a retrievable source\n"
                        "2. Build a recommendation for the affected request\n"
                        "3. Inspect the adapter write log\n"
                        "4. Inspect the audit trail for an InjectionAttempt record\n"
                        "5. Confirm the request status"
                    ),
                    "Expected Result": (
                        f"{clean(exp)}\n"
                        "Write log empty; InjectionAttempt recorded (except the benign control); "
                        "no tool call outside the read allow-list; request still reaches AwaitingEAReview."
                    ),
                    "Traces": "INV-6, FR-203",
                    "Automation": "tests/e2e/test_prompt_injection.py",
                }
            )
            continue

        h = HEADING.match(line)
        if h:
            flush()
            tc_id, title = h.groups()
            suite_key = tc_id.split("-")[1]
            cur = {
                "ID": tc_id,
                "Title": title.strip(),
                "Suite": SUITES.get(suite_key, suite_key),
                "Priority": "",
                "Type": "",
                "Preconditions": "",
                "Test Data": "",
                "Steps": "",
                "Expected Result": "",
                "Traces": "",
                "Automation": "",
            }
            continue

        if cur is None:
            continue

        m = META.match(line)
        if m:
            pri, typ, tail = m.groups()
            cur["Priority"] = pri
            cur["Type"] = typ

            auto = INLINE_AUTO.search(tail)
            if auto:
                cur["Automation"] = auto.group(1)
                tail = tail[: auto.start()]

            data = INLINE_DATA.search(tail)
            if data:
                cur["Test Data"] = clean(data.group(1))
                tail = tail[: data.start()]

            cur["Traces"] = clean(tail).rstrip("·").strip()
            continue

        p = PRECOND.match(line)
        if p:
            cur["Preconditions"] = clean(p.group(1))
            continue

        d = DATA.match(line)
        if d:
            cur["Test Data"] = clean(d.group(1))
            continue

        s = STEP.match(line)
        if s:
            num, action, exp = s.groups()
            if action.strip() in {"Action", "---"} or set(action.strip()) <= {"-"}:
                continue
            steps.append(f"{num}. {clean(action)}")
            expected.append(f"{num}. {clean(exp)}")

    flush()

    fields = [
        "ID", "Title", "Suite", "Priority", "Type",
        "Preconditions", "Test Data", "Steps", "Expected Result",
        "Traces", "Automation",
    ]
    with OUT.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(cases)

    by_suite: dict[str, int] = {}
    p1 = 0
    for c in cases:
        by_suite[c["Suite"]] = by_suite.get(c["Suite"], 0) + 1
        if c["Priority"] == "P1":
            p1 += 1

    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  cases : {len(cases)}  (P1: {p1})")
    for suite, n in by_suite.items():
        print(f"    {n:>3}  {suite}")

    missing = [c["ID"] for c in cases if not c["Priority"] or not c["Traces"]]
    if missing:
        print(f"\n  INCOMPLETE: {', '.join(missing)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
