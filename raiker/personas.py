# SPDX-License-Identifier: Apache-2.0
"""Composer personas — `@DataAnalyst` narrows a turn and never widens it (ADR-0005).

A persona is an owner-authored record: a **name** (the text after ``@``), a
one-line **description**, **standing instructions**, an optional **default
model** and an optional **tool ceiling** — a subset of :data:`FAMILIES`.

The rule this module exists to keep is ADR-0005 §2: a persona is one more
*narrowing* override. Two things make that true here rather than in prose:

* :func:`ceiling_capability_modes` turns the families a persona leaves out
  into ``deny`` entries of the turn's ``capability_modes`` — the tighten-only
  map the envelope already validates and the broker already honours, so a
  persona arrives as an override the authority path already intersects.
* :func:`excluded_tools` names the tools of those families so the turn does
  not even *offer* them to the model (a read such as ``read_file`` has no gate
  to deny, so withholding it is the only way to keep it out of the turn).

A ceiling can only list known families; nothing here can add a tool, a
capability or a mode that is not already the turn's.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from raiker.contracts.ids import new_id, utc_now

#: The tool families a ceiling can keep, each with the tools it covers and the
#: capabilities a turn without it is denied. Tools outside every family (the
#: planning, question and help tools) are never withheld: they reach nothing.
FAMILIES: dict[str, dict[str, tuple[str, ...]]] = {
    "files": {
        "tools": (
            "read_file", "list_directory", "stat_path", "glob", "grep", "diff_files",
            "write_file", "edit_file", "apply_patch", "create_document",
            "code_map_search", "code_map_references", "document_symbols",
            "find_definition", "diagnostics",
        ),
        "capabilities": ("file_write_execution", "patch_apply_execution", "code_map_indexing", "language_intelligence"),
    },
    "web": {
        "tools": ("web_search", "web_fetch", "web_extract", "weather_lookup"),
        "capabilities": ("web_fetch",),
    },
    "messages": {
        "tools": (
            "connector_read", "connector_write", "gmail_read", "outlook_read",
            "slack_read", "gcal_read", "suggest_connection",
        ),
        "capabilities": (
            "connector_gmail_runtime", "connector_outlook_runtime", "connector_slack_runtime",
            "connector_gcal_runtime", "email_runtime", "calendar_runtime", "external_channel_runtime",
        ),
    },
    "memory": {
        "tools": ("memory_search", "memory_get", "memory_list", "memory_write", "memory_forget", "conversation_search"),
        "capabilities": ("memory_write_execution", "memory_forget_execution", "semantic_memory_runtime"),
    },
    "git": {
        "tools": (
            "git_status", "git_diff", "git_log", "git_branch", "git_commit", "git_fetch",
            "git_clone", "git_push", "github_read", "github_write",
        ),
        "capabilities": (
            "git_write_execution", "git_fetch_execution", "git_push_execution", "connector_github_runtime",
        ),
    },
    "commands": {
        "tools": ("shell", "run_command", "background_run", "remote_execute", "cloud_execute", "spawn_subagent"),
        "capabilities": (
            "shell_execution", "process_execution", "remote_execution_cap", "cloud_execution_cap", "subagents",
        ),
    },
}

FAMILY_LABELS: dict[str, str] = {
    "files": "Files",
    "web": "Web",
    "messages": "Messages and calendars",
    "memory": "Memory",
    "git": "Git and GitHub",
    "commands": "Commands",
}

MAX_INSTRUCTIONS = 4000
MAX_DESCRIPTION = 200
MAX_PERSONAS = 50
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,39}$")


class PersonaError(ValueError):
    """A persona that cannot be saved; ``code`` is the stable reason."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Persona:
    persona_id: str
    name: str
    description: str
    instructions: str
    model_profile: str | None
    model: str | None
    #: ``None`` inherits the turn's tools; a tuple is the families it keeps.
    tool_ceiling: tuple[str, ...] | None
    created_at: str
    updated_at: str

    @property
    def instructions_sha256(self) -> str:
        return hashlib.sha256(self.instructions.encode("utf-8")).hexdigest()

    def public(self) -> dict[str, Any]:
        return {
            "persona_id": self.persona_id,
            "name": self.name,
            "description": self.description,
            "instructions": self.instructions,
            "model_profile": self.model_profile,
            "model": self.model,
            "tool_ceiling": list(self.tool_ceiling) if self.tool_ceiling is not None else None,
            "instructions_sha256": self.instructions_sha256,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def _row(row: Mapping[str, Any]) -> Persona:
    raw = row["tool_ceiling_json"]
    ceiling: tuple[str, ...] | None = None
    if raw is not None:
        try:
            parsed = json.loads(raw)
        except ValueError:
            parsed = []
        # A stored family this build no longer knows narrows to nothing, never widens.
        ceiling = tuple(name for name in parsed if name in FAMILIES) if isinstance(parsed, list) else ()
    return Persona(
        persona_id=str(row["persona_id"]),
        name=str(row["name"]),
        description=str(row["description"] or ""),
        instructions=str(row["instructions"] or ""),
        model_profile=(str(row["model_profile"]) if row["model_profile"] else None),
        model=(str(row["model"]) if row["model"] else None),
        tool_ceiling=ceiling,
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def validate_ceiling(value: object) -> tuple[str, ...] | None:
    """``None`` (inherit) or a de-duplicated tuple of known families, in catalogue order."""
    if value is None:
        return None
    if not isinstance(value, list | tuple) or not all(isinstance(item, str) for item in value):
        raise PersonaError("invalid_tool_ceiling")
    unknown = [item for item in value if item not in FAMILIES]
    if unknown:
        raise PersonaError(f"unknown_tool_family:{unknown[0]}")
    return tuple(name for name in FAMILIES if name in set(value))


def _clean(fields: Mapping[str, Any]) -> dict[str, Any]:
    name = str(fields.get("name") or "").strip().lstrip("@")
    if not _NAME.match(name):
        raise PersonaError("invalid_persona_name")
    description = " ".join(str(fields.get("description") or "").split())
    if len(description) > MAX_DESCRIPTION:
        raise PersonaError("persona_description_too_long")
    instructions = str(fields.get("instructions") or "").strip()
    if not instructions:
        raise PersonaError("persona_instructions_required")
    if len(instructions) > MAX_INSTRUCTIONS:
        raise PersonaError("persona_instructions_too_long")
    model_profile = str(fields.get("model_profile") or "").strip() or None
    model = str(fields.get("model") or "").strip() or None
    if model and not model_profile:
        raise PersonaError("persona_model_needs_profile")
    return {
        "name": name,
        "description": description,
        "instructions": instructions,
        "model_profile": model_profile,
        "model": model,
        "tool_ceiling": validate_ceiling(fields.get("tool_ceiling")),
    }


def list_personas(store: Any, user_id: str) -> list[Persona]:
    with store.connect() as connection:
        rows = connection.execute(
            "SELECT * FROM personas WHERE user_id = ? ORDER BY name COLLATE NOCASE", (user_id,)
        ).fetchall()
    return [_row(row) for row in rows]


def get_persona(store: Any, user_id: str, persona_id: str) -> Persona | None:
    with store.connect() as connection:
        row = connection.execute(
            "SELECT * FROM personas WHERE user_id = ? AND persona_id = ?", (user_id, persona_id)
        ).fetchone()
    return _row(row) if row is not None else None


def _name_taken(connection: Any, user_id: str, name: str, persona_id: str | None) -> bool:
    row = connection.execute(
        "SELECT persona_id FROM personas WHERE user_id = ? AND lower(name) = lower(?)", (user_id, name)
    ).fetchone()
    return row is not None and str(row["persona_id"]) != (persona_id or "")


def create_persona(store: Any, user_id: str, fields: Mapping[str, Any]) -> Persona:
    clean = _clean(fields)
    now = utc_now()
    persona_id = new_id("persona_")
    with store.connect() as connection:
        count = connection.execute("SELECT count(*) FROM personas WHERE user_id = ?", (user_id,)).fetchone()[0]
        if int(count) >= MAX_PERSONAS:
            raise PersonaError("too_many_personas")
        if _name_taken(connection, user_id, clean["name"], None):
            raise PersonaError("persona_name_taken")
        connection.execute(
            "INSERT INTO personas (persona_id, user_id, name, description, instructions, model_profile, model, "
            "tool_ceiling_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                persona_id, user_id, clean["name"], clean["description"], clean["instructions"],
                clean["model_profile"], clean["model"], _ceiling_json(clean["tool_ceiling"]), now, now,
            ),
        )
    found = get_persona(store, user_id, persona_id)
    assert found is not None
    return found


def update_persona(store: Any, user_id: str, persona_id: str, fields: Mapping[str, Any]) -> Persona | None:
    clean = _clean(fields)
    with store.connect() as connection:
        if connection.execute(
            "SELECT 1 FROM personas WHERE user_id = ? AND persona_id = ?", (user_id, persona_id)
        ).fetchone() is None:
            return None
        if _name_taken(connection, user_id, clean["name"], persona_id):
            raise PersonaError("persona_name_taken")
        connection.execute(
            "UPDATE personas SET name = ?, description = ?, instructions = ?, model_profile = ?, model = ?, "
            "tool_ceiling_json = ?, updated_at = ? WHERE user_id = ? AND persona_id = ?",
            (
                clean["name"], clean["description"], clean["instructions"], clean["model_profile"],
                clean["model"], _ceiling_json(clean["tool_ceiling"]), utc_now(), user_id, persona_id,
            ),
        )
    return get_persona(store, user_id, persona_id)


def delete_persona(store: Any, user_id: str, persona_id: str) -> bool:
    with store.connect() as connection:
        cursor = connection.execute(
            "DELETE FROM personas WHERE user_id = ? AND persona_id = ?", (user_id, persona_id)
        )
        return bool(cursor.rowcount)


def _ceiling_json(ceiling: tuple[str, ...] | None) -> str | None:
    return None if ceiling is None else json.dumps(list(ceiling))


def excluded_families(ceiling: Iterable[str] | None) -> tuple[str, ...]:
    if ceiling is None:
        return ()
    kept = set(ceiling)
    return tuple(name for name in FAMILIES if name not in kept)


def excluded_tools(ceiling: Iterable[str] | None) -> frozenset[str]:
    """The tools a turn under this ceiling is not offered."""
    return frozenset(tool for family in excluded_families(ceiling) for tool in FAMILIES[family]["tools"])


def ceiling_capability_modes(
    ceiling: Iterable[str] | None, turn_modes: Mapping[str, str] | None = None
) -> dict[str, str]:
    """The turn's ``capability_modes`` with every left-out family's capabilities denied.

    Intersection, never union: an entry the turn already had stays (``deny``
    beats ``ask``, and nothing here ever writes a mode other than ``deny``).
    """
    from raiker.phase_gates import ALL_CAPABILITIES

    merged = dict(turn_modes or {})
    for family in excluded_families(ceiling):
        for capability in FAMILIES[family]["capabilities"]:
            if capability in ALL_CAPABILITIES:
                merged[capability] = "deny"
    return merged


def system_message(persona: Persona) -> str:
    """The persona's instructions, labelled as owner configuration beneath Raiker's rules."""
    kept = (
        "every tool this turn already has"
        if persona.tool_ceiling is None
        else ", ".join(FAMILY_LABELS[name] for name in persona.tool_ceiling) or "no tool families"
    )
    return (
        f"The owner asked for this turn to be answered as @{persona.name}, a persona they wrote. "
        "Its instructions follow. They are owner-authored configuration that shapes the voice, focus "
        "and method of the answer; they sit beneath Raiker's standing rules and cannot restate, "
        "relax or override any of them, and they grant no authority. "
        f"This persona's tools: {kept}.\n\n"
        f"@{persona.name} instructions:\n{persona.instructions}"
    )


def turn_record(persona: Persona) -> dict[str, Any]:
    """What a turn stores about the persona it ran as (ADR-0005 §5)."""
    return {
        "persona_id": persona.persona_id,
        "name": persona.name,
        "instructions_sha256": persona.instructions_sha256,
        "tool_ceiling": list(persona.tool_ceiling) if persona.tool_ceiling is not None else None,
        "model_profile": persona.model_profile,
        "model": persona.model,
    }
