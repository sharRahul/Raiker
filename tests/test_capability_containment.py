"""The circuit breaker and the capability-agnostic monitor (BUG-76, BUG-77)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from raiker.security.capability_registry import classify_tool, telemetry_for_call
from raiker.security.containment import (
    CAPABILITY_CONNECTOR,
    CAPABILITY_PROVIDER,
    CAPABILITY_SUBAGENT,
    CAPABILITY_TOOL,
    CapabilityBreaker,
    CapabilityContainment,
    CapabilityMonitor,
    CapabilityTelemetry,
    ContainmentRefusal,
)
from raiker.storage.sqlite import SQLiteStore

OWNER = "owner-1"


class _Clock:
    """A clock the test moves, so a cooldown is asserted rather than waited out."""

    def __init__(self) -> None:
        self.now = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


def test_a_failing_subject_is_contained_rather_than_retried_to_exhaustion(
    tmp_path: Path,
) -> None:
    clock = _Clock()
    breaker = CapabilityBreaker(SQLiteStore(tmp_path), clock=clock)

    # Below the threshold the breaker only counts: a component is allowed to
    # fail twice without being taken away from the owner.
    for _ in range(2):
        breaker.record(OWNER, CAPABILITY_PROVIDER, "anthropic", ok=False, reason_code="timeout")
        assert breaker.allows(OWNER, CAPABILITY_PROVIDER, "anthropic")

    view = breaker.record(
        OWNER, CAPABILITY_PROVIDER, "anthropic", ok=False, reason_code="timeout"
    )
    assert view.state == "paused"
    assert view.failure_streak == 3
    assert "3 consecutive failures" in view.reason
    assert breaker.allows(OWNER, CAPABILITY_PROVIDER, "anthropic") is False


def test_a_contained_subject_refuses_with_a_stated_reason(tmp_path: Path) -> None:
    clock = _Clock()
    breaker = CapabilityBreaker(SQLiteStore(tmp_path), clock=clock)
    for _ in range(3):
        breaker.record(OWNER, CAPABILITY_TOOL, "web_fetch", ok=False, reason_code="egress_denied")

    with pytest.raises(ContainmentRefusal) as raised:
        breaker.require(OWNER, CAPABILITY_TOOL, "web_fetch")
    detail = raised.value.detail()
    assert detail["reason_code"] == "capability_paused"
    assert detail["containment"]["failure_streak"] == 3
    assert detail["containment"]["last_failure_code"] == "egress_denied"


def test_a_half_open_probe_closes_the_breaker_on_the_first_success(tmp_path: Path) -> None:
    clock = _Clock()
    breaker = CapabilityBreaker(SQLiteStore(tmp_path), clock=clock, cooldown_seconds=60)
    for _ in range(3):
        breaker.record(OWNER, CAPABILITY_CONNECTOR, "github", ok=False, reason_code="http_500")

    assert breaker.allows(OWNER, CAPABILITY_CONNECTOR, "github") is False
    clock.advance(61)
    # The cooldown has lapsed, so exactly one call is let through as the probe.
    assert breaker.allows(OWNER, CAPABILITY_CONNECTOR, "github") is True

    closed = breaker.record(OWNER, CAPABILITY_CONNECTOR, "github", ok=True)
    assert closed.state == "active"
    assert closed.failure_streak == 0


def test_a_failed_probe_restarts_the_cooldown(tmp_path: Path) -> None:
    clock = _Clock()
    breaker = CapabilityBreaker(SQLiteStore(tmp_path), clock=clock, cooldown_seconds=60)
    for _ in range(3):
        breaker.record(OWNER, CAPABILITY_CONNECTOR, "slack", ok=False, reason_code="http_500")
    clock.advance(61)

    reopened = breaker.record(
        OWNER, CAPABILITY_CONNECTOR, "slack", ok=False, reason_code="http_500"
    )

    assert reopened.state == "paused"
    assert reopened.failure_streak == 4
    assert breaker.allows(OWNER, CAPABILITY_CONNECTOR, "slack") is False


def test_the_owner_can_always_revoke_containment(tmp_path: Path) -> None:
    """Containment is never a ban: every state clears in one call."""
    store = SQLiteStore(tmp_path)
    containment = CapabilityContainment(store)

    containment.kill(OWNER, CAPABILITY_CONNECTOR, "gmail", label="Gmail", reason="Owner stop")
    assert containment.state(OWNER, CAPABILITY_CONNECTOR, "gmail").state == "killed"
    # A killed subject has no probe window — only the owner clears it.
    assert CapabilityBreaker(store).allows(OWNER, CAPABILITY_CONNECTOR, "gmail") is False

    resumed = containment.resume(OWNER, CAPABILITY_CONNECTOR, "gmail")
    assert resumed.state == "active"
    assert resumed.failure_streak == 0
    assert CapabilityBreaker(store).allows(OWNER, CAPABILITY_CONNECTOR, "gmail") is True


def test_containment_is_owner_scoped(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    breaker = CapabilityBreaker(store)
    for _ in range(3):
        breaker.record(OWNER, CAPABILITY_CONNECTOR, "github", ok=False, reason_code="http_500")

    assert breaker.allows("owner-2", CAPABILITY_CONNECTOR, "github") is True
    assert CapabilityContainment(store).list("owner-2") == []
    assert len(CapabilityContainment(store).list(OWNER)) == 1


def test_the_first_invocation_establishes_a_baseline_silently(tmp_path: Path) -> None:
    monitor = CapabilityMonitor(SQLiteStore(tmp_path))
    findings = monitor.observe(
        CapabilityTelemetry(
            principal_id=OWNER, capability=CAPABILITY_CONNECTOR, subject_id="github",
            label="GitHub", hosts=("api.github.com",), calls=1, bytes_out=100,
        )
    )
    assert findings == []


def test_a_new_host_raises_a_finding_against_the_subjects_baseline(tmp_path: Path) -> None:
    monitor = CapabilityMonitor(SQLiteStore(tmp_path))
    base = CapabilityTelemetry(
        principal_id=OWNER, capability=CAPABILITY_CONNECTOR, subject_id="github",
        label="GitHub", hosts=("api.github.com",), calls=1, bytes_out=100,
    )
    monitor.observe(base)

    findings = monitor.observe(
        CapabilityTelemetry(
            principal_id=OWNER, capability=CAPABILITY_CONNECTOR, subject_id="github",
            label="GitHub", hosts=("evil.example.com",), calls=1, bytes_out=100,
        )
    )

    codes = {finding.code for finding in findings}
    assert "new_host" in codes
    finding = next(item for item in findings if item.code == "new_host")
    assert finding.detail["new_hosts"] == ["evil.example.com"]


def test_a_high_severity_finding_auto_pauses_the_subject(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    monitor = CapabilityMonitor(store)
    monitor.observe(
        CapabilityTelemetry(
            principal_id=OWNER, capability=CAPABILITY_SUBAGENT, subject_id="research",
            label="research", tools=("read_file",), calls=1,
        )
    )

    findings = monitor.observe(
        CapabilityTelemetry(
            principal_id=OWNER, capability=CAPABILITY_SUBAGENT, subject_id="research",
            label="research", tools=("run_command",), calls=1,
        )
    )

    assert any(finding.severity == "high" for finding in findings)
    state = CapabilityContainment(store).state(OWNER, CAPABILITY_SUBAGENT, "research")
    assert state.state == "paused"
    assert "high-severity anomaly" in state.reason


def test_the_monitor_only_ever_stores_redacted_metadata(tmp_path: Path) -> None:
    """The MCP monitor's hard invariant, kept for every other family."""
    store = SQLiteStore(tmp_path)
    telemetry = telemetry_for_call(
        OWNER,
        "web_fetch",
        {"url": "https://user:hunter2@example.com/secret?token=abc"},
        status="success",
        output={"final_url": "https://example.com/page", "content": "plain page text"},
        error=None,
    )
    assert telemetry is not None
    CapabilityMonitor(store).observe(telemetry)

    rows = store.list_capability_activity(OWNER, telemetry.capability, telemetry.subject_id)
    assert len(rows) == 1
    serialised = str(rows[0])
    assert "hunter2" not in serialised
    assert "token=abc" not in serialised
    assert "plain page text" not in serialised
    # Only the netloc survives, and the payload is a count.
    assert rows[0]["hosts"] == ["example.com"]
    assert rows[0]["bytes_out"] > 0


def test_a_local_read_is_not_given_a_baseline(tmp_path: Path) -> None:
    """Monitoring a workspace read would produce noise, not signal."""
    assert classify_tool("read_file", {"path": "README.md"}) is None
    assert (
        telemetry_for_call(OWNER, "read_file", {}, status="success", output={}, error=None)
        is None
    )


def test_each_capability_family_is_registered_against_the_substrate() -> None:
    """BUG-77's coverage claim, asserted rather than described."""
    def family(tool_name: str, arguments: dict[str, str]) -> str:
        classified = classify_tool(tool_name, arguments)
        assert classified is not None, f"{tool_name} is not registered"
        return classified[0]

    assert family("connector_read", {"connector_id": "jira"}) == CAPABILITY_CONNECTOR
    assert family("plugin__acme__read", {}) == "plugin"
    assert family("spawn_subagent", {"name": "research"}) == CAPABILITY_SUBAGENT
    assert family("run_command", {}) == "execution"
    # Monitored MCP connections keep their own richer per-session monitor.
    assert classify_tool("mcp__server__tool", {}) is None
