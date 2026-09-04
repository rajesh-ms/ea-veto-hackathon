"""Executable requirement-to-test manifest for NFR-06."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
TRACEABILITY: dict[str, set[str]] = {
    "tests/e2e/test_scenario_1_single_exec.py": set(
        "AC-S1-1 AC-S1-2 AC-S1-3 AC-S1-4 AC-S1-5 "
        "FR-101 FR-102 FR-103 FR-104 FR-105 FR-106 FR-107 "
        "FR-201 FR-202 FR-203 FR-204 FR-205".split()
    ),
    "tests/e2e/test_scenario_2_multi_exec.py": set(
        "AC-S2-1 AC-S2-2 AC-S2-3 AC-S2-4 AC-S2-5 "
        "FR-301 FR-302 FR-303 FR-304 FR-401 FR-402 FR-403 FR-404 FR-405 FR-406 FR-407 "
        "FR-501 FR-502 FR-503 FR-504 FR-505 FR-506 FR-507 FR-508".split()
    ),
    "tests/e2e/test_governance_invariants.py": set(
        "FR-601 FR-602 FR-603 FR-604 FR-605 FR-606 FR-607 FR-608 "
        "INV-1 INV-2 INV-3 INV-4 INV-5 INV-6".split()
    ),
    "tests/e2e/test_scenario_3_learning.py": set(
        "AC-S3-1 AC-S3-2 AC-S3-3 AC-S3-4 AC-S3-5 AC-S3-6 "
        "FR-701 FR-702 FR-703 FR-704 FR-705 FR-706 FR-707 FR-708 FR-709 FR-710 FR-711".split()
    ),
    "tests/e2e/test_live_extension_contract.py": set(
        "FR-901 FR-902 FR-903 FR-904 FR-905 FR-906 FR-907 FR-908 FR-909".split()
    ),
    "tests/unit/test_quality.py": set(
        "FR-801 FR-802 FR-803 FR-804 FR-805 "
        "NFR-01 NFR-02 NFR-03 NFR-04 NFR-05 NFR-06 NFR-07 NFR-08 NFR-09 NFR-10".split()
    ),
}


def test_every_requirement_has_a_named_test_NFR_06() -> None:
    requirements = (ROOT / "docs" / "01-requirements.md").read_text(encoding="utf-8")
    defined = set(re.findall(r"(?:INV-\d+|FR-\d{3}|NFR-\d{2}|AC-S\d-\d)", requirements))
    covered = set().union(*TRACEABILITY.values())
    assert covered == defined
    assert all((ROOT / path).parent.exists() for path in TRACEABILITY)
