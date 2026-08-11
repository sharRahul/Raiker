"""Capability-agnostic behaviour monitoring, circuit breaking and containment.

``raiker/security/mcp_monitor.py`` is a complete behaviour monitor — a rolling
per-connection baseline, five deterministic anomaly rules, redacted findings, an
audit event, and three containment states with an automatic revocable pause —
and until this module none of it existed for any other capability family.
Plugins, connectors, subagents, providers and local execution had a *budget* and
nothing else: a component that failed every call spent its whole budget one
doomed call at a time, and a component that started misbehaving raised no
finding and could not be contained short of disabling the whole capability.

This module is that machinery, keyed by ``(principal, capability, subject)``
instead of by MCP connection:

* :class:`CapabilityMonitor` forms a rolling baseline from
  ``capability_activity_log`` and evaluates the same five rules — **new host**,
  **volume spike**, **tool-set swap**, **sensitive-data shape**, **error/refusal
  burst** — raising a redacted ``security_findings`` row and a
  ``capability_anomaly_detected`` event for each hit.
* :class:`CapabilityBreaker` is the ASI08 control the budgets were standing in
  for: consecutive failures per subject are counted in durable state, a
  threshold **opens** the breaker, further calls are refused with a stated
  reason code, and a half-open probe after a cooldown closes it again on the
  first success.
* :class:`CapabilityContainment` carries the owner-authoritative lifecycle in
  the vocabulary the MCP monitor already uses — ``active`` / ``paused`` /
  ``killed`` — with an owner-visible reason and a one-call resume.

The hard invariant is the MCP monitor's: no raw payload, token, argument value
or full URL ever reaches a finding, an event, or an activity row. The monitor
only ever receives redacted metadata — counts, hostnames (netloc), outcome
reason codes, and *classification labels*.

Containment is never a ban. Every state is revocable by the owner in one call,
in keeping with the security posture: allow, monitor, surface anomalies as
findings plus notifications, and give the owner an instant stop plus an
automatic revocable pause for the high-severity cases.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.security.mcp_monitor import (
    ERROR_BURST_THRESHOLD,
    STATE_ACTIVE,
    STATE_KILLED,
    STATE_PAUSED,
    TOOLCALL_SPIKE_FLOOR,
    VOLUME_SPIKE_FACTOR,
    VOLUME_SPIKE_FLOOR_BYTES,
    SecurityFinding,
    shape_sensitivity,
)

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

__all__ = [
    "CAPABILITY_CONNECTOR",
    "CAPABILITY_EXECUTION",
    "CAPABILITY_LABELS",
    "CAPABILITY_PLUGIN",
    "CAPABILITY_PROVIDER",
    "CAPABILITY_SUBAGENT",
    "CAPABILITY_TOOL",
    "BREAKER_COOLDOWN_SECONDS",
    "BREAKER_SOURCE",
    "BREAKER_FAILURE_THRESHOLD",
    "CapabilityBreaker",
    "CapabilityContainment",
    "CapabilityMonitor",
    "CapabilityTelemetry",
    "ContainmentRefusal",
    "ContainmentView",
    "shape_sensitivity",
]

# Events for capability monitoring share one append-only stream, as the MCP
# monitor's do, so the owner reviews containment in one place.
MONITOR_SESSION_ID = "capability"
MONITOR_SOURCE = "capability_monitor"
# The breaker's pauses are attributed separately from the monitor's, because
# only the breaker's own pause may be cleared automatically. A pause an anomaly
# raised is the owner's to review: the next successful call is not evidence that
# the tool set stopped changing underneath them.
BREAKER_SOURCE = "capability_breaker"

# The capability families registered against this substrate. These are the
# *governed* families a subject can belong to, not tool names: a subject is the
# specific connector, plugin, provider, subagent kind or executor being watched.
CAPABILITY_CONNECTOR = "connector"
CAPABILITY_PLUGIN = "plugin"
CAPABILITY_SUBAGENT = "subagent"
CAPABILITY_EXECUTION = "execution"
CAPABILITY_PROVIDER = "provider"
CAPABILITY_TOOL = "tool"

CAPABILITY_LABELS: dict[str, str] = {
    CAPABILITY_CONNECTOR: "Connector",
    CAPABILITY_PLUGIN: "Plugin",
    CAPABILITY_SUBAGENT: "Subagent",
    CAPABILITY_EXECUTION: "Local execution",
    CAPABILITY_PROVIDER: "Model provider",
    CAPABILITY_TOOL: "Tool",
}

# Circuit-breaker thresholds (BUG-76). Deliberately small and deterministic: a
# component that has failed three times in a row is down, and one doomed call
# per cooldown is enough to notice it has recovered.
BREAKER_FAILURE_THRESHOLD = 3
BREAKER_COOLDOWN_SECONDS = 60

# Notification kinds raised by this module.
NOTIFY_ANOMALY = "anomaly"
NOTIFY_CONTAINED = "capability_contained"
NOTIFY_RESUMED = "capability_resumed"


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class CapabilityTelemetry:
    """Redacted metadata about one governed capability invocation.

    Everything here is safe to persist: counts, hostnames (netloc only), outcome
    reason codes, and sensitivity *labels*. There is deliberately no field that
    can hold a raw payload, token, argument value, or full URL.
    """

    principal_id: str
    capability: str
    subject_id: str
    label: str = ""
    operation: str = ""
    hosts: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    calls: int = 0
    bytes_in: int = 0
    bytes_out: int = 0
    error_count: int = 0
    outcome: str = "ok"
    reason_code: str = ""
    # Classification label of the argument / result *shape* (never the value).
    arg_sensitivity: str | None = None
    result_sensitivity: str | None = None

    @property
    def ok(self) -> bool:
        return self.outcome != "error"


@dataclass(frozen=True)
class ContainmentView:
    """One subject's owner-visible containment state."""

    capability: str
    subject_id: str
    label: str
    state: str
    reason: str
    source: str
    finding_id: str | None
    failure_streak: int
    last_failure_code: str
    contained_at: str | None
    probe_after: str | None
    updated_at: str

    @property
    def contained(self) -> bool:
        return self.state in {STATE_PAUSED, STATE_KILLED}

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "capability_label": CAPABILITY_LABELS.get(self.capability, self.capability.title()),
            "subject_id": self.subject_id,
            "label": self.label or self.subject_id,
            "state": self.state,
            "reason": self.reason,
            "source": self.source,
            "finding_id": self.finding_id,
            "failure_streak": self.failure_streak,
            "last_failure_code": self.last_failure_code,
            "contained_at": self.contained_at,
            "probe_after": self.probe_after,
            "updated_at": self.updated_at,
        }


