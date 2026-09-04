"""Static workbench contract for FR-903, FR-904, and FR-909."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from ea_copilot.api.app import create_app
from ea_copilot.bootstrap import build_runtime

ROOT = Path(__file__).parents[2]


def test_FR_909_workbench_declares_calendar_memory_and_scout_surfaces() -> None:
    with TestClient(create_app(build_runtime(ROOT))) as client:
        page = client.get("/demo")

    assert page.status_code == 200
    for test_id in (
        "scout-status",
        "calendar-stage",
        "memory-stage",
        "memory-current-session",
        "memory-evidence-history",
        "memory-governed",
    ):
        assert f'data-testid="{test_id}"' in page.text
    assert "Exec A" in page.text
    assert "Exec B" in page.text
    assert "@humana-demo.com" not in page.text
