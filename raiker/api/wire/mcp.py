# SPDX-License-Identifier: Apache-2.0
"""Adding, connecting, renaming, containing and removing an MCP connection."""

from __future__ import annotations

from typing import Literal

from typing_extensions import TypedDict


class McpServerCreated(TypedDict):
    ok: bool
    server_id: str | None
    name: str


class RemoteMcpServerCreated(TypedDict):
    ok: bool
    server_id: str
    name: str
    transport: Literal["http"]


class McpServerConnected(TypedDict):
    """The handshake's result: the status and the tool names it discovered."""

    ok: bool
    server_id: str
    status: str
    tools: list[str]
    #: DEC-15 step 10 — tools found that the owner has not accepted as they are.
    pending: list[str]


class McpServerRenamed(TypedDict):
    ok: bool
    server_id: str
    name: str


class McpServerDeleted(TypedDict):
    ok: bool
    server_id: str


class McpContainment(TypedDict):
    """A pause, kill or resume, and the monitor state it left the connection in."""

    ok: bool
    server_id: str
    monitor_state: Literal["active", "paused", "killed"]


class McpToolsApproved(TypedDict):
    """DEC-15 step 10 — tools accepted for a server, and what it still holds."""

    ok: bool
    server_id: str
    #: The held tools this call accepted, as they are declared now.
    approved: list[str]
    #: What the server still holds for review after it.
    pending: list[str]
