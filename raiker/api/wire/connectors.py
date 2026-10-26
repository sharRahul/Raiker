# SPDX-License-Identifier: Apache-2.0
"""The connector store: what can be installed, and installing, enabling and
crediting one."""

from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

from raiker.runtime.connector_ecosystem import ConnectorInvocation, ConnectorOperation

ConnectorAuthStatus = Literal["connected", "reauth_required", "not_connected"]


class ConnectorAccount(TypedDict):
    """QUI-F07 — one named account on a connector. Never a credential value."""

    account_id: str
    label: str
    is_default: bool
    auth_status: ConnectorAuthStatus


class StoreConnector(TypedDict):
    """One catalogue connector, as this owner has it. Never a credential value."""

    connector_id: str
    display_name: str
    category: str
    description: str
    auth_type: Literal["oauth2", "api_key"]
    host: str
    installed: bool
    enabled: bool
    auth_status: ConnectorAuthStatus
    vault_configured: bool
    activity_status: Literal["idle", "processing", "completed", "failed"]
    active_operation: str | None
    last_invoked_at: str | None
    operations: list[ConnectorOperation]
    #: QUI-F07 — the default account first, then any the owner added.
    accounts: list[ConnectorAccount]


class ConnectorStoreView(TypedDict):
    connectors: list[StoreConnector]
    count: int
    vault_configured: bool


class ConnectorInstalled(TypedDict):
    ok: bool
    connector_id: str
    installed: bool
    enabled: bool


class ConnectorUninstalled(TypedDict):
    ok: bool
    connector_id: str
    installed: bool


class ConnectorEnabledSet(TypedDict):
    ok: bool
    connector_id: str
    enabled: bool


class ConnectorCredentialsSet(TypedDict):
    ok: bool
    connector_id: str
    auth_status: ConnectorAuthStatus


class ManifestRegistered(TypedDict):
    """The manifest as compiled: its digest and the operations it indexes."""

    ok: bool
    connector_id: str
    manifest_sha256: str
    kind: Literal["openapi", "ai_plugin"]
    version: NotRequired[str]
    api_url: NotRequired[str]
    operations: list[ConnectorOperation]


class ConnectorAccounts(TypedDict):
    connector_id: str
    accounts: list[ConnectorAccount]


class ConnectorAccountChanged(TypedDict):
    ok: bool
    connector_id: str
    account_id: str
    label: str


class ConnectorAccountRemoved(TypedDict):
    ok: bool
    connector_id: str
    account_id: str


class ConnectorActionQueued(TypedDict):
    """A write: recorded as an intent and waiting for the owner's approval. Nothing ran."""

    status: Literal["approval_required"]
    approval_id: str
    intent_id: str
    connector_id: str
    operation_id: str
    executes_action: bool
    #: QUI-F07 — the account the write will use, by the owner's name for it.
    account_label: str


class ConnectorActionCompleted(ConnectorInvocation):
    """A read, carried out."""

    status: Literal["completed"]
