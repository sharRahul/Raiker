"""QUI-F07 — named accounts per service.

An installed connector always has its **default** account. Its credential is
the one the connector always had (``connector_credentials`` keyed by the
connector id), so nothing that existed before changes. The owner may name it
("Work Gmail") and add further accounts ("Personal Gmail"), each with its own
credential slot, keyed ``<connector_id>#<account_id>`` in the same vault.

Rules:

* An account is the owner's. Every read names the principal; another
  principal's account answers as unknown.
* A call names the account it uses, or uses the default. A name the owner did
  not create is refused (``connector_account_unknown``), never mapped to the
  default, so a write meant for "Personal" can never go out from "Work".
* Removing an account removes its credential. The default account cannot be
  removed here; uninstalling the connector removes it.
"""

from __future__ import annotations

from typing import Any

from raiker.contracts.ids import new_id, utc_now
from raiker.storage.sqlite import SQLiteStore

DEFAULT_ACCOUNT = "default"
MAX_ACCOUNTS = 8
MAX_LABEL = 60


class AccountError(ValueError):
    pass


def credential_key(connector_id: str, account_id: str | None) -> str:
    """Where an account's credential lives in the vault."""
    if not account_id or account_id == DEFAULT_ACCOUNT:
        return connector_id
    return f"{connector_id}#{account_id}"


def _clean_label(label: str) -> str:
    clean = " ".join(str(label or "").split())[:MAX_LABEL]
    if not clean:
        raise AccountError("connector_account_label_required")
    return clean


def list_accounts(
    store: SQLiteStore, principal_id: str, connector_id: str, *, default_label: str
) -> list[dict[str, Any]]:
    """The default account first, then the others in the order they were added."""
    rows = {
        str(row["account_id"]): dict(row)
        for row in store._rows(
            "SELECT account_id, label, created_at FROM connector_accounts "
            "WHERE principal_id = ? AND connector_id = ? ORDER BY created_at, rowid",
            (principal_id, connector_id),
        )
    }
    keys = {
        str(row["connector_id"]): dict(row)
        for row in store._rows(
            "SELECT connector_id, expires_at, updated_at FROM connector_credentials "
            "WHERE principal_id = ? AND (connector_id = ? OR substr(connector_id, 1, ?) = ?)",
            (principal_id, connector_id, len(connector_id) + 1, f"{connector_id}#"),
        )
    }
    default = rows.pop(DEFAULT_ACCOUNT, None)
    accounts = [{
        "account_id": DEFAULT_ACCOUNT,
        "label": str(default["label"]) if default else default_label,
        "is_default": True,
        "credential": keys.get(connector_id),
    }]
    for account_id, row in rows.items():
        accounts.append({
            "account_id": account_id,
            "label": str(row["label"]),
            "is_default": False,
            "credential": keys.get(credential_key(connector_id, account_id)),
        })
    return accounts


def add_account(store: SQLiteStore, principal_id: str, connector_id: str, label: str) -> str:
    clean = _clean_label(label)
    existing = store._rows(
        "SELECT account_id, label FROM connector_accounts WHERE principal_id = ? AND connector_id = ?",
        (principal_id, connector_id),
    )
    if sum(1 for row in existing if row["account_id"] != DEFAULT_ACCOUNT) + 1 >= MAX_ACCOUNTS:
        raise AccountError("connector_account_limit")
    if any(str(row["label"]).casefold() == clean.casefold() for row in existing):
        raise AccountError("connector_account_label_taken")
    account_id = new_id("cacct_")
    store._execute(
        "INSERT INTO connector_accounts (principal_id, connector_id, account_id, label, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (principal_id, connector_id, account_id, clean, utc_now()),
    )
    return account_id