class ContainmentRefusal(RuntimeError):
    """Raised when a contained subject is asked to run.

    Carries the owner-visible state so the refusal names *what* is contained,
    *why*, and the one control that clears it — never a bare reason code.
    """

    def __init__(self, view: ContainmentView) -> None:
        super().__init__(view.reason or "capability_contained")
        self.view = view

    @property
    def reason_code(self) -> str:
        return (
            "capability_killed" if self.view.state == STATE_KILLED else "capability_paused"
        )

    def detail(self) -> dict[str, Any]:
        return {"reason_code": self.reason_code, "containment": self.view.to_dict()}


def _view(row: dict[str, Any]) -> ContainmentView:
    return ContainmentView(
        capability=str(row.get("capability", "")),
        subject_id=str(row.get("subject_id", "")),
        label=str(row.get("label") or ""),
        state=str(row.get("state") or STATE_ACTIVE),
        reason=str(row.get("reason") or ""),
        source=str(row.get("source") or "owner"),
        finding_id=row.get("finding_id"),
        failure_streak=int(row.get("failure_streak") or 0),
        last_failure_code=str(row.get("last_failure_code") or ""),
        contained_at=row.get("contained_at"),
        probe_after=row.get("probe_after"),
        updated_at=str(row.get("updated_at") or ""),
    )


