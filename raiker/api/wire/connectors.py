# SPDX-License-Identifier: Apache-2.0
"""The connector store: what can be installed, and installing, enabling and
crediting one."""

from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

from raiker.runtime.connector_ecosystem import ConnectorOperation

ConnectorAuthStatus = Literal["connected", "reauth_required", "not_connected"]


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
