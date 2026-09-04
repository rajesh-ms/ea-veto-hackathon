"""Alias and recursive redaction tests for FR-902 and NFR-09."""

from __future__ import annotations

import pytest

from ea_copilot.services.aliases import AliasDirectory


def test_FR_902_alias_directory_resolves_both_executives_without_exposing_ids() -> None:
    directory = AliasDirectory(
        {"Exec A": "alpha-mailbox-id", "Exec B": "beta-mailbox-id"}
    )

    assert directory.resolve("Exec A") == "alpha-mailbox-id"
    assert directory.resolve("Exec B") == "beta-mailbox-id"
    assert directory.alias_for("ALPHA-MAILBOX-ID") == "Exec A"


def test_FR_902_redaction_recurses_through_public_payloads() -> None:
    directory = AliasDirectory(
        {"Exec A": "alpha-mailbox-id", "Exec B": "beta-mailbox-id"}
    )
    payload = {
        "people": ["alpha-mailbox-id", "beta-mailbox-id"],
        "summary": "alpha-mailbox-id and beta-mailbox-id are available",
        "nested": ("ALPHA-MAILBOX-ID", {"owner": "beta-mailbox-id"}),
    }

    assert directory.redact(payload) == {
        "people": ["Exec A", "Exec B"],
        "summary": "Exec A and Exec B are available",
        "nested": ("Exec A", {"owner": "Exec B"}),
    }


@pytest.mark.parametrize(
    "mapping, message",
    [
        ({"Exec A": "alpha-mailbox-id"}, "exactly Exec A and Exec B"),
        (
            {
                "Exec A": "same-mailbox-id",
                "Exec B": "same-mailbox-id",
            },
            "different mailbox identifiers",
        ),
        (
            {
                "Exec A": "alpha-mailbox-id",
                "Exec B": "beta-mailbox-id",
                "Exec C": "gamma-mailbox-id",
            },
            "exactly Exec A and Exec B",
        ),
    ],
)
def test_FR_902_alias_directory_rejects_ambiguous_or_extra_mappings(
    mapping: dict[str, str], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        AliasDirectory(mapping)
