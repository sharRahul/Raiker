"""Per-principal encrypted model-provider connection settings."""

from __future__ import annotations

from raiker.runtime.connector_ecosystem import ConnectorVault
from raiker.storage.sqlite import SQLiteStore

_PREFIX = "model:"


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
