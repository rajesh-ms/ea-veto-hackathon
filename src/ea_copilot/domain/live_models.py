"""Live Scout and presentation contracts for FR-901..FR-909."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from ea_copilot.domain.models import DomainModel, TimeSlot

ExecutiveAlias = Literal["Exec A", "Exec B"]
CalendarSource = Literal["fixture", "live_via_scout"]


class CalendarBlock(DomainModel):
    """One privacy-filtered block shown on an executive lane."""

    block_id: str
    start: datetime
    end: datetime
    category: Literal["busy", "protected", "travel", "preparation", "candidate"]
    label: str


class CalendarLane(DomainModel):
    """Presentation-only calendar lane keyed by alias."""

    alias: ExecutiveAlias
    blocks: list[CalendarBlock] = Field(default_factory=list)
    access_limited: bool = False
    limitation: str | None = None


class CalendarBoard(DomainModel):
    """Two-lane calendar projection with no private calendar text."""

    request_id: str
    source: CalendarSource
    lanes: list[CalendarLane]
    candidate_slots: list[TimeSlot] = Field(default_factory=list)
