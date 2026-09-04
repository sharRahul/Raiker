"""Compatibility backlog #18 — the governed record had nowhere to go.

Raiker records more per governed action than any compared product exports: the
decision, its source, the gate that admitted it, the approval that carried it,
and a hash chain over the lot. Every bit of it stayed inside the product, so an
owner running Raiker beside an observability stack could see none of it there.
[Cowork exports six event types over OpenTelemetry](https://claude.com/docs/cowork/monitoring);
Raiker exported none — for want of a wire, not for want of a record.

This is that wire, and it is deliberately the *narrow* one:

* **Its own capability, and off until the owner turns it on.** `telemetry_export`
  is Tier 2 for the reason every Tier-2 capability is: it reaches the network. It
  takes the threat-model acknowledgement and the human confirmation that tier
  requires, and the owner's decision mode still governs each run.

  **BUG-281 — this used to say the gate "ships enabled".** The *shipped table*
  does set every real-executor capability to `enabled_runtime`, which is where
  that sentence came from; what an account actually meets is
  `unset_resolution_for("telemetry_export")`, and `telemetry_export` is not in
  `CAPABILITY_UNSET_RESOLUTION`, so an account with nothing persisted resolves
  **off**. A live round confirmed it: Observability said *"Telemetry export is
  turned off. Turn it on in Permissions."* on a fresh install. The behaviour is
  right — a capability that reaches the network should be the owner's explicit
  yes — and the sentence describing it was not.

  Two things are therefore true and are worth keeping apart, because the second
  is the one that would still matter if the first ever changed: the owner turns
  this on, **and** it is inert until they also name a collector. With no
  destination configured there is nowhere for a record to go, and adding one is a
  human-only act.
* **Metadata by default.** A record carries the identifiers and the type — the
  fields the event index keeps as columns because they are already metadata by
  construction — and not the summary, which names the object an action acted on
  and is a file path more often than not.
* **Content is one explicit opt-in, still redacted.** With `include_content` the
  body is the payload through `redact_event_payload`, the same function the
  on-screen record and the audit export pass through. A destination can never be
  told more than the owner can read in the product.
* **The cursor moves on delivery, never on attempt.** A run that could not
  deliver re-sends next time rather than skipping what it could not carry. An
  export that quietly loses events is worse than one that fails loudly.
* **It is audited itself.** The run reaches this executor through
  `route_action`, so exporting the log is an event in the log.

The credential is a *name*: `header_ref` names an environment variable holding an
`Authorization` value. The value is read at send time, sent, and never stored,
returned, or written to an artifact — the same shape the remote MCP transport
uses for the same reason.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from raiker.events.otlp import MAX_RECORDS_PER_RUN, logs_endpoint, logs_payload
from raiker.runtime.executors.base import ExecutionResult
from raiker.runtime.executors.sandbox import SandboxError, post_json_url

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction
    from raiker.storage.sqlite import SQLiteStore

#: How long one delivery may take before it is abandoned. A collector that
#: cannot answer inside this is a collector the next run will try again.
_TIMEOUT_SECONDS = 15.0

#: The most an OTLP body may be. A run that would exceed it is still bounded by
#: `MAX_RECORDS_PER_RUN` first; this is the backstop.
_MAX_BODY_BYTES = 4_000_000


class TelemetryExportExecutor:
    """Deliver governed events to one owner-configured OTLP destination."""

    capability = "telemetry_export"

    def __init__(
        self,
        workspace_root: str | Path,
        store: SQLiteStore,
        *,
        post_fn: Any | None = None,
    ) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store
        # Injectable so the delivery path is testable without a collector.
        self._post_fn = post_fn or post_json_url

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        principal_id = principal.principal_id if principal is not None else action.principal_id
        destination_id = str(action.arguments.get("destination_id", "")).strip()
        if not destination_id:
            return self._fail(action.action_id, "telemetry_destination_required")
        destination = self._store.get_telemetry_destination(destination_id, principal_id)
        if destination is None:
            # Owner-scoped: a caller cannot export to someone else's destination.
            return self._fail(action.action_id, "telemetry_destination_not_found")
        if not destination.get("enabled"):
            return self._fail(action.action_id, "telemetry_destination_disabled")

        endpoint = str(destination.get("endpoint_url", "")).strip()
        parsed = urlparse(endpoint)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return self._fail(action.action_id, "telemetry_invalid_endpoint")

        header_ref = str(destination.get("header_ref") or "").strip()
        headers: dict[str, str] = {}
        if header_ref:
            value = os.environ.get(header_ref)
            if not value:
                # Named but absent: fail closed rather than send unauthenticated
                # to a destination the owner said needs a credential.
                self._store.record_telemetry_attempt(
                    destination_id, principal_id, status="telemetry_credential_missing"
                )
                return self._fail(action.action_id, "telemetry_credential_missing")
            headers["Authorization"] = value

        rows = self._pending(destination)
        if not rows:
            self._store.record_telemetry_attempt(destination_id, principal_id, status="ok")
            return ExecutionResult(
                ok=True,
                capability=self.capability,
                action_id=action.action_id,
                summary="Nothing to export: every governed event is already delivered.",
                artifacts={"exported": 0, "destination": str(destination.get("name", ""))},
            )

        include_content = bool(destination.get("include_content"))
        payload = logs_payload(rows, include_content=include_content)
        try:
            result = self._post_fn(
                logs_endpoint(endpoint),
                payload,
                egress_allowlist=frozenset({parsed.netloc}),
                headers=headers,
                timeout=_TIMEOUT_SECONDS,
                max_bytes=_MAX_BODY_BYTES,
            )
        except SandboxError as exc:
            # `post_json_url` turns a rejection into `http_error:<status>` and a
            # transport failure into `fetch_failed:<type>`; both are carried as
            # they are, so the owner reads which of the two it was.
            reason = f"telemetry_delivery_failed:{exc}"
            self._store.record_telemetry_attempt(destination_id, principal_id, status=reason)
            return self._fail(action.action_id, reason)
        status = int(result.get("status", 0) or 0)
        if not 200 <= status < 300:
            reason = f"telemetry_rejected_{status}"
            self._store.record_telemetry_attempt(destination_id, principal_id, status=reason)
            return self._fail(action.action_id, reason)

        last = rows[-1]
        self._store.record_telemetry_attempt(
            destination_id,
            principal_id,
            status="ok",
            exported=len(rows),
            cursor_timestamp=str(last.get("timestamp", "")),
            cursor_event_id=str(last.get("event_id", "")),
            cursor_seq=int(last.get("seq") or 0),
        )
        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary=(
                f"Exported {len(rows)} governed event(s) to "
                f"'{destination.get('name', '')}' "
                f"({'with redacted content' if include_content else 'metadata only'})."
            ),
            artifacts={
                "exported": len(rows),
                "destination": str(destination.get("name", "")),
                "include_content": include_content,
                # Counts and the cursor only — never a record's contents.
                "cursor_event_id": str(last.get("event_id", "")),
            },
        )

    def _pending(self, destination: dict[str, Any]) -> list[dict[str, Any]]:
        rows = self._store.events_after_cursor(
            after_timestamp=destination.get("cursor_timestamp"),
            after_seq=destination.get("cursor_seq"),
            limit=MAX_RECORDS_PER_RUN,
        )
        if not destination.get("include_content"):
            return rows
        # Content was opted into, so the payload is read back from the log and
        # redacted at encoding time. A payload that cannot be read is exported
        # as metadata rather than skipped.
        from raiker.events.query import EventViewer

        service = EventViewer(self._store)
        for row in rows:
            try:
                payload = service.read_event_payload(str(row.get("event_id", "")))
            except Exception:  # noqa: BLE001 — an unreadable payload is not a failed export
                payload = None
            if isinstance(payload, dict):
                row["payload"] = payload
        return rows

    def _fail(self, action_id: str, reason_code: str) -> ExecutionResult:
        return ExecutionResult(
            ok=False,
            capability=self.capability,
            action_id=action_id,
            reason_code=reason_code,
            summary="Telemetry export failed closed.",
            artifacts={},
        )
