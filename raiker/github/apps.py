"""Which GitHub App Raiker signs in with, and where its secrets are (ADD-27 GH-30, GH-41).

Two Apps can exist:

* **official** — the Raiker GitHub App the product operator registers. A build
  publishes its Client ID (public by design); its private key and client secret
  are never in a build. Until the operator registers it, sign-in through it is
  *not available in this build*, which is a state, not an error.
* **byo** — an App a self-hosting operator registered themselves, configured by
  reference: the App ID and Client ID, and *where* its private key, client
  secret and webhook secret are kept (an environment variable, a file only its
  owner can read, or the workspace vault). Values are never stored in a
  settings row and never returned by any read.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

#: The official App's Client ID, published here once the operator registers the
#: App (GH-30). ``RAIKER_GITHUB_APP_CLIENT_ID`` lets an operator's own build or
#: a managed deployment provide it without a code change.
OFFICIAL_CLIENT_ID: str | None = None
OFFICIAL_APP_SLUG: str | None = None

#: The vault principal App secrets are kept under. Deployment configuration,
#: not any one owner's credential.
APP_VAULT_PRINCIPAL = "system:github_app"

REF_KINDS = ("env", "file", "vault")


class AppConfigError(Exception):
    def __init__(self, reason: str, message: str = "") -> None:
        super().__init__(message or reason)
        self.reason = reason
        self.message = message or reason


@dataclass(frozen=True)
class AppIdentity:
    """The parts of an App a sign-in needs, without any secret."""

    app_ref: str
    client_id: str
    app_id: str | None
    slug: str | None
    has_client_secret: bool
    has_private_key: bool
    callback_url: str | None
    webhooks_enabled: bool


def official_client_id() -> str | None:
    value = os.environ.get("RAIKER_GITHUB_APP_CLIENT_ID", "").strip() or OFFICIAL_CLIENT_ID
    return value or None


def parse_ref(raw: Any) -> dict[str, str] | None:
    """A secret reference ``{"kind": "env"|"file"|"vault", "value": …}``, validated."""
    if raw in (None, "", {}):
        return None
    data = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(data, dict):
        raise AppConfigError("github_app_secret_ref_invalid")
    kind, value = str(data.get("kind", "")), str(data.get("value", "")).strip()
    if kind not in REF_KINDS or not value:
        raise AppConfigError("github_app_secret_ref_invalid")
    if kind == "env" and not value.replace("_", "").isalnum():
        raise AppConfigError("github_app_secret_ref_invalid")
    return {"kind": kind, "value": value}


def read_secret(store: SQLiteStore, raw_ref: Any) -> str:
    """The value a reference points at. Never logged, never returned to a client."""
    ref = parse_ref(raw_ref)
    if ref is None:
        raise AppConfigError("github_app_secret_missing")
    if ref["kind"] == "env":
        value = os.environ.get(ref["value"], "")
    elif ref["kind"] == "file":
        path = Path(ref["value"]).expanduser()
        if not path.is_file():
            raise AppConfigError("github_app_secret_file_missing")
        if os.name != "nt" and stat.S_IMODE(path.stat().st_mode) & 0o077:
            # A private key other accounts on this machine can read is not private.
            raise AppConfigError("github_app_secret_file_too_open")
        value = path.read_text(encoding="utf-8")
    else:
        from raiker.runtime.connector_ecosystem import ConnectorVault

        stored = ConnectorVault(store).get(APP_VAULT_PRINCIPAL, ref["value"]) or {}
        value = stored.get("value", "")
    if not value.strip():
        raise AppConfigError("github_app_secret_missing")
    return value.strip() if ref["kind"] != "file" else value


def store_secret_in_vault(store: SQLiteStore, key: str, value: str) -> dict[str, str]:
    """Keep a pasted secret in the vault and return the reference to it."""
    from raiker.runtime.connector_ecosystem import ConnectorVault

    ConnectorVault(store).put(APP_VAULT_PRINCIPAL, key, {"value": value})
    return {"kind": "vault", "value": key}


def identity(store: SQLiteStore, app_ref: str) -> AppIdentity | None:
    """The App *app_ref* names, if it is configured enough to sign anyone in."""
    if app_ref == "official":
        client_id = official_client_id()
        if not client_id:
            return None
        return AppIdentity(
            app_ref="official", client_id=client_id, app_id=None, slug=OFFICIAL_APP_SLUG,
            has_client_secret=False, has_private_key=False, callback_url=None,
            webhooks_enabled=False,
        )
    row = store.load_github_app(app_ref)
    if row is None or not row.get("client_id"):
        return None
    return AppIdentity(
        app_ref=app_ref,
        client_id=str(row["client_id"]),
        app_id=str(row["app_id"]) if row.get("app_id") else None,
        slug=str(row["slug"]) if row.get("slug") else None,
        has_client_secret=bool(row.get("client_secret_ref")),
        has_private_key=bool(row.get("private_key_ref")),
        callback_url=str(row["callback_url"]) if row.get("callback_url") else None,
        webhooks_enabled=bool(row.get("webhooks_enabled")),
    )


def available_apps(store: SQLiteStore) -> list[AppIdentity]:
    found = [identity(store, "byo"), identity(store, "official")]
    return [app for app in found if app is not None]
