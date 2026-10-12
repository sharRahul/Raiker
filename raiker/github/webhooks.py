"""GitHub webhook deliveries to a configured App (ADD-27 GH-43).

Off unless the operator configured the App with webhooks enabled and a webhook
secret. A delivery is accepted only if all of these hold, checked in order:

1. it is no larger than :data:`MAX_BODY`;
2. ``X-Hub-Signature-256`` is ``sha256=`` and the HMAC-SHA256 of the raw body
   under the webhook secret, compared in constant time (P16);
3. ``X-GitHub-Event`` is one this receiver handles;
4. ``X-GitHub-Delivery`` has not been seen before (a replay claims nothing);
5. the installation it names belongs to this App, or is being created.

What it may change is narrow: an installation's status and repository list,
and — when a user revokes their authorisation of the App — that user's
credentials and every grant on them. A delivery never creates authority, never
starts work and is never given to a model.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from raiker.github.apps import AppConfigError, read_secret

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

MAX_BODY = 1_000_000
HANDLED_EVENTS = frozenset({"ping", "installation", "installation_repositories", "github_app_authorization"})
_INSTALLATION_STATUS = {
    "created": "active", "unsuspend": "active", "new_permissions_accepted": "active",
    "deleted": "removed", "suspend": "suspended",
}


@dataclass(frozen=True)
class WebhookOutcome:
    status: int
    outcome: str


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _header(headers: Mapping[str, str], name: str) -> str:
    lowered = name.lower()
    for key, value in headers.items():
        if key.lower() == lowered:
            return value
    return ""


def signature_valid(secret: str, body: bytes, signature: str) -> bool:
    if not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip())


def receive(
    store: SQLiteStore, headers: Mapping[str, str], body: bytes, *, app_ref: str = "byo"
) -> WebhookOutcome:
    """Verify, deduplicate and apply one delivery. Never raises on bad input."""
    app = store.load_github_app(app_ref)
    if app is None or not app.get("webhooks_enabled") or not app.get("webhook_secret_ref"):
        return WebhookOutcome(404, "webhooks_disabled")
    if len(body) > MAX_BODY:
        return WebhookOutcome(413, "too_large")
    try:
        secret = read_secret(store, app.get("webhook_secret_ref"))
    except AppConfigError:
        return WebhookOutcome(503, "webhook_secret_unavailable")
    if not signature_valid(secret, body, _header(headers, "X-Hub-Signature-256")):
        _record_rejection(store, "signature_invalid")
        return WebhookOutcome(401, "signature_invalid")
    event = _header(headers, "X-GitHub-Event")
    if event not in HANDLED_EVENTS:
        return WebhookOutcome(202, "event_ignored")
    delivery_id = _header(headers, "X-GitHub-Delivery").strip()
    if not delivery_id or len(delivery_id) > 100:
        return WebhookOutcome(400, "delivery_id_missing")
    try:
        payload: Any = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return WebhookOutcome(400, "payload_invalid")
    if not isinstance(payload, dict):
        return WebhookOutcome(400, "payload_invalid")
    installation = _as_dict(payload.get("installation"))
    installation_id = str(installation.get("id") or "") or None
    if not store.claim_github_delivery(delivery_id, event, installation_id):
        return WebhookOutcome(200, "duplicate")
    outcome = _apply(store, app_ref, event, payload, installation_id)
    store.settle_github_delivery(delivery_id, outcome)
    return WebhookOutcome(202, outcome)


def _apply(
    store: SQLiteStore, app_ref: str, event: str, payload: dict[str, Any], installation_id: str | None
) -> str:
    action = str(payload.get("action") or "")
    if event == "ping":
        return "pong"
    if event == "github_app_authorization" and action == "revoked":
        sender = _as_dict(payload.get("sender"))
        account_id = str(sender.get("id") or "")
        if not account_id:
            return "ignored"
        return "revoked" if _revoke_account(store, account_id) else "nothing_to_revoke"
    if installation_id is None:
        return "ignored"
    known = store.load_github_installation(installation_id)
    if known is not None and known.get("app_ref") != app_ref:
        # Another App's installation: a delivery cannot move it.
        return "installation_mismatch"
    if event == "installation":
        status = _INSTALLATION_STATUS.get(action)
        if status is None:
            return "ignored"
        installation = _as_dict(payload.get("installation"))
        account = _as_dict(installation.get("account"))
        store.upsert_github_installation(
            installation_id, app_ref=app_ref, status=status,
            account_id=str(account.get("id") or "") or None,
            account_login=str(account.get("login") or "") or None,
            account_type=str(account.get("type") or "") or None,
            repository_selection=str(installation.get("repository_selection") or "") or None,
            permissions=_as_dict(installation.get("permissions")),
        )
        if status != "active":
            from raiker.github.app_service import forget_installation_tokens

            forget_installation_tokens()
        return f"installation_{status}"
    if event == "installation_repositories" and known is not None:
        removed_value = payload.get("repositories_removed")
        removed: list[Any] = removed_value if isinstance(removed_value, list) else []
        ids = [str(repo.get("id")) for repo in removed if isinstance(repo, dict) and repo.get("id") is not None]
        if ids:
            with store.connect() as connection:
                connection.executemany(
                    """UPDATE github_repositories SET status = 'removed', selected = 0
                       WHERE installation_id = ? AND repository_id = ?""",
                    [(installation_id, value) for value in ids],
                )
        return f"repositories_removed:{len(ids)}"
    return "ignored"


def _revoke_account(store: SQLiteStore, account_id: str) -> bool:
    """A user revoked the App: their App sign-ins stop, and every grant on them."""
    with store.connect() as connection:
        rows = connection.execute(
            "SELECT credential_id, principal_id FROM git_credentials WHERE method = 'app_user' AND account_id = ?",
            (account_id,),
        ).fetchall()
        for row in rows:
            connection.execute(
                "UPDATE git_credentials SET status = 'revoked', last_error = 'github_app_authorization_revoked' WHERE credential_id = ?",
                (row[0],),
            )
    for row in rows:
        store.revoke_git_credential_grants(str(row[1]))
    return bool(rows)


def _record_rejection(store: SQLiteStore, reason: str) -> None:
    from raiker.events.types import make_event
    from raiker.events.writer import EventLogWriter

    try:
        EventLogWriter(store).append(
            make_event(
                session_id="git_credential", turn_id=None, event_type="github_webhook_rejected",
                actor="github_webhooks", payload={"reason": reason},
            )
        )
    except Exception:  # noqa: BLE001 — a rejected delivery is refused whether or not it is recorded
        return
