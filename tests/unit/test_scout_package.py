"""Scout package and transcript guard tests for FR-906 and FR-907."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from ea_copilot.domain.errors import ScoutSequenceError
from ea_copilot.domain.live_models import ScoutToolCall
from ea_copilot.services.scout_transcript import validate_scout_transcript

ROOT = Path(__file__).parents[2]


def valid_calls() -> list[ScoutToolCall]:
    return [
        ScoutToolCall(name="ea_submit_request", arguments={}),
        ScoutToolCall(name="ea_attach_snapshot", arguments={}),
        ScoutToolCall(name="ea_get_recommendation", arguments={}),
        ScoutToolCall(name="ea_record_decision", arguments={"decision": "approve"}),
        ScoutToolCall(name="ea_prepare_draft", arguments={}),
        ScoutToolCall(
            name="workiq_create_event",
            arguments={
                "subject": "[DEMO] Executive scheduling prototype",
                "draft": True,
                "attendees": [{"address": "signed-in-user"}],
            },
        ),
        ScoutToolCall(name="ea_complete_draft", arguments={"draft": True}),
    ]


def test_FR_906_transcript_guard_accepts_only_approval_then_literal_draft_true() -> None:
    result = validate_scout_transcript(valid_calls())

    assert result.valid is True
    assert result.draft is True
    assert result.attendee_count == 1
    assert result.forbidden_tools == []


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda calls: calls[3:], "tool sequence"),
        (
            lambda calls: [
                call.model_copy(update={"arguments": {**call.arguments, "draft": False}})
                if call.name == "workiq_create_event"
                else call
                for call in calls
            ],
            "draft=true",
        ),
        (
            lambda calls: [
                *calls[:5],
                ScoutToolCall(name="workiq_update_event", arguments={}),
                *calls[5:],
            ],
            "forbidden calendar tool",
        ),
    ],
)
def test_FR_906_transcript_guard_rejects_bypasses(mutate, message: str) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ScoutSequenceError, match=message):
        validate_scout_transcript(mutate(valid_calls()))


def test_FR_907_installer_merges_stdio_server_without_credentials(tmp_path: Path) -> None:
    state_root = tmp_path / "scout"
    state_root.mkdir()
    store = state_root / "m-mcp-servers.json"
    store.write_text(
        json.dumps({"servers": {"filesystem": {"builtin": True, "tools": []}}}),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "tools" / "install_scout_integration.ps1"),
            "-StateRoot",
            str(state_root),
            "-RepositoryRoot",
            str(ROOT),
            "-PythonExe",
            "python",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    saved = json.loads(store.read_text(encoding="utf-8"))
    assert saved["servers"]["filesystem"]["builtin"] is True
    entry = saved["servers"]["ea-copilot"]
    assert entry == {
        "builtin": False,
        "config": {
            "name": "EA Copilot",
            "type": "stdio",
            "command": "python",
            "args": ["-m", "ea_copilot.integrations"],
            "timeout": 300000,
        },
        "tools": [],
    }
    encoded = json.dumps(saved).casefold()
    assert "clientid" not in encoded
    assert "accesstoken" not in encoded
    assert "refreshtoken" not in encoded
    assert (state_root / "skills" / "ea-copilot" / "SKILL.md").is_file()
