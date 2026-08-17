"""MEM-04 — the runtime really records observations, and really refuses some.

The defect this file exists for was not that `raiker.memory.eidetic` was wrong;
it was that nothing called it. So every test here goes through the broker rather
than the library, and the assertion that matters most is the count query MEM-04
reproduced with: run a turn that reads a file, then look in the table.
"""
from __future__ import annotations

from pathlib import Path

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id
from raiker.contracts.models import ClientMetadata, ToolAction
from raiker.control.dashboard import DashboardService
from raiker.events.writer import EventLogWriter
from raiker.memory.capture import capture_tool_observation, source_type_for
from raiker.memory.eidetic import list_observations
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.storage.sqlite import SQLiteStore
from tests.machine_identity_helpers import IdentityBoundTestBroker as ToolBroker


def _broker(tmp_path: Path) -> ToolBroker:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    store = SQLiteStore(tmp_path)
    return ToolBroker(
        workspace_root=tmp_path,
        policy_engine=PolicyEngine(StaticPolicyConfig(tmp_path)),
        store=store,
        writer=EventLogWriter(store),
        principal_id="principal_owner",
    )


def _run(broker: ToolBroker, tool: str, arguments: dict[str, object]) -> None:
    broker.execute(
        ToolAction(new_id("act_"), tool, arguments, "medium", False),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
        client=ClientMetadata(type="test_harness", name="tests", version="0.0.0"),
    )


def _observations(tmp_path: Path) -> list[dict[str, object]]:
    store = SQLiteStore(tmp_path)
    with store.connect() as connection:
        return [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM eidetic_observations ORDER BY created_at, observation_id"
            ).fetchall()
        ]


