# SPDX-License-Identifier: Apache-2.0
"""DEC-15 step 2 — secrets a local MCP server is given, and only that server.

Before this, the only way to give a local server a credential was
``RAIKER_MCP_ENV_ALLOWLIST``: a variable named there is passed from Raiker's own
environment to *every* local MCP server, so the token one server needed was in
the environment of all of them, and the value had to sit in the environment
Raiker itself was started with.

A server's secret is now a purpose-bound handle: a variable name the owner gives
one server, with its value held in the encrypted connector vault under that
server's id. It is delivered to that server's process when Raiker starts it,
and to no other process. The value is never returned by any read — the page
shows names — and is replaced in the server's output and error tail before
either is kept or shown to a model. Removing the server removes its secrets.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

#: Vault entries for one server live under this prefix and the server's id.
VAULT_PREFIX = "mcp_server_env:"

#: A variable name: what a program reads with ``os.environ``.
_NAME = re.compile(r"[A-Z][A-Z0-9_]{1,63}")

#: The longest secret value kept. A credential, not a document.
MAX_VALUE_CHARS = 8_192

#: The most secrets one server holds.
MAX_SECRETS = 16

#: What a kept value is replaced by in a server's output.
REDACTED = "[REDACTED_SECRET]"


def vault_key(server_id: str) -> str:
    return f"{VAULT_PREFIX}{server_id}"


def _reserved_names() -> frozenset[str]:
    """Names a server secret may not take.

    The variables a process needs to start (PATH, HOME and the rest) are set by
    the launcher; a secret named ``PATH`` would choose which program runs. The
    two variables that configure this boundary are not a server's to hold.
    """
    from raiker.runtime.executors.mcp import _MCP_ENV_NEVER, _MCP_ENV_PASSTHROUGH

    return frozenset(
        {*_MCP_ENV_PASSTHROUGH, *_MCP_ENV_NEVER, "PYTHONUNBUFFERED", "PYTHONIOENCODING"}
    )


def validate_name(name: str) -> str | None:
    """A refusal reason for a secret's name, or ``None`` when it may be used."""
    if not _NAME.fullmatch(name):
        return "mcp_secret_name_invalid"
    if name in _reserved_names():
        return "mcp_secret_name_reserved"
    return None


def _vault(store: SQLiteStore):  # type: ignore[no-untyped-def]
    from raiker.runtime.connector_ecosystem import ConnectorVault

    return ConnectorVault(store)


def _read(store: SQLiteStore, owner_principal_id: str, server_id: str) -> dict[str, str]:
    try:
        return dict(_vault(store).get(owner_principal_id, vault_key(server_id)) or {})
    except ValueError:
        # The vault key is missing or cannot decrypt: the server is started with
        # none of its secrets rather than with a guess, and the page says so.
        return {}


def secret_names(store: SQLiteStore, owner_principal_id: str, server_id: str) -> list[str]:
    """The names one server is given. Never the values."""
    return sorted(_read(store, owner_principal_id, server_id))


def secrets_updated_at(store: SQLiteStore, owner_principal_id: str, server_id: str) -> str | None:
    meta = _vault(store).metadata(owner_principal_id, vault_key(server_id))
    return str(meta["updated_at"]) if meta and meta.get("updated_at") else None


def set_secret(
    store: SQLiteStore, owner_principal_id: str, server_id: str, name: str, value: str
) -> str | None:
    """Store or replace one secret. Returns a refusal reason, or ``None``."""
    reason = validate_name(name)
    if reason:
        return reason
    if not value or len(value) > MAX_VALUE_CHARS or "\x00" in value:
        return "mcp_secret_value_invalid"
    current = _read(store, owner_principal_id, server_id)
    if name not in current and len(current) >= MAX_SECRETS:
        return "mcp_secret_limit_reached"
    current[name] = value
    _vault(store).put(owner_principal_id, vault_key(server_id), current)
    return None


def remove_secret(store: SQLiteStore, owner_principal_id: str, server_id: str, name: str) -> bool:
    """Remove one secret. True when it was there."""
    current = _read(store, owner_principal_id, server_id)
    if name not in current:
        return False
    del current[name]
    if current:
        _vault(store).put(owner_principal_id, vault_key(server_id), current)
    else:
        remove_all(store, owner_principal_id, server_id)
    return True


def remove_all(store: SQLiteStore, owner_principal_id: str, server_id: str) -> None:
    """Every secret one server held — called when the server is removed."""
    with store.connect() as connection:
        connection.execute(
            "DELETE FROM connector_credentials WHERE principal_id = ? AND connector_id = ?",
            (owner_principal_id, vault_key(server_id)),
        )


def secret_env(store: SQLiteStore, owner_principal_id: str, server_id: str | None) -> dict[str, str]:
    """The secrets to add to one server's process environment.

    A name that has since become reserved is skipped rather than allowed to
    override what the launcher set.
    """
    if not server_id:
        return {}
    return {
        name: value
        for name, value in _read(store, owner_principal_id, server_id).items()
        if validate_name(name) is None
    }


def redact_values(text: str, values: list[str] | tuple[str, ...]) -> str:
    """Replace every given secret value in ``text``. Short values are left: a
    two-character "secret" would redact half of any output and protect nothing."""
    for value in sorted({v for v in values if len(v) >= 4}, key=len, reverse=True):
        text = text.replace(value, REDACTED)
    return text


__all__ = [
    "MAX_SECRETS",
    "REDACTED",
    "redact_values",
    "remove_all",
    "remove_secret",
    "secret_env",
    "secret_names",
    "secrets_updated_at",
    "set_secret",
    "validate_name",
    "vault_key",
]
