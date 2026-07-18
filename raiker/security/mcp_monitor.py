"""Per-session MCP monitoring + anomaly detection (monitored MCP connections,
Phase B).

After each governed MCP session the connector executor hands *redacted*
telemetry to :class:`McpSessionMonitor`. The monitor:

1. writes one redacted ``mcp_session_log`` row (tool-call count, hosts contacted
   as netloc only, byte counts, error count, outcome) and emits an
   ``mcp_session_completed`` audit event;
2. forms a rolling per-connection baseline from that connection's prior rows;
   and
3. evaluates the anomaly rules — **new host**, **volume spike**, **tool-set
   swap**, **sensitive-data shape**, **error/refusal burst**. Each hit raises a
   redacted ``security_findings`` row and an ``mcp_anomaly_detected`` event.

The hard invariant: no raw payload, token, or host secret ever reaches a
finding, an event, or a session-log row. The monitor only ever receives
redacted metadata — counts, hostnames (netloc), and *classification labels*.
The sensitive-shape classification (:func:`shape_sensitivity`) runs transiently
in the executor on the raw value and hands the monitor only the label; the
value itself is discarded before it can be stored.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from raiker.contracts.ids import utc_now
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.memory.policy import MemorySensitivity, classify_memory_sensitivity

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

# Events for MCP monitoring are recorded under a fixed session id so the whole
# monitoring stream lives in one append-only log the owner can review.
MONITOR_SESSION_ID = "mcp"
MONITOR_SOURCE = "mcp_monitor"

# Anomaly thresholds. Deliberately conservative and deterministic so the rules
# are explainable and testable — no fabricated "smart" scoring.
VOLUME_SPIKE_FACTOR = 3.0
VOLUME_SPIKE_FLOOR_BYTES = 2000
TOOLCALL_SPIKE_FLOOR = 5
ERROR_BURST_THRESHOLD = 3

# The value shapes the sensitive-data rule treats as findings. Reuses the memory
# sensitivity classifier so there is a single definition of "looks secret".
_SENSITIVE_LABELS = frozenset(
    {MemorySensitivity.CREDENTIAL_LIKE.value, MemorySensitivity.SECRET_LIKE.value}
)


@dataclass(frozen=True)
class McpSessionTelemetry:
    """Redacted metadata about one governed MCP session.

    Everything here is safe to persist: counts, hostnames (netloc only), and
    sensitivity *labels*. There is deliberately no field that can hold a raw
    payload, token, argument value, or full URL.
    """

    principal_id: str
    server_id: str | None
    transport: str
    operation: str
    hosts: tuple[str, ...] = ()
    tool_calls: int = 0
    tools: tuple[str, ...] = ()
    bytes_in: int = 0
    bytes_out: int = 0
    error_count: int = 0
    outcome: str = "ok"
    # Classification label of the argument / result *shape* (never the value).
    arg_sensitivity: str | None = None
    result_sensitivity: str | None = None
    started_at: str | None = None
    ended_at: str | None = None


@dataclass(frozen=True)
class SecurityFinding:
    """A redacted anomaly finding. ``detail`` holds redacted metadata only."""

    code: str
    severity: str
    summary: str
    detail: dict[str, Any] = field(default_factory=dict)
    finding_id: str | None = None


def shape_sensitivity(text: str) -> str | None:
    """Classify the *shape* of a value and return only a sensitivity label for
    credential/secret-like shapes — never the value, and ``None`` for anything
    else. Called transiently in the executor; only the returned label is ever
    handed to the monitor."""
    if not text:
        return None
    label = classify_memory_sensitivity(text)
    if label.value in _SENSITIVE_LABELS:
        return label.value
    return None


class McpSessionMonitor:
    """Observes governed MCP sessions and raises redacted findings on anomalies.

    Owner-scoped throughout: every read (baseline, known tools) and every write
    (session log, finding) is keyed by ``principal_id`` so one owner's monitor
    can never see or influence another owner's connection.
    """

    def __init__(
        self,
        store: SQLiteStore,
        *,
        writer: EventLogWriter | None = None,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        self._store = store
        self._writer = writer or EventLogWriter(store)
        self._clock = clock

    def observe(self, telemetry: McpSessionTelemetry) -> list[SecurityFinding]:
        """Record a redacted session row, then evaluate the anomaly rules against
        this connection's rolling baseline. Returns the findings raised (also
        persisted + emitted as ``mcp_anomaly_detected`` events)."""
        now = self._clock()
        started = telemetry.started_at or now
        ended = telemetry.ended_at or now

        # Read the prior state BEFORE recording this session, so "new"/"changed"
        # are measured against history, not against the row we are about to add.
        prior = self._store.list_mcp_session_logs(
            telemetry.server_id, telemetry.principal_id, limit=50
        )
        server_row = (
            self._store.get_mcp_server(telemetry.server_id, telemetry.principal_id)
            if telemetry.server_id
            else None
        )
        name = str(server_row["name"]) if server_row else (telemetry.server_id or "connection")
        known_tools = {str(t) for t in (server_row.get("tools") or [])} if server_row else set()

        session_row_id = self._store.insert_mcp_session_log(
            server_id=telemetry.server_id,
            principal_id=telemetry.principal_id,
            transport=telemetry.transport,
            operation=telemetry.operation,
            hosts=list(telemetry.hosts),
            tool_calls=telemetry.tool_calls,
            bytes_in=telemetry.bytes_in,
            bytes_out=telemetry.bytes_out,
            error_count=telemetry.error_count,
            outcome=telemetry.outcome,
            started_at=started,
            ended_at=ended,
        )
        self._emit_session_completed(telemetry, session_row_id)

        findings = self._evaluate(telemetry, prior, known_tools, name)
        stored: list[SecurityFinding] = []
        for finding in findings:
            finding_id = self._store.insert_security_finding(
                principal_id=telemetry.principal_id,
                source=MONITOR_SOURCE,
                severity=finding.severity,
                code=finding.code,
                summary=finding.summary,
                redacted_detail=finding.detail,
                subject_id=telemetry.server_id,
            )
            self._emit_anomaly(telemetry, replace(finding, finding_id=finding_id))
            stored.append(replace(finding, finding_id=finding_id))
        return stored

    # ── rule evaluation ──
    def _evaluate(
        self,
        t: McpSessionTelemetry,
        prior: list[dict[str, Any]],
        known_tools: set[str],
        name: str,
    ) -> list[SecurityFinding]:
        findings: list[SecurityFinding] = []
        # The connection's very first session establishes the baseline silently:
        # with no history, everything is "new", which is not yet an anomaly.
        has_history = bool(prior)

        new_host = self._new_host(t, prior, name) if has_history else None
        if new_host is not None:
            findings.append(new_host)

        if has_history:
            spike = self._volume_spike(t, prior, name)
            if spike is not None:
                findings.append(spike)

        swap = self._tool_set_changed(t, known_tools, name)
        if swap is not None:
            findings.append(swap)

        sensitive = self._sensitive_shape(t, name, escalate=new_host is not None)
        if sensitive is not None:
            findings.append(sensitive)

        burst = self._error_burst(t, prior, name)
        if burst is not None:
            findings.append(burst)
        return findings

    @staticmethod
    def _new_host(
        t: McpSessionTelemetry, prior: list[dict[str, Any]], name: str
    ) -> SecurityFinding | None:
        known: set[str] = set()
        for row in prior:
            known.update(str(h) for h in (row.get("hosts") or []))
        new_hosts = sorted({h for h in t.hosts if h and h not in known})
        if not new_hosts:
            return None
        return SecurityFinding(
            code="new_host",
            severity="medium",
            summary=f"Connection '{name}' contacted a host it had not used before.",
            detail={"new_hosts": new_hosts, "known_host_count": len(known)},
        )

    @staticmethod
    def _volume_spike(
        t: McpSessionTelemetry, prior: list[dict[str, Any]], name: str
    ) -> SecurityFinding | None:
        prior_bytes = [int(r.get("bytes_in", 0)) + int(r.get("bytes_out", 0)) for r in prior]
        prior_calls = [int(r.get("tool_calls", 0)) for r in prior]
        avg_bytes = sum(prior_bytes) / len(prior_bytes) if prior_bytes else 0.0
        avg_calls = sum(prior_calls) / len(prior_calls) if prior_calls else 0.0
        current_bytes = t.bytes_in + t.bytes_out
        detail: dict[str, object] = {}
        if current_bytes > VOLUME_SPIKE_FLOOR_BYTES and current_bytes > VOLUME_SPIKE_FACTOR * max(
            avg_bytes, 1.0
        ):
            detail["current_bytes"] = current_bytes
            detail["baseline_avg_bytes"] = round(avg_bytes, 1)
        if t.tool_calls > TOOLCALL_SPIKE_FLOOR and t.tool_calls > VOLUME_SPIKE_FACTOR * max(
            avg_calls, 1.0
        ):
            detail["current_tool_calls"] = t.tool_calls
            detail["baseline_avg_tool_calls"] = round(avg_calls, 1)
        if not detail:
            return None
        return SecurityFinding(
            code="volume_spike",
            severity="medium",
            summary=f"Connection '{name}' moved far more data or made far more calls than its baseline.",
            detail=detail,
        )

    @staticmethod
    def _tool_set_changed(
        t: McpSessionTelemetry, known_tools: set[str], name: str
    ) -> SecurityFinding | None:
        # Only meaningful for a handshake that (re)discovered tools against a
        # previously known, non-empty tool set. Tool *names* are not secrets.
        current = {str(x) for x in t.tools}
        if not known_tools or not current or current == known_tools:
            return None
        return SecurityFinding(
            code="tool_set_changed",
            severity="high",
            summary=(
                f"Connection '{name}' changed the tools it advertises since the last "
                "check (possible server swap)."
            ),
            detail={
                "added": sorted(current - known_tools),
                "removed": sorted(known_tools - current),
            },
        )

    @staticmethod
    def _sensitive_shape(
        t: McpSessionTelemetry, name: str, *, escalate: bool
    ) -> SecurityFinding | None:
        labels = [label for label in (t.arg_sensitivity, t.result_sensitivity) if label]
        if not any(label in _SENSITIVE_LABELS for label in labels):
            return None
        # High-severity when it coincides with a new host (proposed auto-pause
        # case); otherwise a notify-level finding.
        return SecurityFinding(
            code="sensitive_shape",
            severity="high" if escalate else "medium",
            summary=f"Connection '{name}' handled a value that looks like a secret or credential.",
            detail={
                "arg_sensitivity": t.arg_sensitivity,
                "result_sensitivity": t.result_sensitivity,
                "coincides_with_new_host": escalate,
            },
        )

    @staticmethod
    def _error_burst(
        t: McpSessionTelemetry, prior: list[dict[str, Any]], name: str
    ) -> SecurityFinding | None:
        if t.outcome != "error":
            return None
        consecutive = 1
        for row in prior:  # prior is most-recent-first
            if str(row.get("outcome")) == "error":
                consecutive += 1
            else:
                break
        # Fire once, exactly when the burst threshold is first crossed — not
        # again on every further error while still above it, which would flood
        # the owner with duplicate high-severity findings for one ongoing burst.
        if consecutive != ERROR_BURST_THRESHOLD:
            return None
        return SecurityFinding(
            code="error_burst",
            severity="high",
            summary=f"Connection '{name}' hit repeated errors or auth failures.",
            detail={
                "consecutive_error_sessions": consecutive,
                "session_error_count": t.error_count,
            },
        )

    # ── audit events (redacted) ──
    def _emit_session_completed(self, t: McpSessionTelemetry, session_row_id: str) -> None:
        self._writer.append(
            make_event(
                session_id=MONITOR_SESSION_ID,
                turn_id=None,
                event_type="mcp_session_completed",
                actor=MONITOR_SOURCE,
                payload={
                    "session_row_id": session_row_id,
                    "server_id": t.server_id,
                    "transport": t.transport,
                    "operation": t.operation,
                    "hosts": list(t.hosts),
                    "tool_calls": t.tool_calls,
                    "tool_count": len(t.tools),
                    "bytes_in": t.bytes_in,
                    "bytes_out": t.bytes_out,
                    "error_count": t.error_count,
                    "outcome": t.outcome,
                },
            )
        )

    def _emit_anomaly(self, t: McpSessionTelemetry, finding: SecurityFinding) -> None:
        self._writer.append(
            make_event(
                session_id=MONITOR_SESSION_ID,
                turn_id=None,
                event_type="mcp_anomaly_detected",
                actor=MONITOR_SOURCE,
                payload={
                    "server_id": t.server_id,
                    "finding_id": finding.finding_id,
                    "code": finding.code,
                    "severity": finding.severity,
                    "summary": finding.summary,
                    "detail": finding.detail,
                },
            )
        )
