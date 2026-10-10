"""DEC-15 step 10 — a server's authority grows only by the owner's review.

A connected MCP server re-enumerates its tools on every test and every new
session, and the stored list was simply replaced with whatever the server said
this time. So a server the owner had looked at and accepted with two harmless
tools could come back offering ``delete_repository``, or keep the name
``search`` and change what it tells the model the tool does, and the model was
offered the new thing on the next turn with nobody having seen it. A package
update cannot silently add grants (CAP-12); an MCP server is the same promise
for a thing that updates itself.

What the owner accepted is kept per tool as a fingerprint of its declaration —
name, title, the server's sentence about it and its input schema. A tool is
projected to the model only when its current declaration matches what was
accepted. Anything else is **held**: listed on the server's card as *new* or
*changed*, never offered, and refused if called, until the owner approves it.

Two cases approve without asking, because the owner is already the one acting:

* the first enumeration of a profile — the owner's own Test of a server they
  just added is where they see its tools;
* a profile written before this existed (``approved_tools`` is null) — what it
  stored was already being offered, and taking it away on upgrade would break
  working servers for a review nobody asked for. Its stored tools become the
  approved set the first time it is re-enumerated; only what changes after
  that is held.

Removed tools are simply absent from the next enumeration; their approval stays
in the record, so a tool that disappears and returns *unchanged* is not asked
about again.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any, Literal

from typing_extensions import TypedDict

__all__ = [
    "McpToolChanged",
    "PendingTool",
    "approved_tool_names",
    "decode_approved",
    "fingerprints",
    "pending_tools",
    "settle_approved",
]


class PendingTool(TypedDict):
    """One tool a server offers that the owner has not accepted as it is now."""

    name: str
    change: Literal["new", "changed"]
    description: str
    #: The declaration this card shows. Accepting sends it back, so what is
    #: accepted is what was read — not whatever the server says by then.
    fingerprint: str


class McpToolChanged(Exception):
    """A tool's declaration is no longer the one the owner was shown."""

    def __init__(self, names: list[str]) -> None:
        super().__init__(", ".join(names))
        self.names = names


def _declaration_map(tool_schemas: Iterable[Any] | None) -> dict[str, Mapping[str, Any]]:
    out: dict[str, Mapping[str, Any]] = {}
    for entry in tool_schemas or ():
        if isinstance(entry, Mapping) and isinstance(entry.get("name"), str):
            out[str(entry["name"])] = entry
    return out


def _fingerprint(name: str, declaration: Mapping[str, Any] | None) -> str:
    declared = declaration or {}
    payload = {
        "name": name,
        "title": declared.get("title") or "",
        "description": declared.get("description") or "",
        "input_schema": declared.get("input_schema"),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def fingerprints(tools: Iterable[Any] | None, tool_schemas: Iterable[Any] | None) -> dict[str, str]:
    """``{tool name: fingerprint of its declaration}`` for one enumeration."""
    declared = _declaration_map(tool_schemas)
    return {str(tool): _fingerprint(str(tool), declared.get(str(tool))) for tool in tools or ()}


def decode_approved(stored: Any) -> dict[str, str] | None:
    """The stored approval record, or ``None`` for a profile that predates it."""
    if stored is None:
        return None
    if isinstance(stored, str):
        try:
            stored = json.loads(stored)
        except ValueError:
            return {}
    if not isinstance(stored, Mapping):
        return {}
    return {str(name): str(value) for name, value in stored.items()}


def settle_approved(
    approved: Mapping[str, str] | None,
    *,
    previous_tools: Iterable[Any] | None,
    previous_schemas: Iterable[Any] | None,
    tools: Iterable[Any] | None,
    tool_schemas: Iterable[Any] | None,
) -> dict[str, str]:
    """The approval record to keep after an enumeration (see the module docstring).

    Never adds a tool the owner has not seen: a profile with a record keeps it
    unchanged. Only the two owner-acting cases fill one in.
    """
    if approved is not None:
        return dict(approved)
    previous = list(previous_tools or ())
    if previous:
        return fingerprints(previous, previous_schemas)
    return fingerprints(tools, tool_schemas)


def _effective(row: Mapping[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    current = fingerprints(row.get("tools"), row.get("tool_schemas"))
    approved = decode_approved(row.get("approved_tools"))
    return current, current if approved is None else approved


def approved_tool_names(row: Mapping[str, Any]) -> set[str]:
    """The tools of this profile the model may be offered: accepted as they are now."""
    current, approved = _effective(row)
    return {name for name, mark in current.items() if approved.get(name) == mark}


def pending_tools(row: Mapping[str, Any]) -> list[PendingTool]:
    """The tools held for review, new ones first, each with the server's own sentence."""
    current, approved = _effective(row)
    declared = _declaration_map(row.get("tool_schemas"))
    held: list[PendingTool] = []
    for name, mark in current.items():
        if approved.get(name) == mark:
            continue
        held.append(
            PendingTool(
                name=name,
                change="changed" if name in approved else "new",
                description=str((declared.get(name) or {}).get("description") or ""),
                fingerprint=mark,
            )
        )
    return sorted(held, key=lambda tool: (tool["change"] != "new", tool["name"]))
