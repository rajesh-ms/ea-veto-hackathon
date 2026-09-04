"""SQLite storage foundation for FR-101, FR-701, FR-801, and NFR-01."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Column, Integer, MetaData, String, Table, Text, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

metadata = MetaData()

requests_table = Table(
    "requests",
    metadata,
    Column("request_id", String, primary_key=True),
    Column("status", String, nullable=False),
    Column("data", Text, nullable=False),
)

audit_table = Table(
    "audit_records",
    metadata,
    Column("sequence", Integer, primary_key=True, autoincrement=True),
    Column("audit_id", String, unique=True, nullable=False),
    Column("request_id", String, nullable=False, index=True),
    Column("recommendation_id", String, nullable=True, index=True),
    Column("action", String, nullable=False, index=True),
    Column("approval_id", String, nullable=True, index=True),
    Column("data", Text, nullable=False),
)

profiles_table = Table(
    "profile_versions",
    metadata,
    Column("sequence", Integer, primary_key=True, autoincrement=True),
    Column("executive_upn", String, nullable=False, index=True),
    Column("profile_version", String, nullable=False),
    Column("is_current", Integer, nullable=False),
    Column("data", Text, nullable=False),
)

candidates_table = Table(
    "candidate_rules",
    metadata,
    Column("candidate_id", String, primary_key=True),
    Column("executive_upn", String, nullable=False, index=True),
    Column("status", String, nullable=False),
    Column("data", Text, nullable=False),
)

evidence_table = Table(
    "feedback_evidence",
    metadata,
    Column("sequence", Integer, primary_key=True, autoincrement=True),
    Column("feedback_id", String, unique=True, nullable=False),
    Column("executive_upn", String, nullable=False, index=True),
    Column("created_at", String, nullable=False),
    Column("data", Text, nullable=False),
)

graph_evidence_table = Table(
    "graph_preference_evidence",
    metadata,
    Column("sequence", Integer, primary_key=True, autoincrement=True),
    Column("evidence_id", String, unique=True, nullable=False),
    Column("executive_upn", String, nullable=False, index=True),
    Column("observed_at", String, nullable=False),
    Column("data", Text, nullable=False),
)

draft_commands_table = Table(
    "draft_commands",
    metadata,
    Column("sequence", Integer, primary_key=True, autoincrement=True),
    Column("command_id", String, unique=True, nullable=False),
    Column("transaction_id", String, unique=True, nullable=False),
    Column("data", Text, nullable=False),
)

draft_completions_table = Table(
    "draft_completions",
    metadata,
    Column("sequence", Integer, primary_key=True, autoincrement=True),
    Column("command_id", String, unique=True, nullable=False),
    Column("transaction_id", String, unique=True, nullable=False),
    Column("data", Text, nullable=False),
)


@dataclass(frozen=True)
class Database:
    engine: Engine

    @classmethod
    def memory(cls) -> Database:
        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        metadata.create_all(engine)
        return cls(engine=engine)

    @classmethod
    def file(cls, path: str) -> Database:
        engine = create_engine(f"sqlite+pysqlite:///{path}")
        metadata.create_all(engine)
        return cls(engine=engine)
