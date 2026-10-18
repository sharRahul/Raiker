"""Settings → Connections → GitHub (ADD-27 GH-19, GH-31…GH-56).

Surfaces over the owner's decisions about their GitHub connection — which
credential, which repositories, which delegations — and over sign-in. **No route
here returns a token, a refresh token, a private key or a client secret**; the
ones that accept a secret store it and answer with what was configured, not
with the value.

Sign-in attempts are bound to the API session that started them: the device
code is polled, and the browser callback completed, only from that session.
The webhook receiver is the one unauthenticated route; its own signature check
is its authentication (§16).
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from pydantic import Field

from raiker.api.dependencies import authenticate as _auth
from raiker.api.dependencies import require_human
from raiker.api.dependencies import workspace_root as _ws
from raiker.api.refusals import refusal
from raiker.api.schemas import StrictRequest, serialize_dto
from raiker.api.sessions import ApiSession
from raiker.api.wire.github import (
    GitHubAppValidation,
    GitHubAppView,
    GitHubConnection,
    GitHubDelegationView,
    GitHubDisconnected,
    GitHubDiscovery,
    GitHubSignInAttempt,
    GitHubStates,
    IssueToPrRoutineView,
    attempt_view,
    credential_view,
    delegation_view,
    installation_view,
    repository_view,
)
from raiker.contracts.ids import utc_now
from raiker.github.http import GitHubHttp
from raiker.runtime.authority.models import Principal
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()


def _store(request: Request) -> SQLiteStore:
    return SQLiteStore(_ws(request))


def _http() -> GitHubHttp:
    """The client every route reaches GitHub with — one seam for tests."""
    return GitHubHttp()


def _fail(reason: str, code: int = status.HTTP_400_BAD_REQUEST) -> HTTPException:
    return refusal(code, reason)


# ── the connection as a whole ───────────────────────────────────────────


def _connection(store: SQLiteStore, principal_id: str) -> GitHubConnection:
    from raiker.github.apps import available_apps, identity
    from raiker.github.delegations import DelegationService, risk_table
    from raiker.runtime.authority.admission import capability_admission
    from raiker.runtime.git_credential import GitCredentialBroker

    broker = GitCredentialBroker(store, principal_id, http=_http())
    methods = broker.methods
    rows = methods.list()
    credentials = [credential_view(row, methods.usable(row)) for row in rows]
    selected = next((view for view in credentials if view["selected"]), None)
    apps: list[GitHubAppView] = [
        {
            "app_ref": app.app_ref, "client_id": app.client_id, "slug": app.slug,
            "browser_sign_in": app.has_client_secret and bool(app.callback_url),
            "private_key_configured": app.has_private_key,
            "webhooks_enabled": app.webhooks_enabled,
        }
        for app in available_apps(store)
    ]
    configured = {app["app_ref"] for app in apps}
    installations = [
        installation_view(row) for row in store.list_github_installations() if row.get("app_ref") in configured
    ]
    repositories = [repository_view(row) for row in store.list_github_repositories(principal_id)]
    delegations = [delegation_view(row) for row in DelegationService(store, principal_id).delegations()]
    enabled = any(
        capability_admission(store, principal_id, capability).gate_enabled
        for capability in ("git_push_execution", "connector_github_runtime", "git_fetch_execution")
    )
    states: GitHubStates = {
        "connected_account": selected is not None and selected["account_id"] is not None,
        "application_installed": any(row["status"] == "active" for row in installations),
        "repository_authorised": any(row["status"] == "available" for row in repositories),
        "credential_available": selected is not None and selected["usable"],
        "capability_enabled": enabled,
        "operation_approved": broker.live_grant() is not None or any(d["state"] == "active" for d in delegations),
    }
    byo = identity(store, "byo")
    connection: GitHubConnection = {
        "states": states,
        "selected": selected,
        "credentials": credentials,
        "device_sign_in": any(app.app_ref in ("official", "byo") for app in available_apps(store)),
        "browser_sign_in": byo is not None and byo.has_client_secret and bool(byo.callback_url),
        "apps": apps,
        "installations": installations,
        "repositories": repositories,
        "delegations": delegations,
        "risks": [
            {
                "operation": row["operation"], "label": row["label"], "risk": row["risk"],
                "default": row["default"], "delegable": row["delegable"], "capability": row["capability"],
            }
            for row in risk_table()
        ],
        "checked_at": utc_now(),
    }
    return connection


@router.get("/api/github")
async def get_github_connection(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """The six states, the credentials by method, repositories and delegations."""
    session, _principal = auth_data
    connection = _connection(_store(request), session.principal_id)
    return serialize_dto(connection)


@router.get("/api/github/discovery")
async def discover_github_methods(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """What this machine already has — gh accounts, helpers, SSH keys. Reads no secret."""
    from raiker.github.credentials import CredentialMethods

    session, _principal = auth_data
    found = CredentialMethods(_store(request), session.principal_id).discover()
    discovery: GitHubDiscovery = {
        "gh_accounts": [{"login": str(a["login"]), "active": bool(a["active"])} for a in found["gh_accounts"]],
        "credential_helpers": [str(name) for name in found["credential_helpers"]],
        "ssh_keys": [{"path": str(k["path"]), "fingerprint": str(k["fingerprint"])} for k in found["ssh_keys"]],
    }
    return serialize_dto(discovery)


# ── credentials by method ───────────────────────────────────────────────


class AddCredentialRequest(StrictRequest):
    method: Literal["gh_cli", "os_helper", "ssh", "app_installation"]
    #: The gh login, the credential-manager username, the SSH key path, or the
    #: installation id. Never a secret.
    selector: str = Field(min_length=1, max_length=500)


def _methods_call(request: Request, session: ApiSession, call: Any) -> GitHubConnection:
    from raiker.github.credentials import CredentialMethodError
    from raiker.runtime.git_credential import GitCredentialBroker

    store = _store(request)
    methods = GitCredentialBroker(store, session.principal_id, http=_http()).methods
    try:
        call(methods)
    except CredentialMethodError as exc:
        raise _fail(exc.reason, status.HTTP_422_UNPROCESSABLE_ENTITY) from None
    return _connection(store, session.principal_id)


@router.post("/api/github/credentials")
async def add_github_credential(
    body: AddCredentialRequest, request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """Use a credential this machine already holds; its account is checked first."""
    session, principal = auth_data
    require_human(principal)
    adders = {
        "gh_cli": lambda m: m.add_gh_cli(body.selector),
        "os_helper": lambda m: m.add_os_helper(body.selector),
        "ssh": lambda m: m.add_ssh(body.selector),
        "app_installation": lambda m: m.add_app_installation(body.selector),
    }
    connection = _methods_call(request, session, adders[body.method])
    return serialize_dto(connection)


@router.post("/api/github/credentials/{credential_id}/select")
async def select_github_credential(
    credential_id: str, request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """Use this credential from now on. Another account's grants end at once."""
    session, principal = auth_data
    require_human(principal)
    connection = _methods_call(request, session, lambda m: m.select(credential_id))
    return serialize_dto(connection)


