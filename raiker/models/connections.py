"""Per-principal encrypted model-provider connection settings."""

from __future__ import annotations

import re

from raiker.runtime.connector_ecosystem import ConnectorVault
from raiker.storage.sqlite import SQLiteStore

_PREFIX = "model:"

# BUG-274 — a workspace id the owner pastes becomes an HTTP header value, so its
# shape is a safety question before it is a provider question. Anthropic's ids
# are `wrkspc_` followed by hex today, but a provider is free to change that and
# a rule written to today's prefix would refuse a valid id tomorrow. So the
# check is the conservative one a header actually needs — printable, bounded,
# and with nothing in it that could start a second header — rather than a guess
# at the provider's format. What the provider makes of the value is the
# provider's answer to give, and `provider_workspace_invalid` carries it back.
_WORKSPACE_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")

WORKSPACE_ID_INVALID_SHAPE = "workspace_id_invalid_shape"


def validated_workspace_id(value: str) -> str:
    """Return *value* stripped, or raise when it cannot safely become a header.

    Fail-closed: an id Raiker will not send is refused at the point the owner
    saves it, where they can still see what they typed, rather than at the point
    a turn needs it.
    """
    candidate = value.strip()
    if not _WORKSPACE_ID.match(candidate):
        raise ValueError(WORKSPACE_ID_INVALID_SHAPE)
    return candidate


def get_model_connection(
    store: SQLiteStore, principal_id: str, profile_id: str
) -> dict[str, str] | None:
    return ConnectorVault(store).get(principal_id, f"{_PREFIX}{profile_id}")


def put_model_connection(
    store: SQLiteStore, principal_id: str, profile_id: str, values: dict[str, str]
) -> None:
    ConnectorVault(store).put(principal_id, f"{_PREFIX}{profile_id}", values)


def list_model_connections(store: SQLiteStore, principal_id: str) -> list[str]:
    """Profile ids this principal has saved a connection for.

    Reads ids only — never a credential value — because callers use this to
    answer "has the owner configured this provider", not to obtain the secret.
    """
    with store.connect() as connection:
        rows = connection.execute(
            "SELECT connector_id FROM connector_credentials "
            "WHERE principal_id=? AND connector_id LIKE ?",
            (principal_id, f"{_PREFIX}%"),
        ).fetchall()
    return [str(row[0])[len(_PREFIX) :] for row in rows if str(row[0]).startswith(_PREFIX)]


def clear_model_connection(store: SQLiteStore, principal_id: str, profile_id: str) -> None:
    with store.connect() as connection:
        connection.execute(
            "DELETE FROM connector_credentials WHERE principal_id=? AND connector_id=?",
            (principal_id, f"{_PREFIX}{profile_id}"),
        )
