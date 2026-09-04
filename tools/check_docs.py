"""Consistency check across the spec set: links, requirement IDs, diagram paths, test IDs."""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

md_files = sorted(DOCS.glob("*.md")) + [ROOT / "AGENTS.md", ROOT / "README.md"]
texts = {f: f.read_text(encoding="utf-8") for f in md_files}
errors: list[str] = []

ID_PAT = r"\b(FR-\d{3}|NFR-\d{2}|INV-\d|AC-S\d-\d)\b"

# 1. relative links resolve
for f, t in texts.items():
    for label, target in re.findall(r"\[([^\]]+)\]\(([^)]+)\)", t):
        if target.startswith(("http://", "https://", "#")):
            continue
        if not (f.parent / target.split("#")[0]).exists():
            errors.append(f"BROKEN LINK   {f.name}: [{label}]({target})")

# 2. every referenced requirement ID is defined
req = texts[DOCS / "01-requirements.md"]
defined = set(re.findall(ID_PAT, req))
for f, t in texts.items():
    if f.name == "01-requirements.md":
        continue
    for rid in set(re.findall(ID_PAT, t)):
        if rid not in defined:
            errors.append(f"UNDEFINED ID  {rid} in {f.name}")

# 3. every requirement is covered by a test or build gate
coverage_text = (
    texts[DOCS / "06-e2e-test-cases.md"]
    + texts[DOCS / "07-build-plan.md"]
    + texts[DOCS / "08-e2e-test-catalogue.md"]
)
covered = set(re.findall(ID_PAT, coverage_text))
for lo, hi in re.findall(r"FR-(\d{3})\s*(?:…|\.\.\.)\s*FR-(\d{3})", coverage_text):
    covered.update(f"FR-{n:03d}" for n in range(int(lo), int(hi) + 1))
for lo, hi in re.findall(r"NFR-(\d{2})\s*(?:…|\.\.\.)\s*NFR-(\d{2})", coverage_text):
    covered.update(f"NFR-{n:02d}" for n in range(int(lo), int(hi) + 1))
for lo, hi in re.findall(r"INV-(\d)\s*(?:…|\.\.\.)\s*(?:INV-)?(\d)", coverage_text):
    covered.update(f"INV-{n}" for n in range(int(lo), int(hi) + 1))

uncovered = sorted(defined - covered)
if uncovered:
    errors.append(f"UNCOVERED ({len(uncovered)}): {', '.join(uncovered)}")

# 4. images resolve
for f, t in texts.items():
    for target in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", t):
        if not (f.parent / target).exists():
            errors.append(f"MISSING IMAGE {f.name}: {target}")

# 5. CSV is in sync with the catalogue
cat = texts[DOCS / "08-e2e-test-catalogue.md"]
cat_ids = set(re.findall(r"\b(TC-[A-Z0-9]+-\d{3})\b", cat))
csv_path = DOCS / "08-test-cases.csv"
if csv_path.exists():
    csv_ids = {r["ID"] for r in csv.DictReader(csv_path.open(encoding="utf-8-sig"))}
    if missing := sorted(cat_ids - csv_ids):
        errors.append(f"CSV MISSING: {', '.join(missing)}  (run tools/gen_test_csv.py)")
    if extra := sorted(csv_ids - cat_ids):
        errors.append(f"CSV EXTRA:   {', '.join(extra)}")
else:
    errors.append("CSV MISSING entirely (run tools/gen_test_csv.py)")
    csv_ids = set()

print(f"docs            : {len(md_files)}")
print(f"requirement IDs : {len(defined)} defined, {len(defined) - len(uncovered)} covered")
print(f"test cases      : {len(cat_ids)} in catalogue, {len(csv_ids)} in CSV")
print()
if errors:
    for e in errors:
        print("  " + e)
    sys.exit(1)
print("OK - spec set is internally consistent")
