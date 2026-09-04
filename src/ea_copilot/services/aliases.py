"""Presentation alias boundary for FR-902."""

from __future__ import annotations

import re
from types import MappingProxyType
from typing import Any

from ea_copilot.domain.live_models import ExecutiveAlias


class AliasDirectory:
    """Map private mailbox identifiers to the two public executive aliases."""

    def __init__(self, mapping: dict[str, str]) -> None:
        if set(mapping) != {"Exec A", "Exec B"}:
            raise ValueError("Alias mapping must contain exactly Exec A and Exec B")
        normalized = {alias: identifier.strip() for alias, identifier in mapping.items()}
        if not all(normalized.values()):
            raise ValueError("Mailbox identifiers must not be empty")
        if len({value.casefold() for value in normalized.values()}) != 2:
            raise ValueError("Exec A and Exec B require different mailbox identifiers")
        self._by_alias = MappingProxyType(normalized)
        self._by_identifier = MappingProxyType(
            {identifier.casefold(): alias for alias, identifier in normalized.items()}
        )

    @property
    def aliases(self) -> tuple[ExecutiveAlias, ExecutiveAlias]:
        return ("Exec A", "Exec B")

    def resolve(self, alias: ExecutiveAlias) -> str:
        return self._by_alias[alias]

    def alias_for(self, identifier: str) -> ExecutiveAlias:
        try:
            alias = self._by_identifier[identifier.casefold()]
        except KeyError as error:
            raise KeyError("Unknown executive identifier") from error
        if alias == "Exec A":
            return "Exec A"
        return "Exec B"

    def redact(self, value: Any) -> Any:
        if isinstance(value, str):
            redacted = value
            for alias, identifier in self._by_alias.items():
                redacted = re.sub(re.escape(identifier), alias, redacted, flags=re.IGNORECASE)
            return redacted
        if isinstance(value, dict):
            return {self.redact(key): self.redact(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.redact(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self.redact(item) for item in value)
        return value
