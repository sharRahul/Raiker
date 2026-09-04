"""Compatibility backlog #18 — the governed record had no wire.

Raiker records strictly more per governed action than any compared product
exports: the decision, its source, the gate that admitted it, the approval that
carried it, and a hash chain over the lot. All of it stayed inside the product.
[Cowork exports six event types over OpenTelemetry](https://claude.com/docs/cowork/monitoring);
Raiker exported none — for want of a wire, not for want of a record.

What has to hold about the wire:

* **Metadata by default, and metadata that is checkable.** A record carries the
  identifiers and the type, and *not* the summary — a summary names the object
  an action acted on, which is a file path more often than not.
* **Content is one explicit opt-in and is still redacted**, by the same function
  the on-screen record and the audit export pass through.
* **The credential is a name.** The value is read from the environment at send
  time and never stored, returned, or written to an artifact.
* **The cursor moves on delivery, never on attempt.** A run that failed re-sends;
  an export that quietly loses events is worse than one that fails loudly.
* **It is governed like everything else** — its own gate, defaulting off, and the
  export is an event in the log it exported.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import AgentEvent
from raiker.events.otlp import (
    METADATA_ATTRIBUTE_KEYS,
    logs_endpoint,
    logs_payload,
)
from raiker.events.writer import EventLogWriter
from raiker.phase_gates import ALL_CAPABILITIES, default_capability_gates
from raiker.runtime.authority import GovernedAction
from raiker.runtime.authority.models import Principal, RiskLevelValue
from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES
from raiker.runtime.executors.sandbox import SandboxError
from raiker.runtime.executors.tier2_telemetry import TelemetryExportExecutor
from raiker.storage.sqlite import SQLiteStore

_OWNER = "principal_owner"


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    from raiker.cli.principal_resolver import bootstrap_owner

    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    return tmp_path


@pytest.fixture()
def store(workspace: Path) -> SQLiteStore:
    return SQLiteStore(workspace)


def _principal(store: SQLiteStore) -> Principal:
    raw = store.get_principal(_OWNER)
    assert raw is not None
    return Principal(**raw)


def _write_events(store: SQLiteStore, count: int) -> None:
    writer = EventLogWriter(store)
    for _index in range(count):
        writer.append(
            AgentEvent(
                event_id=new_id("evt_"),
                timestamp=utc_now(),
                session_id="sess_1",
                turn_id="turn_1",
                event_type="action_proposed",
                actor="agent_runtime",
                payload={
                    # A path is content, which is the whole reason the summary
                    # is not a default attribute — and this one is benign, so
                    # the opt-in test can prove the payload really travelled
                    # rather than watching the redactor eat it for other reasons.
                    "summary": "/home/owner/notes/plan.md",
                    "risk_level": "low",
                    "api_key": "sk-live-should-never-travel",
                },
            )
        )


def _destination(store: SQLiteStore, **overrides: Any) -> str:
    destination_id = new_id("otlp_")
    store.create_telemetry_destination(
        destination_id=destination_id,
        principal_id=_OWNER,
        name=str(overrides.pop("name", "local")),
        endpoint_url=str(overrides.pop("endpoint_url", "http://127.0.0.1:4318")),
        header_ref=overrides.pop("header_ref", None),
        include_content=bool(overrides.pop("include_content", False)),
    )
    return destination_id


class _Collector:
    """A collector that records what it was sent and answers however told to."""

    def __init__(self, *, status: int = 200, fail: str | None = None) -> None:
        self.status = status
        self.fail = fail
        self.bodies: list[dict[str, Any]] = []
        self.headers: list[dict[str, str]] = []
        self.urls: list[str] = []

    def __call__(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        egress_allowlist: Any = None,
        headers: dict[str, str] | None = None,
        timeout: float = 15.0,
        max_bytes: int = 0,
    ) -> dict[str, Any]:
        if self.fail is not None:
            raise SandboxError(self.fail)
        self.urls.append(url)
        self.bodies.append(payload)
        self.headers.append(dict(headers or {}))
        return {"status": self.status, "body_text": "", "body_bytes": 0, "truncated": False}


def _action(destination_id: str) -> GovernedAction:
    return GovernedAction(
        action_id=new_id("act_"),
        principal_id=_OWNER,
        action_type="telemetry_export",
        tool_or_service_name="telemetry_export",
        arguments={"destination_id": destination_id},
        risk_level=RiskLevelValue.MEDIUM,
    )


def _records(collector: _Collector) -> list[dict[str, Any]]:
    return collector.bodies[0]["resourceLogs"][0]["scopeLogs"][0]["logRecords"]


class TestItIsGovernedLikeEverythingElse:
    def test_it_is_its_own_tier_2_capability_with_a_real_executor(self) -> None:
        assert "telemetry_export" in ALL_CAPABILITIES
        assert "telemetry_export" in REAL_EXECUTOR_CAPABILITIES
        # Tier 2 for the reason every Tier-2 capability is: it leaves the machine.
        assert default_capability_gates()["telemetry_export"].phase == 2

    def test_it_is_inert_until_the_owner_names_a_collector(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        """The gate ships enabled, as every capability with a real executor
        does. What makes that safe is not the gate: it is that a run with no
        destination has nowhere to send anything."""
        _write_events(store, 3)
        collector = _Collector()
        result = TelemetryExportExecutor(workspace, store, post_fn=collector).execute(
            _action("otlp_nonexistent"), _principal(store)
        )
        assert result.ok is False
        assert collector.bodies == []

    def test_it_is_reachable_only_through_the_router(self) -> None:
        from raiker.runtime.authority.router import CAPABILITY_GATE_MAP

        assert CAPABILITY_GATE_MAP["telemetry_export"] == "telemetry_export"

    def test_another_accounts_destination_is_not_exportable(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        store.create_telemetry_destination(
            destination_id="otlp_other",
            principal_id="principal_someone_else",
            name="theirs",
            endpoint_url="http://127.0.0.1:4318",
        )
        result = TelemetryExportExecutor(workspace, store, post_fn=_Collector()).execute(
            _action("otlp_other"), _principal(store)
        )
        assert result.ok is False
        assert result.reason_code == "telemetry_destination_not_found"


class TestWhatARecordCarries:
    def test_metadata_only_by_default_and_the_summary_is_not_metadata(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        _write_events(store, 2)
        collector = _Collector()
        result = TelemetryExportExecutor(workspace, store, post_fn=collector).execute(
            _action(_destination(store)), _principal(store)
        )
        assert result.ok, result.reason_code

        wire = json.dumps(collector.bodies[0])
        assert "notes/plan.md" not in wire
        assert "sk-live-should-never-travel" not in wire

        keys = {a["key"] for a in _records(collector)[0]["attributes"]}
        assert keys <= set(METADATA_ATTRIBUTE_KEYS)
        assert "event_type" in keys

    def test_content_is_an_opt_in_and_is_still_redacted(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        _write_events(store, 1)
        collector = _Collector()
        result = TelemetryExportExecutor(workspace, store, post_fn=collector).execute(
            _action(_destination(store, include_content=True)), _principal(store)
        )
        assert result.ok, result.reason_code

        bodies = [record["body"]["stringValue"] for record in _records(collector)]
        # The payload really travelled…
        assert any("notes/plan.md" in body for body in bodies)
        # …and the credential in it did not.
        assert not any("sk-live-should-never-travel" in body for body in bodies)

    def test_the_body_goes_to_the_logs_signal(self, workspace: Path, store: SQLiteStore) -> None:
        _write_events(store, 1)
        collector = _Collector()
        TelemetryExportExecutor(workspace, store, post_fn=collector).execute(
            _action(_destination(store)), _principal(store)
        )
        assert collector.urls[0] == "http://127.0.0.1:4318/v1/logs"

    def test_a_full_signal_url_is_not_doubled(self) -> None:
        assert logs_endpoint("http://c:4318/v1/logs") == "http://c:4318/v1/logs"
        assert logs_endpoint("http://c:4318/") == "http://c:4318/v1/logs"

    def test_an_unparseable_timestamp_is_zero_rather_than_now(self) -> None:
        payload = logs_payload(
            [{"event_id": "e", "event_type": "t", "timestamp": "not a time"}],
            include_content=False,
        )
        record = payload["resourceLogs"][0]["scopeLogs"][0]["logRecords"][0]
        assert record["timeUnixNano"] == "0"


class TestTheCredentialIsAName:
    def test_the_value_is_read_from_the_environment_and_sent(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("RAIKER_TEST_OTEL_HEADER", "Bearer collector-secret")
        _write_events(store, 1)
        collector = _Collector()
        result = TelemetryExportExecutor(workspace, store, post_fn=collector).execute(
            _action(_destination(store, header_ref="RAIKER_TEST_OTEL_HEADER")),
            _principal(store),
        )
        assert result.ok, result.reason_code
        assert collector.headers[0]["Authorization"] == "Bearer collector-secret"
        # And it is nowhere in what the run reports back.
        assert "collector-secret" not in json.dumps(result.artifacts)
        assert "collector-secret" not in (result.summary or "")

    def test_a_named_but_absent_variable_fails_closed(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("RAIKER_TEST_OTEL_ABSENT", raising=False)
        _write_events(store, 1)
        collector = _Collector()
        result = TelemetryExportExecutor(workspace, store, post_fn=collector).execute(
            _action(_destination(store, header_ref="RAIKER_TEST_OTEL_ABSENT")),
            _principal(store),
        )
        assert result.ok is False
        assert result.reason_code == "telemetry_credential_missing"
        # Nothing was sent unauthenticated to a destination that needs a credential.
        assert collector.bodies == []

    def test_the_stored_row_never_holds_a_credential(
        self, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("RAIKER_TEST_OTEL_HEADER", "Bearer collector-secret")
        _destination(store, header_ref="RAIKER_TEST_OTEL_HEADER")
        row = store.list_telemetry_destinations(_OWNER)[0]
        assert row["header_ref"] == "RAIKER_TEST_OTEL_HEADER"
        assert "collector-secret" not in json.dumps(row)


class TestTheCursorMovesOnDeliveryOnly:
    def test_a_second_run_sends_only_what_is_new(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        destination_id = _destination(store)
        executor = TelemetryExportExecutor(workspace, store, post_fn=_Collector())
        # Drain whatever bootstrapping the workspace already logged, so the
        # counts below are about this test's own events.
        executor.execute(_action(destination_id), _principal(store))

        _write_events(store, 3)
        first = executor.execute(_action(destination_id), _principal(store))
        assert first.artifacts["exported"] == 3

        _write_events(store, 1)
        second = executor.execute(_action(destination_id), _principal(store))
        assert second.artifacts["exported"] == 1

        third = executor.execute(_action(destination_id), _principal(store))
        assert third.ok, third.reason_code
        assert third.artifacts["exported"] == 0

    def test_a_failed_delivery_re_sends_rather_than_skipping(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        destination_id = _destination(store)
        TelemetryExportExecutor(workspace, store, post_fn=_Collector()).execute(
            _action(destination_id), _principal(store)
        )
        _write_events(store, 2)

        failed = TelemetryExportExecutor(
            workspace, store, post_fn=_Collector(fail="fetch_failed:URLError")
        ).execute(_action(destination_id), _principal(store))
        assert failed.ok is False
        assert failed.reason_code is not None
        assert "fetch_failed" in failed.reason_code

        collector = _Collector()
        recovered = TelemetryExportExecutor(workspace, store, post_fn=collector).execute(
            _action(destination_id), _principal(store)
        )
        assert recovered.artifacts["exported"] == 2

    def test_a_rejection_is_recorded_on_the_destination(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        _write_events(store, 1)
        destination_id = _destination(store)
        TelemetryExportExecutor(
            workspace, store, post_fn=_Collector(fail="http_error:503")
        ).execute(_action(destination_id), _principal(store))

        row = store.get_telemetry_destination(destination_id, _OWNER)
        assert row is not None
        assert "http_error:503" in str(row["last_status"])
        assert row["cursor_event_id"] is None

    def test_events_written_inside_one_second_are_neither_skipped_nor_repeated(
        self, store: SQLiteStore
    ) -> None:
        """`utc_now()` truncates to whole seconds, so ordering by timestamp
        alone would lose or duplicate the events a busy turn writes."""
        writer = EventLogWriter(store)
        stamp = utc_now()
        for _ in range(5):
            writer.append(
                AgentEvent(
                    event_id=new_id("evt_"),
                    timestamp=stamp,
                    session_id="sess_1",
                    turn_id="turn_1",
                    event_type="action_proposed",
                    actor="agent_runtime",
                    payload={},
                )
            )
        first = store.events_after_cursor(after_timestamp=None, after_seq=None, limit=2)
        rest = store.events_after_cursor(
            after_timestamp=first[-1]["timestamp"],
            after_seq=first[-1]["seq"],
            limit=10,
        )
        seen = [row["event_id"] for row in (*first, *rest)]
        # Nothing repeated across the page boundary, and nothing dropped at it.
        assert len(set(seen)) == len(seen)
        everything = store.events_after_cursor(
            after_timestamp=None, after_seq=None, limit=100
        )
        assert seen == [row["event_id"] for row in everything]


class TestItLeavesWithoutSomebodyPressingAButton:
    """BUG-276 — the wire delivered only on demand, so events accumulated
    behind the cursor until an owner looked.

    What has to hold about a cadence:

    * **A cadence the host will actually run.** The names come from the
      scheduler's own interval table, so a card cannot state a schedule the tick
      does not know how to advance.
    * **Claimed exactly once.** Two workers seeing one due destination must
      produce one delivery, not two.
    * **Anchored to the slot, not to the clock.** A delivery that took a minute
      must not drift the schedule by a minute every run.
    * **Off is off.** A destination the owner has taken off a timer keeps no
      claim in the queue.
    * **Paused means paused.** A delivery reaches the network, which is exactly
      the background work the host's pause switch exists to stop.
    """

    def test_a_cadence_names_a_schedule_the_scheduler_honours(self) -> None:
        from raiker.tasks.scheduler import RECURRING_INTERVALS, TELEMETRY_CADENCES

        assert TELEMETRY_CADENCES[0] == "off"
        # Not a superset and not a subset: one vocabulary, so a name the Tasks
        # board offers is a name a collector offers, with the same meaning.
        assert set(TELEMETRY_CADENCES[1:]) == set(RECURRING_INTERVALS)

    def test_setting_a_cadence_arms_a_next_run_and_off_disarms_it(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        from raiker.control.service import RuntimeControlService

        destination_id = _destination(store)
        row = store.get_telemetry_destination(destination_id, _OWNER)
        assert row is not None
        # Shipped default: what the card said before the column existed.
        assert row["delivery_cadence"] == "off"
        assert row["next_delivery_at"] is None

        service = RuntimeControlService(workspace)
        result = service.set_telemetry_destination_cadence(_OWNER, destination_id, "hourly")
        assert result.ok is True
        row = store.get_telemetry_destination(destination_id, _OWNER)
        assert row is not None
        assert row["delivery_cadence"] == "hourly"
        # Armed, and one interval away — turning a cadence on is not itself a
        # delivery the owner did not ask for.
        assert row["next_delivery_at"] is not None
        assert row["next_delivery_at"] > utc_now()

        assert service.set_telemetry_destination_cadence(_OWNER, destination_id, "off").ok
        row = store.get_telemetry_destination(destination_id, _OWNER)
        assert row is not None
        assert row["next_delivery_at"] is None

    def test_an_unknown_cadence_is_refused_rather_than_stored(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        from raiker.control.service import RuntimeControlService

        destination_id = _destination(store)
        result = RuntimeControlService(workspace).set_telemetry_destination_cadence(
            _OWNER, destination_id, "fortnightly"
        )
        assert result.ok is False
        assert result.reason_code == "telemetry_unknown_cadence"
        row = store.get_telemetry_destination(destination_id, _OWNER)
        assert row is not None
        assert row["delivery_cadence"] == "off"

    def test_a_due_destination_is_claimed_once(self, store: SQLiteStore) -> None:
        from raiker.tasks.scheduler import _next_delivery

        destination_id = _destination(store)
        store.set_telemetry_destination_cadence(
            destination_id, _OWNER, cadence="hourly", next_delivery_at="2020-01-01T00:00:00Z"
        )
        first = store.claim_due_telemetry_destinations(utc_now(), _next_delivery)
        second = store.claim_due_telemetry_destinations(utc_now(), _next_delivery)
        assert [row["destination_id"] for row in first] == [destination_id]
        # The claim *is* the advance, so the loser of the race finds nothing.
        assert second == []
        row = store.get_telemetry_destination(destination_id, _OWNER)
        assert row is not None
        assert str(row["next_delivery_at"]) > utc_now()

    def test_a_destination_that_is_off_or_disabled_is_never_claimed(
        self, store: SQLiteStore
    ) -> None:
        from raiker.tasks.scheduler import _next_delivery

        off = _destination(store, name="off")
        disabled = _destination(store, name="disabled")
        store.set_telemetry_destination_cadence(
            disabled, _OWNER, cadence="hourly", next_delivery_at="2020-01-01T00:00:00Z"
        )
        store.set_telemetry_destination_enabled(disabled, _OWNER, False)
        claimed = store.claim_due_telemetry_destinations(utc_now(), _next_delivery)
        assert [row["destination_id"] for row in claimed] == []
        assert off not in {row["destination_id"] for row in claimed}

    def test_the_next_run_is_anchored_to_the_claimed_slot(self) -> None:
        from datetime import UTC, datetime, timedelta

        from raiker.tasks.scheduler import _next_delivery

        # A slot an hour in the past on an hourly cadence lands on the next
        # whole hour from that slot, not an hour from now.
        slot = (datetime.now(UTC) - timedelta(minutes=50)).replace(microsecond=0)
        due = slot.isoformat().replace("+00:00", "Z")
        following = _next_delivery({"delivery_cadence": "hourly", "next_delivery_at": due})
        assert following == (slot + timedelta(hours=1)).isoformat().replace("+00:00", "Z")

    def test_an_unrecognised_stored_cadence_slows_down_rather_than_spinning(self) -> None:
        from raiker.tasks.scheduler import _next_delivery

        following = _next_delivery(
            {"delivery_cadence": "fortnightly", "next_delivery_at": "2020-01-01T00:00:00Z"}
        )
        # Daily, not "immediately": slower than asked for is the safe direction
        # for something that reaches the network.
        assert following > utc_now()

    def test_a_paused_host_delivers_nothing(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        import asyncio

        from raiker.app.host import HostControl
        from raiker.tasks.scheduler import TaskScheduler

        _write_events(store, 2)
        destination_id = _destination(store)
        store.set_telemetry_destination_cadence(
            destination_id, _OWNER, cadence="hourly", next_delivery_at="2020-01-01T00:00:00Z"
        )
        HostControl(workspace).pause()
        assert asyncio.run(TaskScheduler(workspace).deliver_due_telemetry()) == 0
        row = store.get_telemetry_destination(destination_id, _OWNER)
        assert row is not None
        # The claim is left where it was: it becomes due again on resume.
        assert row["next_delivery_at"] == "2020-01-01T00:00:00Z"
        assert row["last_attempt_at"] is None

    def test_a_wire_that_starts_failing_notifies_once_and_recovery_notifies_once(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        from raiker.tasks.scheduler import TELEMETRY_DELIVERY_KIND, TaskScheduler

        scheduler = TaskScheduler(workspace)
        destination = {
            "destination_id": _destination(store),
            "principal_id": _OWNER,
            "name": "local",
        }

        def notices() -> list[dict[str, Any]]:
            return [
                row
                for row in store.list_notifications(_OWNER)
                if row.get("kind") == TELEMETRY_DELIVERY_KIND
            ]

        scheduler._report_delivery(destination, "ok", "http_error:503")  # noqa: SLF001
        assert len(notices()) == 1
        # Still failing, and for the same reason: an owner does not need
        # seventy-two identical notices about one collector being down.
        scheduler._report_delivery(destination, "http_error:503", "http_error:503")  # noqa: SLF001
        scheduler._report_delivery(destination, "http_error:503", "http_error:504")  # noqa: SLF001
        assert len(notices()) == 1

        scheduler._report_delivery(destination, "http_error:504", "ok")  # noqa: SLF001
        assert len(notices()) == 2
        # And a wire that has been fine stays quiet.
        scheduler._report_delivery(destination, "ok", "ok")  # noqa: SLF001
        assert len(notices()) == 2

    def test_a_due_destination_delivers_through_the_same_governed_path(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        """End to end on the host tick: claim, route, attempt, record.

        The endpoint is a port nothing is listening on, so the delivery fails —
        which is the point. What this proves is that the *path* ran without a
        button: the claim was taken, the governed action was routed, and the
        outcome landed on the destination row where the card reads it.
        """
        import asyncio

        from raiker.tasks.scheduler import TaskScheduler

        _write_events(store, 2)
        destination_id = _destination(store, endpoint_url="http://127.0.0.1:4/")
        store.set_telemetry_destination_cadence(
            destination_id, _OWNER, cadence="hourly", next_delivery_at="2020-01-01T00:00:00Z"
        )
        asyncio.run(TaskScheduler(workspace).deliver_due_telemetry())

        row = store.get_telemetry_destination(destination_id, _OWNER)
        assert row is not None
        assert row["last_attempt_at"] is not None
        # Nothing landed, so the cursor did not move: the next run re-sends
        # exactly what this one could not carry.
        assert row["cursor_event_id"] is None
        # And the schedule advanced regardless, so a collector that is down does
        # not wedge the queue on one due slot.
        assert str(row["next_delivery_at"]) > utc_now()