def test_a_governed_read_records_one_observation(tmp_path: Path) -> None:
    (tmp_path / "notes.md").write_text(
        "The deployment runbook lives in docs and is reviewed every quarter.",
        encoding="utf-8",
    )
    broker = _broker(tmp_path)
    _run(broker, "read_file", {"path": "notes.md"})
    rows = _observations(tmp_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["tool_name"] == "read_file"
    assert row["source_type"] == "workspace_file"
    assert row["capture_status"] == "captured"
    assert len(str(row["content_sha256"])) == 64
    # The material itself is never a column. If this ever fails it means an
    # observation became a second, ungoverned copy of what the agent read.
    assert "runbook" not in str(row["summary"]).lower() or len(str(row["summary"])) <= 180
    assert "deployment runbook" not in " ".join(
        str(value) for key, value in row.items() if key not in {"summary"}
    )


def test_the_observation_points_back_at_a_real_event(tmp_path: Path) -> None:
    (tmp_path / "notes.md").write_text("A file long enough to be material.", encoding="utf-8")
    broker = _broker(tmp_path)
    _run(broker, "read_file", {"path": "notes.md"})
    row = _observations(tmp_path)[0]
    store = SQLiteStore(tmp_path)
    with store.connect() as connection:
        event = connection.execute(
            "SELECT event_type FROM events_index WHERE event_id = ?", (row["source_event_id"],)
        ).fetchone()
    assert event is not None and event["event_type"] == "tool_completed"


def test_bookkeeping_tools_produce_no_observation(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    _run(broker, "update_plan", {"steps": [{"title": "one", "status": "pending"}]})
    assert _observations(tmp_path) == []
    assert source_type_for("update_plan") is None


def test_credential_like_material_is_refused_and_says_so(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    observation = capture_tool_observation(
        store,
        tool_name="read_file",
        arguments={"path": ".env"},
        output={"content": "api_key = AKIA1234567890ABCDEFGHIJKLMNOPQRSTUV"},
        source_event_id="evt_1",
        session_id="sess_1",
        turn_id="turn_1",
        owner_principal_id="own_1",
    )
    assert observation is not None
    assert observation.capture_status == "skipped"
    assert observation.skip_reason == "observation_sensitivity_credential_like"
    # A digest of a credential is still a fact about the credential.
    assert observation.content_sha256 == ""
    assert observation.content_bytes == 0
    assert not observation.promotable_to_memory


def test_outside_material_is_observable_but_never_promotable(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    fetched = capture_tool_observation(
        store,
        tool_name="web_fetch",
        arguments={"url": "https://example.invalid/page"},
        output={"content": "A page of outside prose long enough to count as material."},
        source_event_id="evt_1",
        session_id="sess_1",
        turn_id="turn_1",
        owner_principal_id="own_1",
    )
    assert fetched is not None
    assert fetched.capture_status == "captured"
    assert fetched.source_type == "external_web"
    assert fetched.retention == "short_term_7_days"
    assert not fetched.promotable_to_memory


def test_a_gist_is_proposed_only_for_a_conclusion_and_stays_pending(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    capture_tool_observation(
        store,
        tool_name="read_file",
        arguments={"path": "notes.md"},
        output={"content": "Ordinary workspace prose that is long enough to be material."},
        source_event_id="evt_1",
        session_id="sess_1",
        turn_id="turn_1",
        owner_principal_id="own_1",
    )
    produced = capture_tool_observation(
        store,
        tool_name="create_document",
        arguments={"path": "report.md"},
        output={"content": "The generated report body, long enough to count as material."},
        source_event_id="evt_2",
        session_id="sess_1",
        turn_id="turn_1",
        owner_principal_id="own_1",
    )
    assert produced is not None
    with store.connect() as connection:
        gists = connection.execute(
            "SELECT observation_id, status FROM gist_memories"
        ).fetchall()
    assert len(gists) == 1
    assert str(gists[0]["observation_id"]) == produced.observation_id
    assert str(gists[0]["status"]) == "pending_review"


def test_observations_are_owner_scoped_and_deletable(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    mine = capture_tool_observation(
        store,
        tool_name="read_file",
        arguments={"path": "a.md"},
        output={"content": "Material belonging to the first owner, long enough to count."},
        source_event_id="evt_1",
        session_id="sess_1",
        turn_id="turn_1",
        owner_principal_id="own_1",
    )
    capture_tool_observation(
        store,
        tool_name="read_file",
        arguments={"path": "b.md"},
        output={"content": "Material belonging to the second owner, long enough to count."},
        source_event_id="evt_2",
        session_id="sess_2",
        turn_id="turn_2",
        owner_principal_id="own_2",
    )
    assert mine is not None
    assert [item.observation_id for item in list_observations(store=store, owner_principal_id="own_1")] == [
        mine.observation_id
    ]
    from raiker.memory.eidetic import delete_observations

    assert delete_observations(
        store=store, owner_principal_id="own_2", observation_ids={mine.observation_id}
    ) == []
    assert delete_observations(
        store=store, owner_principal_id="own_1", observation_ids={mine.observation_id}
    ) == [mine.observation_id]


def test_the_control_service_reports_captured_and_refused_separately(tmp_path: Path) -> None:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    store = SQLiteStore(tmp_path)
    owner = store.account_scope("principal_owner") or "principal_owner"
    capture_tool_observation(
        store,
        tool_name="read_file",
        arguments={"path": "a.md"},
        output={"content": "Ordinary workspace prose that is long enough to be material."},
        source_event_id="evt_1",
        session_id="sess_1",
        turn_id="turn_1",
        owner_principal_id=owner,
    )
    capture_tool_observation(
        store,
        tool_name="read_file",
        arguments={"path": ".env"},
        output={"content": "password = correcthorsebatterystaple-and-then-some"},
        source_event_id="evt_2",
        session_id="sess_1",
        turn_id="turn_1",
        owner_principal_id=owner,
    )
    result = DashboardService(tmp_path).list_observations("principal_owner")
    assert result.ok
    assert result.data["captured"] == 1
    assert result.data["skipped"] == 1
    refused = [
        item for item in result.data["observations"] if item["capture_status"] == "skipped"
    ]
    assert refused and refused[0]["skip_reason"].startswith("observation_sensitivity_")
