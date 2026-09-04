"""Append-only Graph preference evidence for FR-905 and INV-3."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from ea_copilot.domain.live_models import GraphPreferenceEvidence
from ea_copilot.services.database import Database, graph_evidence_table, metadata


class LiveEvidenceStore:
    """Store Graph observations separately from approved profile memory."""

    def __init__(self, database: Database) -> None:
        self._database = database
        self.read_log: list[str] = []
        metadata.create_all(database.engine)

    def append(self, evidence: GraphPreferenceEvidence) -> GraphPreferenceEvidence:
        with self._database.engine.begin() as connection:
            connection.execute(
                graph_evidence_table.insert().values(
                    evidence_id=evidence.evidence_id,
                    executive_upn=evidence.executive_upn,
                    observed_at=evidence.observed_at.isoformat(),
                    data=evidence.model_dump_json(),
                )
            )
        return evidence

    def _read(self, executive_upn: str | None = None) -> list[GraphPreferenceEvidence]:
        statement = select(graph_evidence_table.c.data)
        if executive_upn is not None:
            statement = statement.where(graph_evidence_table.c.executive_upn == executive_upn)
        statement = statement.order_by(graph_evidence_table.c.sequence)
        with self._database.engine.connect() as connection:
            values = connection.scalars(statement).all()
        return [GraphPreferenceEvidence.model_validate_json(value) for value in values]

    def for_executive(self, executive_upn: str) -> list[GraphPreferenceEvidence]:
        self.read_log.append(f"for_executive:{executive_upn}")
        return self._read(executive_upn)

    def in_window(
        self, executive_upn: str, start: datetime, end: datetime
    ) -> list[GraphPreferenceEvidence]:
        self.read_log.append(f"in_window:{executive_upn}")
        return [
            item
            for item in self._read(executive_upn)
            if start <= item.observed_at <= end
        ]

    def all(self) -> list[GraphPreferenceEvidence]:
        self.read_log.append("all")
        return self._read()
