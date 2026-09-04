"""Append-only Scout draft command/completion store for FR-906 and INV-1."""

from __future__ import annotations

from sqlalchemy import select

from ea_copilot.domain.errors import DraftCompletionError
from ea_copilot.domain.live_models import DraftCommand, DraftCompletion
from ea_copilot.domain.models import DraftEvent
from ea_copilot.services.database import (
    Database,
    draft_commands_table,
    draft_completions_table,
    metadata,
)
from ea_copilot.services.ids import stable_id


class DraftCommandStore:
    """Append commands and their idempotent completion results; never mutate them."""

    def __init__(self, database: Database) -> None:
        self._database = database
        metadata.create_all(database.engine)

    def _command_by_id(self, command_id: str) -> DraftCommand | None:
        with self._database.engine.connect() as connection:
            value = connection.scalar(
                select(draft_commands_table.c.data).where(
                    draft_commands_table.c.command_id == command_id
                )
            )
        return DraftCommand.model_validate_json(value) if value is not None else None

    def _command_by_transaction(self, transaction_id: str) -> DraftCommand | None:
        with self._database.engine.connect() as connection:
            value = connection.scalar(
                select(draft_commands_table.c.data).where(
                    draft_commands_table.c.transaction_id == transaction_id
                )
            )
        return DraftCommand.model_validate_json(value) if value is not None else None

    def append(self, command: DraftCommand) -> DraftCommand:
        existing = self._command_by_id(command.command_id)
        transaction = self._command_by_transaction(command.transaction_id)
        if existing is not None or transaction is not None:
            matched = existing or transaction
            if matched != command:
                raise DraftCompletionError("Draft command or transaction already has other data")
            return command
        with self._database.engine.begin() as connection:
            connection.execute(
                draft_commands_table.insert().values(
                    command_id=command.command_id,
                    transaction_id=command.transaction_id,
                    data=command.model_dump_json(),
                )
            )
        return command

    def all(self) -> list[DraftCommand]:
        with self._database.engine.connect() as connection:
            values = connection.scalars(
                select(draft_commands_table.c.data).order_by(draft_commands_table.c.sequence)
            ).all()
        return [DraftCommand.model_validate_json(value) for value in values]

    def _completed_event(self, transaction_id: str) -> DraftEvent | None:
        with self._database.engine.connect() as connection:
            value = connection.scalar(
                select(draft_completions_table.c.data).where(
                    draft_completions_table.c.transaction_id == transaction_id
                )
            )
        return DraftEvent.model_validate_json(value) if value is not None else None

    def pending(self) -> list[DraftCommand]:
        with self._database.engine.connect() as connection:
            completed = set(
                connection.scalars(select(draft_completions_table.c.transaction_id)).all()
            )
        return [command for command in self.all() if command.transaction_id not in completed]

    def complete(self, completion: DraftCompletion) -> DraftEvent:
        command = self._command_by_id(completion.command_id)
        if command is None:
            raise DraftCompletionError("Draft completion command does not exist")
        if command.transaction_id != completion.transaction_id:
            raise DraftCompletionError("Draft completion transaction does not match command")
        existing = self._completed_event(completion.transaction_id)
        if existing is not None:
            return existing
        event = DraftEvent(
            draft_id=stable_id("DRAFT", command.command_id),
            request_id=command.request_id,
            recommendation_id=command.recommendation_id,
            approval_id=command.approval_id,
            graph_event_id=completion.graph_event_id,
            web_link=completion.web_link,
            is_sent=False,
            created_at=completion.completed_at,
        )
        with self._database.engine.begin() as connection:
            connection.execute(
                draft_completions_table.insert().values(
                    command_id=completion.command_id,
                    transaction_id=completion.transaction_id,
                    data=event.model_dump_json(),
                )
            )
        return event
