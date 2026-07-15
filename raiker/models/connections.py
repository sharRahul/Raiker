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


def clear_model_connection(store: SQLiteStore, principal_id: str, profile_id: str) -> None:
    with store.connect() as connection:
        connection.execute(
            "DELETE FROM connector_credentials WHERE principal_id=? AND connector_id=?",
            (principal_id, f"{_PREFIX}{profile_id}"),
        )