def rename_account(store: SQLiteStore, principal_id: str, connector_id: str, account_id: str, label: str) -> str:
    clean = _clean_label(label)
    if account_id != DEFAULT_ACCOUNT and not _exists(store, principal_id, connector_id, account_id):
        raise AccountError("connector_account_unknown")
    taken = store._row(
        "SELECT 1 FROM connector_accounts WHERE principal_id = ? AND connector_id = ? "
        "AND account_id <> ? AND lower(label) = lower(?)",
        (principal_id, connector_id, account_id, clean),
    )
    if taken is not None:
        raise AccountError("connector_account_label_taken")
    store._execute(
        "INSERT INTO connector_accounts (principal_id, connector_id, account_id, label, created_at) "
        "VALUES (?, ?, ?, ?, ?) ON CONFLICT(principal_id, connector_id, account_id) DO UPDATE SET label = excluded.label",
        (principal_id, connector_id, account_id, clean, utc_now()),
    )
    return clean


def remove_account(store: SQLiteStore, principal_id: str, connector_id: str, account_id: str) -> None:
    if account_id == DEFAULT_ACCOUNT:
        raise AccountError("connector_account_default")
    if not _exists(store, principal_id, connector_id, account_id):
        raise AccountError("connector_account_unknown")
    with store.connect() as connection:
        connection.execute(
            "DELETE FROM connector_credentials WHERE principal_id = ? AND connector_id = ?",
            (principal_id, credential_key(connector_id, account_id)),
        )
        connection.execute(
            "DELETE FROM connector_accounts WHERE principal_id = ? AND connector_id = ? AND account_id = ?",
            (principal_id, connector_id, account_id),
        )


def remove_all(store: SQLiteStore, principal_id: str, connector_id: str) -> None:
    """Uninstalling a connector removes every account and every credential it had."""
    with store.connect() as connection:
        connection.execute(
            "DELETE FROM connector_credentials WHERE principal_id = ? AND substr(connector_id, 1, ?) = ?",
            (principal_id, len(connector_id) + 1, f"{connector_id}#"),
        )
        connection.execute(
            "DELETE FROM connector_accounts WHERE principal_id = ? AND connector_id = ?",
            (principal_id, connector_id),
        )


def resolve(
    store: SQLiteStore, principal_id: str, connector_id: str, account_id: str | None, *, default_label: str
) -> tuple[str, str]:
    """``(account_id, label)`` for a call, refusing an account the owner does not have."""
    wanted = (account_id or "").strip() or DEFAULT_ACCOUNT
    for account in list_accounts(store, principal_id, connector_id, default_label=default_label):
        if account["account_id"] == wanted:
            return wanted, str(account["label"])
    raise AccountError("connector_account_unknown")


def _exists(store: SQLiteStore, principal_id: str, connector_id: str, account_id: str) -> bool:
    return store._row(
        "SELECT 1 FROM connector_accounts WHERE principal_id = ? AND connector_id = ? AND account_id = ?",
        (principal_id, connector_id, account_id),
    ) is not None


def match(store: SQLiteStore, principal_id: str, connector_id: str, wanted: str | None, *, default_label: str) -> str | None:
    """The account a model named, by the owner's label or its id; ``None`` if none matches.

    A model writes what the owner said ("from my personal Gmail"), so a label
    matches case-insensitively. Nothing named means the default account.
    """
    text = " ".join(str(wanted or "").split())
    if not text:
        return DEFAULT_ACCOUNT
    for account in list_accounts(store, principal_id, connector_id, default_label=default_label):
        if text == account["account_id"] or text.casefold() == str(account["label"]).casefold():
            return str(account["account_id"])
    return None


def intent_account_label(store: SQLiteStore, approval_id: str) -> str | None:
    """The account a pending write will use, as the owner named it, from the intent itself."""
    row = store._row(
        "SELECT principal_id, connector_id, account_id FROM connector_write_intents WHERE approval_id = ?",
        (approval_id,),
    )
    if row is None:
        return None
    from raiker.runtime.connector_ecosystem import ConnectorCatalog

    try:
        default_label = ConnectorCatalog().get(str(row["connector_id"])).name
    except ValueError:
        default_label = str(row["connector_id"])
    try:
        return resolve(
            store, str(row["principal_id"]), str(row["connector_id"]), row["account_id"], default_label=default_label
        )[1]
    except AccountError:
        return None
