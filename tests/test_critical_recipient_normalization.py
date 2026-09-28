"""CR-11 — a send's recipients are read wherever they are, and never assumed absent.

Criterion (b) extracted destinations from seven flat keys. A connector that
nested its recipients or used another name produced an empty set, and an empty
set read as "sends to nobody" — not critical. These tests hold the canonical
walk and the fail-closed branch for a destination that cannot be resolved.
"""
from __future__ import annotations

from typing import Any

import pytest

from raiker.runtime.authority.critical import (
    CRITICAL_EXTERNAL_SEND_UNLISTED,
    CRITICAL_EXTERNAL_SEND_UNRESOLVED,
    _recipients,
    classify_critical,
)

_ALLOW = ["*@my-company.com"]


@pytest.mark.parametrize(
    "arguments",
    [
        {"message": {"to": "stranger@example.com"}},
        {"attendees": [{"email": "stranger@example.com"}]},
        {"toRecipients": [{"emailAddress": {"address": "stranger@example.com"}}]},
        {"to": "Boss <boss@my-company.com>, stranger@example.com"},
        {"invitees": ["boss@my-company.com", "stranger@example.com"]},
        {"payload": [{"cc": ["stranger@example.com"]}]},
    ],
)
def test_a_nested_or_renamed_stranger_is_still_found(arguments: dict[str, Any]) -> None:
    match = classify_critical("email_send", "", arguments, recipient_allowlist=_ALLOW)
    assert match is not None
    assert match.code == CRITICAL_EXTERNAL_SEND_UNLISTED


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"body": "hello"},
        {"to": ""},
        {"to": []},
        {"message": {"subject": "no destination"}},
    ],
)
def test_a_send_with_no_readable_destination_fails_closed(arguments: dict[str, Any]) -> None:
    match = classify_critical("email_send", "", arguments, recipient_allowlist=_ALLOW)
    assert match is not None
    assert match.code == CRITICAL_EXTERNAL_SEND_UNRESOLVED


def test_an_unreadable_recipient_beside_a_listed_one_is_not_waved_through() -> None:
    match = classify_critical(
        "calendar_invite",
        "",
        {"attendees": [{"email": "boss@my-company.com"}, {"name": "No Address"}]},
        recipient_allowlist=_ALLOW,
    )
    assert match is not None
    assert match.code == CRITICAL_EXTERNAL_SEND_UNLISTED


def test_every_listed_recipient_anywhere_is_still_not_critical() -> None:
    arguments = {
        "message": {
            "toRecipients": [{"emailAddress": {"address": "boss@my-company.com"}}],
            "cc": "Team <team@my-company.com>",
        }
    }
    assert classify_critical("email_send", "", arguments, recipient_allowlist=_ALLOW) is None


def test_the_walk_is_bounded() -> None:
    deep: dict[str, Any] = {"to": "boss@my-company.com"}
    for _ in range(40):
        deep = {"wrap": deep}
    # Too deep to read is unresolved, never a pass.
    match = classify_critical("email_send", "", deep, recipient_allowlist=_ALLOW)
    assert match is not None


def test_the_detail_never_carries_an_address() -> None:
    match = classify_critical("email_send", "", {"to": "stranger@example.com"})
    assert match is not None
    assert "@" not in match.detail


def test_recipients_flattens_the_canonical_list() -> None:
    assert sorted(
        _recipients({"to": "a@x.io; b@y.io", "message": {"bcc": [{"address": "c@z.io"}]}})
    ) == ["a@x.io", "b@y.io", "c@z.io"]


def test_a_non_send_action_is_not_asked_for_recipients() -> None:
    assert classify_critical("write_file", "", {"path": "a.txt"}) is None