class CapabilityContainment:
    """Owner-authoritative containment for any monitored capability subject.

    Shared by the monitor (the automatic, revocable pause a high-severity anomaly
    trips), the breaker (the same pause on a consecutive-failure threshold), and
    the owner's own instant stop, kill and resume. Every transition writes the
    subject's new state, emits its audit event, and raises an owner-facing
    notification — so the owner always sees, and can always revoke, containment.

    Owner-scoped throughout: a transition addresses
    ``(principal_id, capability, subject_id)`` and can never touch another
    owner's subject.
    """

    def __init__(
        self,
        store: SQLiteStore,
        *,
        writer: EventLogWriter | None = None,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self._store = store
        self._writer = writer or EventLogWriter(store)
        self._clock = clock

    def state(self, principal_id: str, capability: str, subject_id: str) -> ContainmentView:
        row = self._store.get_capability_containment(principal_id, capability, subject_id)
        if row is None:
            return ContainmentView(
                capability=capability, subject_id=subject_id, label="", state=STATE_ACTIVE,
                reason="", source="owner", finding_id=None, failure_streak=0,
                last_failure_code="", contained_at=None, probe_after=None, updated_at="",
            )
        return _view(row)

    def list(self, principal_id: str, *, capability: str | None = None) -> list[ContainmentView]:
        return [
            _view(row)
            for row in self._store.list_capability_containment(
                principal_id, capability=capability
            )
        ]

    def pause(
        self,
        principal_id: str,
        capability: str,
        subject_id: str,
        *,
        label: str = "",
        reason: str,
        source: str = "owner",
        finding_id: str | None = None,
        probe_after: str | None = None,
    ) -> ContainmentView:
        """Trip the revocable circuit breaker: refuse further calls until resumed."""
        return self._transition(
            principal_id, capability, subject_id, state=STATE_PAUSED, label=label,
            reason=reason, source=source, finding_id=finding_id, probe_after=probe_after,
            title=f"{CAPABILITY_LABELS.get(capability, capability.title())} paused",
        )

    def kill(
        self,
        principal_id: str,
        capability: str,
        subject_id: str,
        *,
        label: str = "",
        reason: str = "",
        source: str = "owner",
    ) -> ContainmentView:
        """The instant kill switch: refuse every call immediately. Revocable."""
        return self._transition(
            principal_id, capability, subject_id, state=STATE_KILLED, label=label,
            reason=reason or "This subject was stopped and will refuse every call until you resume it.",
            source=source, finding_id=None, probe_after=None,
            title=f"{CAPABILITY_LABELS.get(capability, capability.title())} stopped",
        )

    def resume(
        self,
        principal_id: str,
        capability: str,
        subject_id: str,
        *,
        source: str = "owner",
    ) -> ContainmentView:
        """Revoke containment: clear the pause/kill and reset the failure streak."""
        return self._transition(
            principal_id, capability, subject_id, state=STATE_ACTIVE, label="",
            reason="", source=source, finding_id=None, probe_after=None,
            title=f"{CAPABILITY_LABELS.get(capability, capability.title())} resumed",
            clear=True,
        )

    def _transition(
        self,
        principal_id: str,
        capability: str,
        subject_id: str,
        *,
        state: str,
        label: str,
        reason: str,
        source: str,
        finding_id: str | None,
        probe_after: str | None,
        title: str,
        clear: bool = False,
    ) -> ContainmentView:
        now = self._clock().astimezone(UTC).isoformat()
        stored = self._store.set_capability_containment(
            principal_id, capability, subject_id,
            state=state, label=label, reason=reason or None, source=source,
            finding_id=finding_id,
            failure_streak=0 if clear else None,
            last_failure_code="" if clear else None,
            contained_at=None if clear else now,
            probe_after=probe_after,
        )
        self._writer.append(
            make_event(
                session_id=MONITOR_SESSION_ID,
                turn_id=None,
                event_type=(
                    "capability_containment_cleared" if clear else "capability_contained"
                ),
                actor=source,
                payload={
                    "capability": capability,
                    "subject_id": subject_id,
                    "state": state,
                    "source": source,
                    "reason": reason,
                    "finding_id": finding_id,
                },
            )
        )
        self._store.insert_notification(
            principal_id=principal_id,
            kind=NOTIFY_RESUMED if clear else NOTIFY_CONTAINED,
            title=title,
            body=reason or f"'{label or subject_id}' can run again.",
            finding_id=finding_id,
            subject_id=subject_id,
        )
        return _view({**stored, "capability": capability, "subject_id": subject_id})


class CapabilityBreaker:
    """Consecutive-failure circuit breaker for any capability subject (BUG-76).

    Every bound Raiker previously enforced on a runaway loop was a *budget* —
    per-turn tool calls, subagent dimensions, API rate limits, per-job retries —
    and none of them carried failure state, so a hard-down provider or a broken
    connector consumed its whole budget one failing call at a time and the next
    turn started fresh and repeated it.

    This is the missing state. Failures are counted per subject in durable
    storage; the threshold **opens** the breaker via :class:`CapabilityContainment`
    (a revocable pause with a stated reason, not a new vocabulary); further calls
    are refused until a half-open probe is allowed after the cooldown; and the
    first success closes it again and clears the streak.
    """

    def __init__(
        self,
        store: SQLiteStore,
        *,
        writer: EventLogWriter | None = None,
        clock: Callable[[], datetime] = _now,
        threshold: int = BREAKER_FAILURE_THRESHOLD,
        cooldown_seconds: int = BREAKER_COOLDOWN_SECONDS,
    ) -> None:
        self._store = store
        self._clock = clock
        self._threshold = max(1, threshold)
        self._cooldown = max(1, cooldown_seconds)
        self.containment = CapabilityContainment(store, writer=writer, clock=clock)

    def state(self, principal_id: str, capability: str, subject_id: str) -> ContainmentView:
        return self.containment.state(principal_id, capability, subject_id)

    def allows(self, principal_id: str, capability: str, subject_id: str) -> bool:
        """True when a call may proceed (including a half-open probe)."""
        return self.refusal(principal_id, capability, subject_id) is None

    def refusal(
        self, principal_id: str, capability: str, subject_id: str
    ) -> ContainmentView | None:
        """The containment refusing this call, or ``None`` when it may proceed.

        A killed subject always refuses. A paused subject refuses until its
        cooldown lapses; after that exactly one call is let through as the
        half-open probe, and its outcome decides whether the breaker closes or
        the cooldown restarts.
        """
        view = self.containment.state(principal_id, capability, subject_id)
        if view.state == STATE_KILLED:
            return view
        if view.state != STATE_PAUSED:
            return None
        if not view.probe_after:
            # An owner-initiated pause has no probe window: only the owner clears it.
            return view
        try:
            probe_at = datetime.fromisoformat(view.probe_after)
        except ValueError:
            return view
        if probe_at.tzinfo is None:
            probe_at = probe_at.replace(tzinfo=UTC)
        return None if self._clock().astimezone(UTC) >= probe_at else view

    def require(self, principal_id: str, capability: str, subject_id: str) -> None:
        """Raise :class:`ContainmentRefusal` when the subject is contained."""
        refusal = self.refusal(principal_id, capability, subject_id)
        if refusal is not None:
            raise ContainmentRefusal(refusal)

    def record(
        self,
        principal_id: str,
        capability: str,
        subject_id: str,
        *,
        ok: bool,
        label: str = "",
        reason_code: str = "",
    ) -> ContainmentView:
        """Record one call's outcome and move the breaker accordingly."""
        view = self.containment.state(principal_id, capability, subject_id)
        if ok:
            return self._record_success(principal_id, capability, subject_id, view, label)
        return self._record_failure(
            principal_id, capability, subject_id, view, label, reason_code
        )

    def _record_success(
        self,
        principal_id: str,
        capability: str,
        subject_id: str,
        view: ContainmentView,
        label: str,
    ) -> ContainmentView:
        if view.state == STATE_PAUSED and view.source == BREAKER_SOURCE:
            # The half-open probe answered: the component is back, so the
            # breaker closes itself rather than waiting for the owner. Only a
            # pause the *breaker* opened clears this way — an anomaly's pause is
            # the owner's to review.
            return self.containment.resume(
                principal_id, capability, subject_id, source=BREAKER_SOURCE
            )
        if view.failure_streak == 0 and view.state == STATE_ACTIVE:
            return view
        stored = self._store.set_capability_containment(
            principal_id, capability, subject_id,
            state=view.state, label=label or view.label, reason=view.reason or None,
            source=view.source, finding_id=view.finding_id, failure_streak=0,
            last_failure_code="", contained_at=view.contained_at,
            probe_after=view.probe_after,
        )
        return _view({**stored, "capability": capability, "subject_id": subject_id})

    def _record_failure(
        self,
        principal_id: str,
        capability: str,
        subject_id: str,
        view: ContainmentView,
        label: str,
        reason_code: str,
    ) -> ContainmentView:
        streak = view.failure_streak + 1
        now = self._clock().astimezone(UTC)
        probe_after = (now + timedelta(seconds=self._cooldown)).isoformat()
        if view.state == STATE_PAUSED and view.source != BREAKER_SOURCE:
            # Already contained by an anomaly: count the failure, but leave the
            # owner's stated reason and its finding exactly as they are.
            stored = self._store.set_capability_containment(
                principal_id, capability, subject_id,
                state=view.state, label=label or view.label, reason=view.reason or None,
                source=view.source, finding_id=view.finding_id, failure_streak=streak,
                last_failure_code=reason_code, contained_at=view.contained_at,
                probe_after=view.probe_after,
            )
            return _view({**stored, "capability": capability, "subject_id": subject_id})
        if streak < self._threshold and view.state == STATE_ACTIVE:
            stored = self._store.set_capability_containment(
                principal_id, capability, subject_id,
                state=STATE_ACTIVE, label=label or view.label, reason=None,
                source=view.source, finding_id=None, failure_streak=streak,
                last_failure_code=reason_code, contained_at=None, probe_after=None,
            )
            return _view({**stored, "capability": capability, "subject_id": subject_id})
        if view.state == STATE_KILLED:
            return view
        # Threshold reached, or a half-open probe failed: (re)open the breaker.
        name = label or view.label or subject_id
        family = CAPABILITY_LABELS.get(capability, capability.title()).lower()
        reason = (
            f"Contained after {streak} consecutive failures"
            + (f" ({reason_code})" if reason_code else "")
            + f". Raiker will retry this {family} once after a short pause, or resume it yourself."
        )
        finding_id = self._store.insert_security_finding(
            principal_id=principal_id,
            source=BREAKER_SOURCE,
            severity="high",
            code="repeated_failures",
            summary=f"'{name}' failed {streak} times in a row and was contained.",
            redacted_detail={
                "capability": capability,
                "consecutive_failures": streak,
                "last_failure_code": reason_code,
                "cooldown_seconds": self._cooldown,
            },
            subject_id=subject_id,
        )
        contained = self.containment.pause(
            principal_id, capability, subject_id, label=name, reason=reason,
            source=BREAKER_SOURCE, finding_id=finding_id, probe_after=probe_after,
        )
        stored = self._store.set_capability_containment(
            principal_id, capability, subject_id,
            state=STATE_PAUSED, label=name, reason=reason, source=BREAKER_SOURCE,
            finding_id=finding_id, failure_streak=streak, last_failure_code=reason_code,
            contained_at=contained.contained_at, probe_after=probe_after,
        )
        return _view({**stored, "capability": capability, "subject_id": subject_id})


class CapabilityMonitor:
    """Observes governed capability invocations and raises redacted findings.

    The MCP monitor's rules, keyed by ``(principal, capability, subject)`` rather
    than by connection, so connectors, plugins, subagents and local execution get
    the baseline, the finding and the automatic revocable pause that monitored
    MCP connections have had all along.

    Owner-scoped throughout: every read (baseline) and every write (activity row,
    finding, containment) is keyed by ``principal_id``.
    """

    def __init__(
        self,
        store: SQLiteStore,
        *,
        writer: EventLogWriter | None = None,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self._store = store
        self._writer = writer or EventLogWriter(store)
        self._clock = clock
        self.breaker = CapabilityBreaker(store, writer=self._writer, clock=clock)
        self.containment = self.breaker.containment

    def observe(self, telemetry: CapabilityTelemetry) -> list[SecurityFinding]:
        """Record a redacted activity row, evaluate the rules, move the breaker."""
        prior = self._store.list_capability_activity(
            telemetry.principal_id, telemetry.capability, telemetry.subject_id, limit=50
        )
        known_tools = self._known_tools(prior)
        self._store.insert_capability_activity(
            principal_id=telemetry.principal_id,
            capability=telemetry.capability,
            subject_id=telemetry.subject_id,
            operation=telemetry.operation,
            hosts=list(telemetry.hosts),
            tools=list(telemetry.tools),
            calls=telemetry.calls,
            bytes_in=telemetry.bytes_in,
            bytes_out=telemetry.bytes_out,
            error_count=telemetry.error_count,
            outcome=telemetry.outcome,
            reason_code=telemetry.reason_code,
            arg_sensitivity=telemetry.arg_sensitivity,
            result_sensitivity=telemetry.result_sensitivity,
            observed_at=self._clock().astimezone(UTC).isoformat(),
        )
        name = telemetry.label or telemetry.subject_id
        findings = self._evaluate(telemetry, prior, known_tools, name)
        stored: list[SecurityFinding] = []
        for finding in findings:
            finding_id = self._store.insert_security_finding(
                principal_id=telemetry.principal_id,
                source=MONITOR_SOURCE,
                severity=finding.severity,
                code=finding.code,
                summary=finding.summary,
                redacted_detail={**finding.detail, "capability": telemetry.capability},
                subject_id=telemetry.subject_id,
            )
            resolved = replace(finding, finding_id=finding_id)
            self._emit_anomaly(telemetry, resolved)
            self._store.insert_notification(
                principal_id=telemetry.principal_id,
                kind=NOTIFY_ANOMALY,
                title=f"Security anomaly on '{name}'",
                body=finding.summary,
                finding_id=finding_id,
                subject_id=telemetry.subject_id,
            )
            stored.append(resolved)
        self._auto_pause_if_high_severity(telemetry, stored, name)
        self.breaker.record(
            telemetry.principal_id,
            telemetry.capability,
            telemetry.subject_id,
            ok=telemetry.ok,
            label=name,
            reason_code=telemetry.reason_code,
        )
        return stored

    @staticmethod
    def _known_tools(prior: list[dict[str, Any]]) -> set[str]:
        for row in prior:
            tools = {str(tool) for tool in (row.get("tools") or [])}
            if tools:
                return tools
        return set()

    def _auto_pause_if_high_severity(
        self, telemetry: CapabilityTelemetry, stored: list[SecurityFinding], name: str
    ) -> None:
        """Revocable circuit breaker: a high-severity finding pauses the subject.

        Transitions once — a subject already contained is left as-is, so one
        ongoing incident does not churn the timestamp or re-emit the event.
        """
        high = [finding for finding in stored if finding.severity == "high"]
        if not high:
            return
        current = self.containment.state(
            telemetry.principal_id, telemetry.capability, telemetry.subject_id
        )
        if current.state != STATE_ACTIVE:
            return
        codes = ", ".join(sorted({finding.code for finding in high}))
        self.containment.pause(
            telemetry.principal_id,
            telemetry.capability,
            telemetry.subject_id,
            label=name,
            reason=(
                f"Auto-paused: high-severity anomaly ({codes}). Resume when you have reviewed it."
            ),
            source=MONITOR_SOURCE,
            finding_id=high[0].finding_id,
        )

    # ── rule evaluation (the MCP monitor's rules, capability-agnostic) ──
    def _evaluate(
        self,
        telemetry: CapabilityTelemetry,
        prior: list[dict[str, Any]],
        known_tools: set[str],
        name: str,
    ) -> list[SecurityFinding]:
        findings: list[SecurityFinding] = []
        # A subject's very first invocation establishes the baseline silently:
        # with no history, everything is "new", which is not yet an anomaly.
        has_history = bool(prior)

        new_host = self._new_host(telemetry, prior, name) if has_history else None
        if new_host is not None:
            findings.append(new_host)
        if has_history:
            spike = self._volume_spike(telemetry, prior, name)
            if spike is not None:
                findings.append(spike)
        swap = self._tool_set_changed(telemetry, known_tools, name)
        if swap is not None:
            findings.append(swap)
        sensitive = self._sensitive_shape(telemetry, name, escalate=new_host is not None)
        if sensitive is not None:
            findings.append(sensitive)
        burst = self._error_burst(telemetry, prior, name)
        if burst is not None:
            findings.append(burst)
        return findings

    @staticmethod
    def _new_host(
        telemetry: CapabilityTelemetry, prior: list[dict[str, Any]], name: str
    ) -> SecurityFinding | None:
        known: set[str] = set()
        for row in prior:
            known.update(str(host) for host in (row.get("hosts") or []))
        new_hosts = sorted({host for host in telemetry.hosts if host and host not in known})
        if not new_hosts:
            return None
        return SecurityFinding(
            code="new_host",
            severity="medium",
            summary=f"'{name}' contacted a host it had not used before.",
            detail={"new_hosts": new_hosts, "known_host_count": len(known)},
        )

    @staticmethod
    def _volume_spike(
        telemetry: CapabilityTelemetry, prior: list[dict[str, Any]], name: str
    ) -> SecurityFinding | None:
        prior_bytes = [int(row.get("bytes_in", 0)) + int(row.get("bytes_out", 0)) for row in prior]
        prior_calls = [int(row.get("calls", 0)) for row in prior]
        avg_bytes = sum(prior_bytes) / len(prior_bytes) if prior_bytes else 0.0
        avg_calls = sum(prior_calls) / len(prior_calls) if prior_calls else 0.0
        current_bytes = telemetry.bytes_in + telemetry.bytes_out
        detail: dict[str, object] = {}
        if current_bytes > VOLUME_SPIKE_FLOOR_BYTES and current_bytes > VOLUME_SPIKE_FACTOR * max(
            avg_bytes, 1.0
        ):
            detail["current_bytes"] = current_bytes
            detail["baseline_avg_bytes"] = round(avg_bytes, 1)
        if telemetry.calls > TOOLCALL_SPIKE_FLOOR and telemetry.calls > VOLUME_SPIKE_FACTOR * max(
            avg_calls, 1.0
        ):
            detail["current_calls"] = telemetry.calls
            detail["baseline_avg_calls"] = round(avg_calls, 1)
        if not detail:
            return None
        return SecurityFinding(
            code="volume_spike",
            severity="medium",
            summary=f"'{name}' moved far more data or made far more calls than its baseline.",
            detail=detail,
        )

    @staticmethod
    def _tool_set_changed(
        telemetry: CapabilityTelemetry, known_tools: set[str], name: str
    ) -> SecurityFinding | None:
        current = {str(tool) for tool in telemetry.tools}
        if not known_tools or not current or current == known_tools:
            return None
        return SecurityFinding(
            code="tool_set_changed",
            severity="high",
            summary=(
                f"'{name}' changed the operations it advertises since the last check "
                "(possible substitution)."
            ),
            detail={
                "added": sorted(current - known_tools),
                "removed": sorted(known_tools - current),
            },
        )

    @staticmethod
    def _sensitive_shape(
        telemetry: CapabilityTelemetry, name: str, *, escalate: bool
    ) -> SecurityFinding | None:
        labels = [
            label
            for label in (telemetry.arg_sensitivity, telemetry.result_sensitivity)
            if label
        ]
        if not labels:
            return None
        return SecurityFinding(
            code="sensitive_shape",
            severity="high" if escalate else "medium",
            summary=f"'{name}' handled a value that looks like a secret or credential.",
            detail={
                "arg_sensitivity": telemetry.arg_sensitivity,
                "result_sensitivity": telemetry.result_sensitivity,
                "coincides_with_new_host": escalate,
            },
        )

    @staticmethod
    def _error_burst(
        telemetry: CapabilityTelemetry, prior: list[dict[str, Any]], name: str
    ) -> SecurityFinding | None:
        if telemetry.outcome != "error":
            return None
        consecutive = 1
        for row in prior:  # prior is most-recent-first
            if str(row.get("outcome")) == "error":
                consecutive += 1
            else:
                break
        # Fire once, exactly when the burst threshold is first crossed.
        if consecutive != ERROR_BURST_THRESHOLD:
            return None
        return SecurityFinding(
            code="error_burst",
            severity="high",
            summary=f"'{name}' hit repeated errors or refusals.",
            detail={
                "consecutive_error_invocations": consecutive,
                "invocation_error_count": telemetry.error_count,
                "last_failure_code": telemetry.reason_code,
            },
        )

    def _emit_anomaly(self, telemetry: CapabilityTelemetry, finding: SecurityFinding) -> None:
        self._writer.append(
            make_event(
                session_id=MONITOR_SESSION_ID,
                turn_id=None,
                event_type="capability_anomaly_detected",
                actor=MONITOR_SOURCE,
                payload={
                    "capability": telemetry.capability,
                    "subject_id": telemetry.subject_id,
                    "finding_id": finding.finding_id,
                    "code": finding.code,
                    "severity": finding.severity,
                    "summary": finding.summary,
                    "detail": finding.detail,
                },
            )
        )
