# SPDX-License-Identifier: Apache-2.0
"""Settings → Connections → GitHub, as the page reads it (ADD-27 GH-19).

Metadata only. No key here names a token or a secret: the API redactor masks
any such key, which is the right blunt instrument to keep, so the shapes say
``browser_sign_in`` and ``private_key_configured`` instead.
"""

from __future__ import annotations

from typing import Any, Literal

from typing_extensions import TypedDict


class GitHubStates(TypedDict):
    """§4.2 — the six states, kept apart. No single *Connected* light."""

    connected_account: bool
    application_installed: bool
    repository_authorised: bool
    credential_available: bool
    capability_enabled: bool
    operation_approved: bool


class GitHubCredentialView(TypedDict):
    credential_id: str
    method: str
    label: str
    account_login: str | None
    account_id: str | None
    status: str
    selected: bool
    usable: bool
    expires_at: str | None
    validated_at: str | None
    last_error: str | None


class GitHubAppView(TypedDict):
    app_ref: str
    client_id: str
    slug: str | None
    browser_sign_in: bool
    private_key_configured: bool
    webhooks_enabled: bool


class GitHubInstallationView(TypedDict):
    installation_id: str
    app_ref: str
    account_login: str | None
    account_type: str | None
    repository_selection: str | None
    status: str


class GitHubRepositoryView(TypedDict):
    credential_id: str
    repository_id: str
    full_name: str
    private: bool
    installation_id: str | None
    status: str
    selected: bool


class GitHubDelegationView(TypedDict):
    delegation_id: str
    repository: str
    repository_id: str | None
    operations: list[str]
    branch_pattern: str | None
    expires_at: str
    max_actions: int | None
    actions_used: int
    state: str
    parent_delegation_id: str | None
    created_at: str


class IssueToPrStepView(TypedDict):
    step: str
    label: str
    operation: str
    decision: Literal["runs", "runs_under_delegation", "asks"]


class IssueToPrRoutineView(TypedDict):
    """BUG-339 — a plan and the Build task that would carry it out. Starts nothing."""

    repository: str
    work_branch: str
    delegation_id: str | None
    delegation_problems: list[str]
    steps: list[IssueToPrStepView]
    never: list[str]
    blocked_needs_owner: bool
    title: str
    description: str


class GitHubRiskView(TypedDict):
    operation: str
    label: str
    risk: str
    default: str
    delegable: bool
    capability: str | None


class GitHubConnection(TypedDict):
    states: GitHubStates
    selected: GitHubCredentialView | None
    credentials: list[GitHubCredentialView]
    device_sign_in: bool
    browser_sign_in: bool
    apps: list[GitHubAppView]
    installations: list[GitHubInstallationView]
    repositories: list[GitHubRepositoryView]
    delegations: list[GitHubDelegationView]
    risks: list[GitHubRiskView]
    checked_at: str


class GhAccountView(TypedDict):
    login: str
    active: bool


class SshKeyView(TypedDict):
    path: str
    fingerprint: str


class GitHubDiscovery(TypedDict):
    gh_accounts: list[GhAccountView]
    credential_helpers: list[str]
    ssh_keys: list[SshKeyView]


class GitHubSignInAttempt(TypedDict):
    attempt_id: str
    method: str
    outcome: str
    reason: str | None
    user_code: str | None
    verification_uri: str | None
    authorize_url: str | None
    expires_at: str
    next_poll_at: str | None
    credential_id: str | None


class GitHubDisconnected(TypedDict):
    credential_id: str
    method: str
    #: ``revoked`` · ``could_not_confirm`` · ``not_supported`` · ``not_applicable``
    github: str


class GitHubAppCheck(TypedDict):
    check: str
    result: str


class GitHubAppValidation(TypedDict):
    ok: bool
    checks: list[GitHubAppCheck]
    excess_permissions: list[str]
    installations: int


def credential_view(row: dict[str, Any], usable: bool) -> GitHubCredentialView:
    return {
        "credential_id": str(row["credential_id"]),
        "method": str(row["method"]),
        "label": str(row.get("label") or row["method"]),
        "account_login": str(row["account_login"]) if row.get("account_login") else None,
        "account_id": str(row["account_id"]) if row.get("account_id") else None,
        "status": str(row.get("status") or "unverified"),
        "selected": bool(row.get("selected")),
        "usable": usable,
        "expires_at": str(row["expires_at"]) if row.get("expires_at") else None,
        "validated_at": str(row["validated_at"]) if row.get("validated_at") else None,
        "last_error": str(row["last_error"]) if row.get("last_error") else None,
    }


def installation_view(row: dict[str, Any]) -> GitHubInstallationView:
    return {
        "installation_id": str(row["installation_id"]),
        "app_ref": str(row.get("app_ref") or ""),
        "account_login": str(row["account_login"]) if row.get("account_login") else None,
        "account_type": str(row["account_type"]) if row.get("account_type") else None,
        "repository_selection": str(row["repository_selection"]) if row.get("repository_selection") else None,
        "status": str(row.get("status") or "unknown"),
    }


def repository_view(row: dict[str, Any]) -> GitHubRepositoryView:
    return {
        "credential_id": str(row.get("credential_id") or ""),
        "repository_id": str(row["repository_id"]),
        "full_name": str(row["full_name"]),
        "private": bool(row.get("private")),
        "installation_id": str(row["installation_id"]) if row.get("installation_id") else None,
        "status": str(row.get("status") or "available"),
        "selected": bool(row.get("selected")),
    }


def delegation_view(row: dict[str, Any]) -> GitHubDelegationView:
    return {
        "delegation_id": str(row["delegation_id"]),
        "repository": str(row["repository"]),
        "repository_id": str(row["repository_id"]) if row.get("repository_id") else None,
        "operations": [str(op) for op in row.get("operations") or []],
        "branch_pattern": str(row["branch_pattern"]) if row.get("branch_pattern") else None,
        "expires_at": str(row["expires_at"]),
        "max_actions": int(row["max_actions"]) if row.get("max_actions") is not None else None,
        "actions_used": int(row.get("actions_used") or 0),
        "state": str(row.get("state") or "active"),
        "parent_delegation_id": str(row["parent_delegation_id"]) if row.get("parent_delegation_id") else None,
        "created_at": str(row["created_at"]),
    }


def attempt_view(row: dict[str, Any], authorize_url: str | None = None) -> GitHubSignInAttempt:
    return {
        "attempt_id": str(row["attempt_id"]),
        "method": str(row["method"]),
        "outcome": str(row.get("outcome") or "pending"),
        "reason": str(row["outcome_reason"]) if row.get("outcome_reason") else None,
        "user_code": str(row["user_code"]) if row.get("user_code") else None,
        "verification_uri": str(row["verification_uri"]) if row.get("verification_uri") else None,
        "authorize_url": authorize_url,
        "expires_at": str(row["expires_at"]),
        "next_poll_at": str(row["next_poll_at"]) if row.get("next_poll_at") else None,
        "credential_id": str(row["credential_id"]) if row.get("credential_id") else None,
    }
