# SPDX-License-Identifier: Apache-2.0
"""What web access may not reach, and the rules' sources."""

from __future__ import annotations

from typing import Any, Literal

from typing_extensions import TypedDict


class WebBlocklistRule(TypedDict):
    rule_id: str
    rule: str
    kind: str
    note: str
    created_at: str


def blocklist_rule(row: dict[str, Any]) -> WebBlocklistRule:
    """A stored rule as the page reads it: the rule, not who owns the row."""
    return {
        "rule_id": str(row["rule_id"]),
        "rule": str(row["rule"]),
        "kind": str(row["kind"]),
        "note": str(row.get("note") or ""),
        "created_at": str(row["created_at"]),
    }


class AddressGuard(TypedDict):
    """The private-address refusal: always on, and not a setting."""

    enforced: bool
    editable: bool
    description: str


class WebBlocklist(TypedDict):
    """The rules in force, by source, so the page knows which it may delete."""

    stored: list[WebBlocklistRule]
    environment: list[str]
    environment_variable: str
    builtin: list[str]
    effective_count: int
    address_guard: AddressGuard


class BlocklistRuleAdded(TypedDict):
    rule_id: str
    rule: str
    kind: str


class BlocklistRuleDeleted(TypedDict):
    deleted: bool


class BlocklistProbe(TypedDict):
    """Would this host be reachable, said without fetching it."""

    host: str
    allowed: bool
    reason: str
    addresses: list[str]
    #: DEC-21 — the refusal in the owner's words; empty when it is reachable.
    explanation: str
    #: The blocklist rule that refused it, as written, or null.
    rule: str | None
    #: Where that rule comes from: ``built_in``, ``environment`` or ``yours``.
    rule_source: Literal["built_in", "environment", "yours"] | None
