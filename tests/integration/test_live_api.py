"""Aliased calendar and memory API tests for FR-902..FR-905."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ea_copilot.api.app import create_app
from ea_copilot.bootstrap import build_runtime

ROOT = Path(__file__).parents[2]
REQUESTER = {"entra_object_id": "demo-requester", "display_name": "Requester"}


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app(build_runtime(ROOT))) as test_client:
        yield test_client


def create_multi_exec_recommendation(client: TestClient) -> str:
    submitted = client.post(
        "/requests",
        json={
            "raw_text": (
                "Schedule a 45 minute strategic operating-plan decision with Dana, Marcus, "
                "and Priya before Friday."
            ),
            "requester": REQUESTER,
        },
    )
    request_id = submitted.json()["request"]["request_id"]
    response = client.get(f"/requests/{request_id}/recommendation")
    assert response.status_code == 200
    return request_id


def test_FR_903_calendar_route_returns_two_private_detail_free_alias_lanes(
    client: TestClient,
) -> None:
    request_id = create_multi_exec_recommendation(client)

    response = client.get(f"/live/requests/{request_id}/calendar")

    assert response.status_code == 200
    board = response.json()
    assert board["source"] == "fixture"
    assert [lane["alias"] for lane in board["lanes"]] == ["Exec A", "Exec B"]
    encoded = response.text
    assert "@humana-demo.com" not in encoded
    assert "Board preparation" not in encoded
    assert "Quarterly forecast" not in encoded


def test_FR_904_memory_route_returns_three_safe_layers(client: TestClient) -> None:
    request_id = create_multi_exec_recommendation(client)

    response = client.get(f"/live/requests/{request_id}/memory")

    assert response.status_code == 200
    projection = response.json()
    assert {note["layer"] for note in projection["notes"]} == {
        "Current Session",
        "Evidence History",
        "Governed Memory",
    }
    assert "@humana-demo.com" not in response.text


def test_FR_908_live_status_never_mislabels_default_fixture_runtime(client: TestClient) -> None:
    assert client.get("/live/status").json() == {
        "configured": False,
        "source": "fixture",
        "aliases": ["Exec A", "Exec B"],
        "scout": "integration available",
    }
