"""QUI-P04 — what Raiker may do with one connection: three presets.

The plan's connection detail offers, per service:

* **Read only** — the default for every new connection. Reads go ahead under
  Permissions; any operation that changes something is refused for this
  connection, whatever else allows it.
* **Ask before changes** — every operation that changes something waits for
  the owner, even one its manifest marks as not needing confirmation.
* **Custom** — Permissions as set, nothing added. A connection added before
  presets existed reads as Custom, so nothing it already did changes.

A preset only narrows: it is checked after everything that already governs a
connector action (the connector gate, its decision mode, the manifest's own
confirmation flag), and can turn an allow into an ask or a refusal, never the
reverse. It is one row per owner and connection, stored once and read by every
surface (following Hermes' connector presets and Muse's per-app read-only or
full actions).
"""

from __future__ import annotations

from typing import Any, Literal, cast

from raiker.contracts.ids import utc_now

Preset = Literal["read_only", "ask", "custom"]
PRESETS: tuple[str, ...] = ("read_only", "ask", "custom")
#: What a connection added from now on starts as.
NEW_CONNECTION_PRESET: Preset = "read_only"
#: What a connection with no stored preset reads as: unchanged behaviour.
UNSET_PRESET: Preset = "custom"

_READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def is_read(method: str) -> bool:
    """Whether an operation only reads, by its HTTP method (as the detail labels it)."""
    return method.strip().upper() in _READ_METHODS


def get(store: Any, principal_id: str, connector_id: str) -> Preset:
    row = store._row(
        "SELECT preset FROM connector_policies WHERE principal_id = ? AND connector_id = ?",
        (principal_id, connector_id),
    )
    if row is None:
        return UNSET_PRESET
    preset = str(row["preset"])
    # A stored value this build does not know is read as the strictest preset.
    return cast(Preset, preset) if preset in PRESETS else "read_only"


def set_preset(store: Any, principal_id: str, connector_id: str, preset: str) -> Preset:
    if preset not in PRESETS:
        raise ValueError("connector_preset_invalid")
    store._execute(
        "INSERT INTO connector_policies (principal_id, connector_id, preset, updated_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(principal_id, connector_id) DO UPDATE SET preset = excluded.preset, updated_at = excluded.updated_at",
        (principal_id, connector_id, preset, utc_now()),
    )
    return cast(Preset, preset)


def start_new(store: Any, principal_id: str, connector_id: str) -> None:
    """A newly added connection starts Read only; an existing choice is kept."""
    store._execute(
        "INSERT INTO connector_policies (principal_id, connector_id, preset, updated_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(principal_id, connector_id) DO NOTHING",
        (principal_id, connector_id, NEW_CONNECTION_PRESET, utc_now()),
    )


def refusal(preset: str, method: str) -> str | None:
    """The reason this preset refuses an operation outright, or ``None``."""
    if preset == "read_only" and not is_read(method):
        return "connection_read_only"
    return None


def must_ask(preset: str, method: str) -> bool:
    """Whether this preset sends a changing operation to the owner first."""
    return preset == "ask" and not is_read(method)
