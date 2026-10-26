# mypy: disable-error-code="misc"
"""The Library's pinned answer blocks (QUI-F15).

One part of :class:`raiker.storage.sqlite.SQLiteStore`, which inherits it. A pin
is a copy of one validated block of a stored answer; this layer only stores and
reads it. Every read and write names the owner, and an empty owner matches
nothing.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from raiker.contracts.ids import new_id, utc_now

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore


class LibraryStore:

    def save_library_pin(
        self: SQLiteStore,
        *,
        owner_principal_id: str,
        session_id: str,
        turn_id: str,
        part_index: int,
        part_type: str,
        title: str,
        data: dict[str, Any],
        project_id: str | None,
    ) -> dict[str, Any]:
        """Pin one block, or re-file the pin that already holds it.

        Pinning the same block twice keeps one pin: the second call moves it to
        the project it names rather than making a copy the owner then has to
        tell apart.
        """
        existing = self._row(
            "SELECT pin_id FROM library_pins WHERE owner_principal_id = ? AND turn_id = ? AND part_index = ?",
            (owner_principal_id, turn_id, part_index),
        )
        if existing is not None:
            self._execute(
                "UPDATE library_pins SET project_id = ? WHERE pin_id = ?",
                (project_id, existing["pin_id"]),
            )
            pin_id = str(existing["pin_id"])
        else:
            pin_id = new_id("pin_")
            self._execute(
                """
                INSERT INTO library_pins
                (pin_id, owner_principal_id, session_id, turn_id, part_index, part_type,
                 title, data_json, project_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pin_id, owner_principal_id, session_id, turn_id, part_index, part_type,
                    title, json.dumps(data, sort_keys=True), project_id, utc_now(),
                ),
            )
        pin = self.load_library_pin(pin_id, owner_principal_id=owner_principal_id)
        assert pin is not None
        return pin

    def load_library_pin(self: SQLiteStore, pin_id: str, *, owner_principal_id: str) -> dict[str, Any] | None:
        if not (pin_id and owner_principal_id):
            return None
        row = self._row(
            "SELECT * FROM library_pins WHERE pin_id = ? AND owner_principal_id = ?",
            (pin_id, owner_principal_id),
        )
        return _pin(dict(row)) if row else None

    def list_library_pins(
        self: SQLiteStore, *, owner_principal_id: str, limit: int = 200
    ) -> list[dict[str, Any]]:
        if not owner_principal_id:
            return []
        rows = self._rows(
            "SELECT * FROM library_pins WHERE owner_principal_id = ? ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (owner_principal_id, max(1, min(int(limit), 500))),
        )
        return [_pin(dict(row)) for row in rows]

    def pinned_parts_for_session(
        self: SQLiteStore, *, owner_principal_id: str, session_id: str
    ) -> list[dict[str, Any]]:
        """Which blocks of one conversation are pinned, so the toolbar can say so."""
        if not (owner_principal_id and session_id):
            return []
        rows = self._rows(
            "SELECT pin_id, turn_id, part_index, project_id FROM library_pins "
            "WHERE owner_principal_id = ? AND session_id = ?",
            (owner_principal_id, session_id),
        )
        return [dict(row) for row in rows]

    def move_library_pin(
        self: SQLiteStore, pin_id: str, *, owner_principal_id: str, project_id: str | None
    ) -> bool:
        if not (pin_id and owner_principal_id):
            return False
        return bool(self._execute(
            "UPDATE library_pins SET project_id = ? WHERE pin_id = ? AND owner_principal_id = ?",
            (project_id, pin_id, owner_principal_id),
        ))

    def delete_library_pin(self: SQLiteStore, pin_id: str, *, owner_principal_id: str) -> bool:
        if not (pin_id and owner_principal_id):
            return False
        return bool(self._execute(
            "DELETE FROM library_pins WHERE pin_id = ? AND owner_principal_id = ?",
            (pin_id, owner_principal_id),
        ))


def _pin(row: dict[str, Any]) -> dict[str, Any]:
    try:
        data = json.loads(str(row.get("data_json") or "{}"))
    except ValueError:
        data = {}
    row["data"] = data if isinstance(data, dict) else {}
    row.pop("data_json", None)
    return row
