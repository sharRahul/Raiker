"""ADR-0005 — what the persona routes answer with."""

from __future__ import annotations

from typing_extensions import TypedDict


class PersonaView(TypedDict):
    persona_id: str
    #: The text after `@`; letters and digits, unique per account.
    name: str
    description: str
    instructions: str
    model_profile: str | None
    model: str | None
    #: `None` inherits the turn's tools; a list is the families it keeps.
    tool_ceiling: list[str] | None
    #: The SHA-256 a turn records, so an older turn can say it ran an earlier version.
    instructions_sha256: str
    created_at: str
    updated_at: str


class PersonaFamily(TypedDict):
    family: str
    label: str


class PersonaList(TypedDict):
    personas: list[PersonaView]
    #: The tool families a ceiling may keep, in the order the form lists them.
    families: list[PersonaFamily]


class PersonaRemoved(TypedDict):
    ok: bool
    persona_id: str
