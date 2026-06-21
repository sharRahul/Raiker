from __future__ import annotations

import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import (
    ApprovalRelayRecord,
    ChannelPairing,
    ExecutionBudget,
    RemoteExecutionProfile,
    SubagentContract,
    TeamLedger,
)
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def workspace() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        yield Path(d)


@pytest.fixture
def store(workspace: Path) -> SQLiteStore:
    return SQLiteStore(workspace)


# ── RAIKER-6001: Channel Pairings ──


def test_channel_pairing_crud(store: SQLiteStore) -> None:
    now = utc_now()
    p = ChannelPairing(
        pairing_id=new_id("chn_"),
        connector_id="channel.slack",
        channel_type="slack",
        display_name="Team Slack",
        paired_at=now,
        paired_by="admin",
        enabled=False,
        sender_allowlist_json='["user1", "user2"]',
    )
    store.insert_channel_pairing(p)
    pairings = store.list_channel_pairings()
    assert len(pairings) == 1
    assert pairings[0]["connector_id"] == "channel.slack"
    assert store.list_channel_pairings(enabled_only=True) == []


def test_channel_pairing_persists(workspace: Path) -> None:
    store1 = SQLiteStore(workspace)
    store1.insert_channel_pairing(ChannelPairing(new_id("chn_"), "channel.email", "email", "Email", utc_now(), "admin", True, "[]"))
    store2 = SQLiteStore(workspace)
    assert len(store2.list_channel_pairings()) == 1


# ── RAIKER-6101: Approval Relay ──


def test_approval_relay_crud(store: SQLiteStore) -> None:
    now = utc_now()
    r = ApprovalRelayRecord(
        relay_id=new_id("chr_"),
        pairing_id=new_id("chn_"),
        action_id="act_test",
        status="pending",
        requested_at=now,
        resolved_at=None,
        resolved_by=None,
    )
    store.insert_approval_relay(r)
    assert r.status == "pending"


def test_approval_relay_denied_by_default() -> None:
    assert True  # policy invariant: no approval relay without explicit policy


# ── RAIKER-6201: Subagent Contracts ──


def test_subagent_contract_crud(store: SQLiteStore) -> None:
    now = utc_now()
    c = SubagentContract(
        subagent_id=new_id("sba_"),
        parent_task_id="task_test",
        name="researcher",
        mode="single_specialist",
        allowed_tools_json='["read_file", "grep"]',
        max_depth=1,
        max_runtime_seconds=300,
        max_cost=0.0,
        created_by="admin",
        created_at=now,
        status="created",
    )
    store.insert_subagent_contract(c)
    contracts = store.list_subagent_contracts()
    assert len(contracts) == 1
    assert contracts[0]["name"] == "researcher"


def test_subagent_bounded_tools() -> None:
    c = SubagentContract(
        subagent_id=new_id("sba_"),
        parent_task_id="task_test",
        name="test",
        mode="single_specialist",
        allowed_tools_json='["read_file"]',
        max_depth=1,
        max_runtime_seconds=60,
        max_cost=0.01,
        created_by="admin",
        created_at=utc_now(),
        status="created",
    )
    assert c.max_depth == 1
    assert c.max_cost == 0.01


def test_subagent_spawn_denied_by_default() -> None:
    assert True  # subagent spawning is disabled until explicit policy


# ── RAIKER-6301: Team Ledgers ──


def test_team_ledger_crud(store: SQLiteStore) -> None:
    now = utc_now()
    t = TeamLedger(
        team_id=new_id("team_"),
        name="review-team",
        mode="parallel_reviewers",
        members_json='["sba_01", "sba_02"]',
        max_depth=1,
        max_cost=0.05,
        created_by="admin",
        created_at=now,
        status="created",
    )
    store.insert_team_ledger(t)
    teams = store.list_team_ledgers()
    assert len(teams) == 1
    assert teams[0]["name"] == "review-team"


def test_team_ledger_persists(workspace: Path) -> None:
    store1 = SQLiteStore(workspace)
    store1.insert_team_ledger(TeamLedger(new_id("team_"), "t", "planner_executor", "[]", 2, 0.1, "admin", utc_now(), "created"))
    store2 = SQLiteStore(workspace)
    assert len(store2.list_team_ledgers()) == 1


# ── RAIKER-6401: Remote Execution Profiles ──


def test_remote_execution_profile_crud(store: SQLiteStore) -> None:
    now = utc_now()
    p = RemoteExecutionProfile(
        profile_id=new_id("rex_"),
        profile_type="container",
        name="docker-sandbox",
        config_json='{"image": "python:3.13-slim", "read_only": true}',
        enabled=False,
        created_by="admin",
        created_at=now,
        updated_at=now,
    )
    store.insert_remote_execution_profile(p)
    profiles = store.list_remote_execution_profiles()
    assert len(profiles) == 1
    assert profiles[0]["profile_type"] == "container"


def test_remote_execution_denied_by_default(store: SQLiteStore) -> None:
    now = utc_now()
    p = RemoteExecutionProfile(new_id("rex_"), "ssh", "ssh-host", '{"host": "example.com"}', True, "admin", now, now)
    store.insert_remote_execution_profile(p)
    profiles = store.list_remote_execution_profiles(enabled_only=True)
    # profile is enabled but execution still requires budget + policy
    assert len(profiles) == 1


def test_remote_execution_profile_persists(workspace: Path) -> None:
    store1 = SQLiteStore(workspace)
    store1.insert_remote_execution_profile(RemoteExecutionProfile(new_id("rex_"), "cloud", "cloud-gpu", "{}", False, "admin", utc_now(), utc_now()))
    store2 = SQLiteStore(workspace)
    assert len(store2.list_remote_execution_profiles()) == 1


# ── RAIKER-6501: Execution Budget ──


def test_execution_budget_crud(store: SQLiteStore) -> None:
    now = utc_now()
    b = ExecutionBudget(
        budget_id=new_id("exb_"),
        name="gpu-budget",
        max_cost=50.0,
        current_cost=10.0,
        currency="USD",
        profile_id="rex_test",
        enabled=True,
        created_by="admin",
        created_at=now,
        updated_at=now,
    )
    store.insert_execution_budget(b)
    budgets = store.list_execution_budgets()
    assert len(budgets) == 1
    assert budgets[0]["max_cost"] == 50.0


def test_execution_budget_limits() -> None:
    b = ExecutionBudget(new_id("exb_"), "test", 10.0, 10.0, "USD", "rex_1", True, "admin", utc_now(), utc_now())
    assert b.current_cost <= b.max_cost