@router.post("/api/github/credentials/{credential_id}/check")
async def check_github_credential(
    credential_id: str, request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """Ask GitHub whose this credential is now."""
    session, _principal = auth_data
    connection = _methods_call(request, session, lambda m: m.check(credential_id))
    return serialize_dto(connection)


@router.delete("/api/github/credentials/{credential_id}")
async def disconnect_github_credential(
    credential_id: str, request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """Stop using a credential at once; say whether GitHub confirmed the revocation."""
    from raiker.github.auth import GitHubSignIn
    from raiker.github.credentials import CredentialMethodError

    session, principal = auth_data
    require_human(principal)
    try:
        outcome = GitHubSignIn(_store(request), session.principal_id, http=_http()).disconnect(credential_id)
    except CredentialMethodError as exc:
        raise _fail(exc.reason, status.HTTP_404_NOT_FOUND) from None
    disconnected: GitHubDisconnected = {
        "credential_id": str(outcome["credential_id"]),
        "method": str(outcome["method"]),
        "github": str(outcome["github"]),
    }
    return serialize_dto(disconnected)


# ── sign-in ─────────────────────────────────────────────────────────────


class SignInRequest(StrictRequest):
    method: Literal["device", "browser"] = "device"


@router.post("/api/github/sign-in")
async def start_github_sign_in(
    body: SignInRequest, request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """Start a sign-in. Device: a code to enter at GitHub. Browser: a URL to open."""
    from raiker.github.apps import identity
    from raiker.github.auth import GitHubSignIn, SignInError

    session, principal = auth_data
    require_human(principal)
    store = _store(request)
    sign_in = GitHubSignIn(store, session.principal_id, http=_http())
    try:
        if body.method == "browser":
            row, url = sign_in.start_browser(session.session_id)
            attempt = attempt_view(row, authorize_url=url)
        else:
            app_ref = "byo" if identity(store, "byo") is not None else "official"
            attempt = attempt_view(sign_in.start_device(session.session_id, app_ref=app_ref))
    except SignInError as exc:
        raise _fail(exc.reason, status.HTTP_409_CONFLICT) from None
    return serialize_dto(attempt)


def _attempt_call(request: Request, session: ApiSession, attempt_id: str, verb: str) -> GitHubSignInAttempt:
    from raiker.github.auth import GitHubSignIn, SignInError

    sign_in = GitHubSignIn(_store(request), session.principal_id, http=_http())
    try:
        row = (
            sign_in.poll_device(attempt_id, session.session_id)
            if verb == "poll"
            else sign_in.cancel(attempt_id, session.session_id)
        )
    except SignInError as exc:
        code = status.HTTP_404_NOT_FOUND if exc.reason == "github_sign_in_unknown" else status.HTTP_409_CONFLICT
        raise _fail(exc.reason, code) from None
    return attempt_view(row)


@router.post("/api/github/sign-in/{attempt_id}/poll")
async def poll_github_sign_in(
    attempt_id: str, request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """Ask GitHub once — no sooner than it allows — whether the code was entered."""
    session, _principal = auth_data
    attempt = _attempt_call(request, session, attempt_id, "poll")
    return serialize_dto(attempt)


@router.post("/api/github/sign-in/{attempt_id}/cancel")
async def cancel_github_sign_in(
    attempt_id: str, request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    session, _principal = auth_data
    attempt = _attempt_call(request, session, attempt_id, "cancel")
    return serialize_dto(attempt)


_CALLBACK_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>GitHub sign-in</title><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:system-ui,sans-serif;max-width:32rem;margin:4rem auto;padding:0 1rem">
<h1 style="font-size:1.25rem">{title}</h1><p>{body}</p>
<p><a href="/#/settings/connections/github">Back to Raiker</a></p></body></html>"""


@router.get("/api/github/callback")
async def github_sign_in_callback(
    request: Request,
    state: str = "",
    code: str | None = None,
    error: str | None = None,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> HTMLResponse:
    """Where GitHub sends the browser back. Completed only by the session that started it."""
    from html import escape

    from raiker.github.auth import GitHubSignIn, SignInError

    session, _principal = auth_data
    sign_in = GitHubSignIn(_store(request), session.principal_id, http=_http())
    try:
        row = sign_in.complete_browser(session.session_id, state=state, code=code, error=error)
    except SignInError as exc:
        page = _CALLBACK_PAGE.format(title="GitHub sign-in did not complete", body=escape(exc.message))
        return HTMLResponse(page, status_code=status.HTTP_400_BAD_REQUEST)
    if row.get("outcome") == "connected":
        page = _CALLBACK_PAGE.format(title="Signed in to GitHub", body="You can close this tab.")
    elif row.get("outcome") == "denied":
        page = _CALLBACK_PAGE.format(title="GitHub did not grant access", body="Nothing was connected.")
    else:
        page = _CALLBACK_PAGE.format(title="Sign-in was cancelled", body="Nothing was connected.")
    return HTMLResponse(page)


# ── repositories ────────────────────────────────────────────────────────


@router.post("/api/github/repositories/refresh")
async def refresh_github_repositories(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """Ask GitHub, now, which repositories the selected credential reaches."""
    from raiker.github.auth import SignInError, discover_repositories
    from raiker.github.credentials import CredentialMethodError
    from raiker.runtime.git_credential import GitCredentialBroker

    session, _principal = auth_data
    store = _store(request)
    broker = GitCredentialBroker(store, session.principal_id, http=_http())
    selected = broker.methods.selected()
    if selected is None:
        raise _fail("git_token_not_configured", status.HTTP_409_CONFLICT)
    try:
        discover_repositories(
            store, session.principal_id, str(selected["credential_id"]), http=_http(), methods=broker.methods
        )
    except (SignInError, CredentialMethodError) as exc:
        raise _fail(exc.reason, status.HTTP_409_CONFLICT) from None
    connection = _connection(store, session.principal_id)
    return serialize_dto(connection)


class RepositorySelection(StrictRequest):
    credential_id: str = Field(min_length=1, max_length=100)
    selected: bool


@router.put("/api/github/repositories/{repository_id}")
async def select_github_repository(
    repository_id: str,
    body: RepositorySelection,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, principal = auth_data
    require_human(principal)
    store = _store(request)
    if not store.set_github_repository_selected(session.principal_id, body.credential_id, repository_id, body.selected):
        raise _fail("github_repository_unknown", status.HTTP_404_NOT_FOUND)
    connection = _connection(store, session.principal_id)
    return serialize_dto(connection)


# ── delegations ─────────────────────────────────────────────────────────


class DelegationRequest(StrictRequest):
    repository: str = Field(min_length=1, max_length=200)
    operations: list[str] = Field(min_length=1, max_length=12)
    branch_pattern: str | None = Field(default=None, max_length=200)
    expires_in_hours: float = Field(default=24.0, gt=0, le=24 * 30)
    max_actions: int | None = Field(default=None, gt=0, le=1000)
    note: str | None = Field(default=None, max_length=500)


@router.post("/api/github/delegations")
async def create_github_delegation(
    body: DelegationRequest, request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """Delegate repository work. Only a person can; merges and deletions never."""
    from raiker.github.delegations import DelegationError, DelegationService

    session, principal = auth_data
    require_human(principal)
    try:
        row = DelegationService(_store(request), session.principal_id).create(
            created_by=principal, repository=body.repository, operations=body.operations,
            branch_pattern=body.branch_pattern, expires_in_hours=body.expires_in_hours,
            max_actions=body.max_actions, note=body.note,
        )
    except DelegationError as exc:
        raise _fail(exc.reason, status.HTTP_422_UNPROCESSABLE_ENTITY) from None
    delegation: GitHubDelegationView = delegation_view(row)
    return serialize_dto(delegation)


@router.delete("/api/github/delegations/{delegation_id}")
async def revoke_github_delegation(
    delegation_id: str, request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """End a delegation and every share narrowed from it."""
    from raiker.github.delegations import DelegationError, DelegationService

    session, principal = auth_data
    require_human(principal)
    store = _store(request)
    try:
        DelegationService(store, session.principal_id).revoke(delegation_id, revoked_by=principal)
    except DelegationError as exc:
        raise _fail(exc.reason, status.HTTP_404_NOT_FOUND) from None
    connection = _connection(store, session.principal_id)
    return serialize_dto(connection)


class IssueToPrRequest(StrictRequest):
    repository: str = Field(min_length=1, max_length=200)
    issue_number: int = Field(gt=0)
    work_branch: str = Field(min_length=1, max_length=200)
    delegation_id: str | None = Field(default=None, max_length=100)


def _routine_http() -> GitHubHttp:
    """GitHub, asked whether the delegated repository is still the one named (BUG-338)."""
    return GitHubHttp()


@router.post("/api/github/routines/issue-to-pr")
async def plan_issue_to_pr_routine(
    body: IssueToPrRequest, request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """BUG-339 — which steps would run, and the Build task that would run them.

    Read-only: the owner schedules the returned task through Tasks, where the
    model check and the schedule's terms apply as to any other routine. The
    task carries instructions, not authority — each write still meets the
    router, which runs it only under a covering, re-validated delegation.
    """
    from raiker.github.routines import issue_to_pr_task_draft, plan_issue_to_pr

    session, principal = auth_data
    require_human(principal)
    repository = body.repository.strip()
    if not repository.startswith("github.com/"):
        repository = f"github.com/{repository}"
    plan = plan_issue_to_pr(
        _store(request), session.principal_id, repository=repository,
        work_branch=body.work_branch.strip(), delegation_id=body.delegation_id,
        http=_routine_http() if body.delegation_id else None,
    )
    routine: IssueToPrRoutineView = {
        **plan,  # type: ignore[typeddict-item]
        **issue_to_pr_task_draft(plan, issue_number=body.issue_number),
    }
    return serialize_dto(routine)


# ── a custom GitHub App (Advanced, self-hosted) ─────────────────────────


class SecretReference(StrictRequest):
    """Where a secret lives: an environment variable, a file, or pasted (vault)."""

    kind: Literal["env", "file", "vault"]
    value: str = Field(min_length=1, max_length=20_000)


class AppConfigRequest(StrictRequest):
    client_id: str = Field(min_length=1, max_length=100)
    app_id: str | None = Field(default=None, max_length=30)
    callback_url: str | None = Field(default=None, max_length=500)
    private_key: SecretReference | None = None
    client_secret: SecretReference | None = None
    webhook_secret: SecretReference | None = None
    webhooks_enabled: bool = False


def _reference(store: SQLiteStore, name: str, ref: SecretReference | None) -> str | None:
    import json

    from raiker.github.apps import parse_ref, store_secret_in_vault

    if ref is None:
        return None
    if ref.kind == "vault":
        # A pasted value is kept in the vault; the row holds where, not what.
        return json.dumps(store_secret_in_vault(store, f"byo_{name}", ref.value))
    return json.dumps(parse_ref({"kind": ref.kind, "value": ref.value}))


@router.put("/api/github/app")
async def configure_github_app(
    body: AppConfigRequest, request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """Configure your own GitHub App. Secrets are kept by reference, never echoed."""
    from raiker.github.apps import AppConfigError, identity

    session, principal = auth_data
    require_human(principal)
    store = _store(request)
    if body.callback_url and not body.callback_url.startswith(("https://", "http://127.0.0.1", "http://localhost")):
        raise _fail("github_app_callback_invalid", status.HTTP_422_UNPROCESSABLE_ENTITY)
    try:
        refs = {
            "private_key_ref": _reference(store, "private_key", body.private_key),
            "client_secret_ref": _reference(store, "client_secret", body.client_secret),
            "webhook_secret_ref": _reference(store, "webhook_secret", body.webhook_secret),
        }
    except AppConfigError as exc:
        raise _fail(exc.reason, status.HTTP_422_UNPROCESSABLE_ENTITY) from None
    store.upsert_github_app(
        "byo", updated_by=session.principal_id, client_id=body.client_id, app_id=body.app_id,
        callback_url=body.callback_url, webhooks_enabled=1 if body.webhooks_enabled else 0,
        **{key: value for key, value in refs.items() if value is not None},
    )
    app = identity(store, "byo")
    assert app is not None
    view: GitHubAppView = {
        "app_ref": app.app_ref, "client_id": app.client_id, "slug": app.slug,
        "browser_sign_in": app.has_client_secret and bool(app.callback_url),
        "private_key_configured": app.has_private_key, "webhooks_enabled": app.webhooks_enabled,
    }
    return serialize_dto(view)


@router.post("/api/github/app/validate")
async def validate_github_app(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """Check the App against GitHub: its key, its id, its permissions, its installations."""
    from raiker.github.app_service import GitHubAppService

    _session, principal = auth_data
    require_human(principal)
    store = _store(request)
    result = GitHubAppService(store, "byo", http=_http()).validate()
    validation: GitHubAppValidation = {
        "ok": bool(result.get("ok")),
        "checks": [
            {"check": str(item.get("check")), "result": str(item.get("result"))}
            for item in result.get("checks") or []
        ],
        "excess_permissions": [str(item) for item in result.get("excess_permissions") or []],
        "installations": len([row for row in store.list_github_installations() if row.get("app_ref") == "byo"]),
    }
    return serialize_dto(validation)


@router.delete("/api/github/app")
async def remove_github_app(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """Forget the custom App's configuration. Sign-ins made with it stop refreshing."""
    from raiker.github.app_service import forget_installation_tokens

    session, principal = auth_data
    require_human(principal)
    store = _store(request)
    store.delete_github_app("byo")
    forget_installation_tokens()
    connection = _connection(store, session.principal_id)
    return serialize_dto(connection)


# ── webhooks (§16) ──────────────────────────────────────────────────────


@router.post("/api/github/webhook")
async def receive_github_webhook(request: Request) -> dict[str, Any]:
    """One delivery to the configured App. Its signature is its authentication."""
    from raiker.github.webhooks import MAX_BODY, receive

    body = await request.body()
    if len(body) > MAX_BODY:
        raise _fail("too_large", status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
    outcome = receive(_store(request), dict(request.headers), body)
    if outcome.status >= 400:
        raise _fail(outcome.outcome, outcome.status)
    return {"outcome": outcome.outcome}
