"""Signal inbound: the owner's signal-cli daemon's event stream, read by the host.

Telegram pushes each update to Raiker's webhook. Signal has no server that
could: messages arrive at the owner's own ``signal-cli``, linked to their phone
as a device, and the daemon publishes them as Server-Sent Events on
``/api/v1/events``. This is the model Hermes Agent uses, and it keeps Signal's
keys in signal-cli rather than in Raiker.

So the host subscribes. This module is only a pump: it connects to the daemon
on loopback, turns each event into an :class:`InboundMessage` with the Signal
adapter, and hands it to the same ``_handle_inbound`` path a Telegram update
or a webhook message takes. Pairing, the sender allowlist, the per-sender
budget, duplicate suppression, the loop guard, redaction, the audit event and
the owner's stored route all apply there, identically. Nothing here decides
whether a message is allowed.

It runs only while a Signal pairing is enabled and ``RAIKER_SIGNAL_ACCOUNT``
names the linked number, reconnects with jittered backoff when the daemon goes
away, and reports what it is doing through :func:`bridge_status` so Messaging
can say whether Signal is actually listening.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

from raiker.channels.adapters import (
    InboundMessage,
    SignalAdapter,
    signal_account,
    signal_http_url,
)
from raiker.contracts.ids import utc_now

_LOG = logging.getLogger(__name__)

#: How long to wait before looking again while Signal is not set up.
IDLE_SECONDS = 15.0
#: Reconnect backoff after the daemon drops or refuses the stream.
RETRY_INITIAL_SECONDS = 2.0
RETRY_MAX_SECONDS = 60.0
#: The longest single SSE line accepted. An envelope is a few kilobytes; a
#: daemon sending more than this on one line is not one Raiker should parse.
MAX_LINE_BYTES = 256 * 1024


@dataclass
class BridgeStatus:
    """What the receiver is doing, for the Messaging page. Never holds a number."""

    state: str = "off"
    detail: str | None = None
    since: str = field(default_factory=utc_now)
    received: int = 0

    def set(self, state: str, detail: str | None = None) -> None:
        if state != self.state or detail != self.detail:
            self.state, self.detail, self.since = state, detail, utc_now()


_STATUS: dict[str, BridgeStatus] = {}


def bridge_status(workspace_root: str | Path) -> BridgeStatus:
    """The receiver's state for one workspace: ``off``, ``waiting``, ``connecting``,
    ``listening`` or ``unreachable``."""
    return _STATUS.setdefault(str(workspace_root), BridgeStatus())


def _enabled_signal_connector(workspace_root: str | Path) -> str | None:
    """The connector id of an enabled Signal pairing, if one exists."""
    from raiker.storage.sqlite import SQLiteStore

    for row in SQLiteStore(workspace_root).list_channel_pairings():
        if str(row.get("channel_type") or "") == "signal" and bool(row.get("enabled")):
            return str(row.get("connector_id") or "") or None
    return None


Handler = Callable[[str, InboundMessage], Awaitable[None]]


def parse_sse_line(line: str) -> dict[str, Any] | None:
    """One ``data:`` line of the stream as a JSON object, else ``None``."""
    if not line.startswith("data:"):
        return None
    try:
        parsed = json.loads(line[5:].strip())
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


async def pump_stream(
    lines: Any, connector_id: str, handle: Handler, status: BridgeStatus
) -> None:
    """Feed every message in one connected stream to ``handle``."""
    adapter = SignalAdapter()
    async for raw in lines:
        line = raw.strip() if isinstance(raw, str) else ""
        if not line or len(line) > MAX_LINE_BYTES:
            continue
        payload = parse_sse_line(line)
        if payload is None:
            continue
        message = adapter.parse_inbound(payload)
        if message is None:
            continue
        status.received += 1
        try:
            await handle(connector_id, message)
        except Exception as exc:  # noqa: BLE001 - one message must not end the stream
            # A refusal (sender not allowlisted, over budget, paused) is the
            # inbound path's answer and is already on the record; anything
            # else is logged by type only, never with the message.
            _LOG.debug("signal message not accepted: %s", type(exc).__name__)


async def run(
    workspace_root: str | Path,
    handle: Handler,
    stop: asyncio.Event,
    *,
    client_factory: Callable[[], Any] | None = None,
) -> None:
    """Listen for Signal messages until ``stop`` is set."""
    import httpx

    status = bridge_status(workspace_root)
    backoff = RETRY_INITIAL_SECONDS
    factory = client_factory or (lambda: httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=None)))

    async def wait(seconds: float) -> None:
        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=seconds)

    while not stop.is_set():
        try:
            connector_id = await asyncio.to_thread(_enabled_signal_connector, workspace_root)
        except Exception:  # noqa: BLE001 - a locked or migrating store is a later try
            connector_id = None
        account, base = signal_account(), signal_http_url()
        if connector_id is None:
            status.set("off")
            await wait(IDLE_SECONDS)
            continue
        if not account:
            status.set("waiting", "signal_account_missing")
            await wait(IDLE_SECONDS)
            continue
        if base is None:
            status.set("waiting", "signal_bridge_not_local")
            await wait(IDLE_SECONDS)
            continue
        url = f"{base}/api/v1/events?account={quote(account, safe='')}"
        status.set("connecting")
        try:
            async with factory() as client, client.stream(
                "GET", url, headers={"Accept": "text/event-stream"}
            ) as response:
                if response.status_code != 200:
                    raise ConnectionError(f"status_{response.status_code}")
                status.set("listening")
                backoff = RETRY_INITIAL_SECONDS
                pump = asyncio.create_task(
                    pump_stream(response.aiter_lines(), connector_id, handle, status)
                )
                stopper = asyncio.create_task(stop.wait())
                done, _ = await asyncio.wait({pump, stopper}, return_when=asyncio.FIRST_COMPLETED)
                for task in (pump, stopper):
                    if task not in done:
                        task.cancel()
                        with suppress(asyncio.CancelledError, Exception):
                            await task
                if pump in done:
                    pump.result()
                    raise ConnectionError("stream_ended")
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - every failure is a reconnect
            if stop.is_set():
                break
            status.set("unreachable", type(exc).__name__ if not str(exc) else str(exc)[:60])
            await wait(backoff + backoff * 0.2 * random.random())
            backoff = min(backoff * 2, RETRY_MAX_SECONDS)
    status.set("off")


def inbound_handler(app: Any) -> Handler:
    """Hand a Signal message to the inbound path every channel takes."""
    from starlette.requests import Request

    async def handle(connector_id: str, message: InboundMessage) -> None:
        from raiker.api.routes_channels import _handle_inbound

        # The inbound path reads the workspace and the dashboard service from
        # the application; a request carrying only that is what it needs. The
        # message did not come over HTTP, so nothing else of one is invented.
        request = Request({"type": "http", "app": app, "headers": [], "method": "POST", "path": "/"})
        await _handle_inbound(
            connector_id,
            sender_id=message.sender_id,
            text=message.text,
            request=request,
            conversation_scope=message.conversation_scope,
            event_key=message.event_id,
            sender_label=message.sender_label,
        )

    return handle
