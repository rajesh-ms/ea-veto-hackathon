"""Build a privacy-filtered Scout snapshot from delegated Work IQ getSchedule data."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
NODE = Path(r"C:\Program Files\Microsoft Scout\resources\node\node.exe")
WORKIQ = Path(
    r"C:\Program Files\Microsoft Scout\resources\app.asar.unpacked"
    r"\node_modules\@microsoft\workiq\bin\workiq.js"
)
CENTRAL = ZoneInfo("America/Chicago")
STATUS = {"0": "free", "1": "tentative", "2": "busy", "3": "oof", "4": "workingElsewhere"}


class SnapshotBuildError(RuntimeError):
    """The delegated Work IQ read did not produce a valid bounded snapshot."""


def _parse_datetime(value: str) -> datetime:
    normalized = value.removesuffix("Z")
    if "." in normalized:
        head, fraction = normalized.split(".", maxsplit=1)
        normalized = f"{head}.{fraction[:6]}"
    parsed = datetime.fromisoformat(normalized)
    return parsed.replace(tzinfo=CENTRAL).astimezone(UTC) if parsed.tzinfo is None else parsed


def _safe_id(*parts: object) -> str:
    raw = "|".join(str(part) for part in parts)
    return "GRAPH-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16].upper()


def _run_get_schedule(identifiers: list[str], start: datetime, end: datetime) -> dict[str, Any]:
    body = {
        "schedules": identifiers,
        "startTime": {
            "dateTime": start.astimezone(CENTRAL).replace(tzinfo=None).isoformat(),
            "timeZone": "Central Standard Time",
        },
        "endTime": {
            "dateTime": end.astimezone(CENTRAL).replace(tzinfo=None).isoformat(),
            "timeZone": "Central Standard Time",
        },
        "availabilityViewInterval": 30,
    }
    completed = subprocess.run(
        [
            str(NODE),
            str(WORKIQ),
            "do-action",
            "--url",
            "/me/calendar/getSchedule",
            "--body",
            json.dumps(body, separators=(",", ":")),
            "--log-level",
            "Error",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if completed.returncode != 0:
        raise SnapshotBuildError("Work IQ getSchedule failed")
    raw = completed.stdout
    first, last = raw.find("{"), raw.rfind("}")
    if first < 0 or last <= first:
        raise SnapshotBuildError("Work IQ getSchedule returned no JSON object")
    result = json.loads(raw[first : last + 1])
    if not isinstance(result, dict) or not isinstance(result.get("value"), list):
        raise SnapshotBuildError("Work IQ getSchedule response shape is invalid")
    return result


def _working_hours(value: dict[str, Any]) -> dict[str, Any]:
    zone = value.get("timeZone", {})
    zone_name = zone.get("name") if isinstance(zone, dict) else zone
    return {
        "days_of_week": [str(day).casefold() for day in value.get("daysOfWeek", [])],
        "start_time": str(value.get("startTime", "08:00:00")).split(".")[0],
        "end_time": str(value.get("endTime", "17:00:00")).split(".")[0],
        "time_zone": zone_name or "Central Standard Time",
    }


def build_snapshot(
    *,
    identities_path: Path,
    output: Path,
    request_id: str,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    identities = json.loads(identities_path.read_text(encoding="utf-8"))
    aliases = identities["aliases"]
    identifiers = [aliases["Exec A"], aliases["Exec B"]]
    start = datetime.combine(start_date, time(8), tzinfo=CENTRAL)
    end = datetime.combine(end_date, time(17), tzinfo=CENTRAL)
    response = _run_get_schedule(identifiers, start, end)
    by_identifier = {str(item.get("scheduleId", "")).casefold(): item for item in response["value"]}
    schedules: list[dict[str, Any]] = []
    events: dict[str, list[dict[str, Any]]] = {}
    evidence: list[dict[str, Any]] = []
    captured_at = datetime.now(UTC)
    for alias, identifier in zip(("Exec A", "Exec B"), identifiers, strict=True):
        item = by_identifier.get(identifier.casefold())
        if item is None:
            raise SnapshotBuildError(f"Delegated schedule missing for {alias}")
        view = str(item.get("availabilityView", ""))
        slots = []
        for index, code in enumerate(view):
            slot_start = start.astimezone(UTC) + timedelta(minutes=30 * index)
            slots.append(
                {
                    "start": slot_start.isoformat(),
                    "end": (slot_start + timedelta(minutes=30)).isoformat(),
                    "status": STATUS.get(code, "busy"),
                }
            )
        schedules.append(
            {
                "upn": identifier,
                "slots": slots,
                "working_hours": _working_hours(item.get("workingHours", {})),
                "access_limited": False,
            }
        )
        safe_events: list[dict[str, Any]] = []
        tuesday_afternoon: list[datetime] = []
        for schedule_item in item.get("scheduleItems", []):
            event_start = _parse_datetime(str(schedule_item["start"]["dateTime"]))
            event_end = _parse_datetime(str(schedule_item["end"]["dateTime"]))
            show_as = str(schedule_item.get("status", "busy"))
            if show_as not in {"free", "tentative", "busy", "oof", "workingElsewhere"}:
                show_as = "busy"
            safe_events.append(
                {
                    "event_id": _safe_id(alias, event_start, event_end),
                    "subject": "Busy",
                    "body_preview": "",
                    "start": event_start.isoformat(),
                    "end": event_end.isoformat(),
                    "show_as": show_as,
                    "is_movable": False,
                    "is_protected": False,
                    "location": None,
                    "organizer": None,
                    "attendees": [],
                }
            )
            local_start = event_start.astimezone(CENTRAL)
            if alias == "Exec A" and local_start.weekday() == 1 and local_start.hour >= 12:
                tuesday_afternoon.append(event_start)
        events[identifier] = safe_events
        for index, observed_at in enumerate(sorted(tuesday_afternoon)[:3]):
            evidence_id = _safe_id("preference", alias, observed_at, index)
            evidence.append(
                {
                    "evidence_id": evidence_id,
                    "executive_upn": identifier,
                    "dimension": "time_of_day",
                    "value": "tuesday_after_12",
                    "source": {
                        "source_id": evidence_id,
                        "source_type": "event",
                        "title": "Observed calendar time pattern",
                        "url": None,
                        "retrieved_at": captured_at.isoformat(),
                    },
                    "confidence": 0.8,
                    "observed_at": observed_at.isoformat(),
                }
            )
    snapshot = {
        "request_id": request_id,
        "captured_at": captured_at.isoformat(),
        "schedules": schedules,
        "events": events,
        "mail": [],
        "teams": [],
        "files": [],
        "limitations": [],
        "preference_evidence": evidence,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    temporary.replace(output)
    return {
        "aliases": ["Exec A", "Exec B"],
        "schedule_count": len(schedules),
        "preference_evidence_count": len(evidence),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--identities", type=Path, default=ROOT / ".local" / "live-identities.json"
    )
    parser.add_argument("--output", type=Path, default=ROOT / ".local" / "live-snapshot.json")
    parser.add_argument("--request-id", default="LIVE-PREFLIGHT")
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2026, 9, 7))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date(2026, 9, 11))
    args = parser.parse_args()
    try:
        result = build_snapshot(
            identities_path=args.identities.resolve(),
            output=args.output.resolve(),
            request_id=args.request_id,
            start_date=args.start_date,
            end_date=args.end_date,
        )
    except (SnapshotBuildError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        parser.exit(1, f"live snapshot failed: {error}\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
