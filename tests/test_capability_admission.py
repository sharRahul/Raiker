"""The shared capability-admission read (GEP-01 / FIXED-279).

Eight modules used to carry their own copy of this lookup. Reading them side by
side found two disagreements neither was visible from — a scope difference and,
worse, three different answers to "what does an empty gate table mean". These
hold the one copy to the behaviour each of the eight had, and to the one rule
none of them may break: a broken read is off.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from raiker.contracts.ids import utc_now
from raiker.runtime.authority.admission import (
    CAPABILITY_UNSET_RESOLUTION,
    UNSET_OFF,
    UNSET_SHIPPED_DEFAULT,
    UNSET_SHIPPED_DEFAULT_UNSCOPED,
    capability_admission,
    gate_enabled,
    unset_resolution_for,
)
from raiker.runtime.authority.decision_modes import DecisionMode
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    return SQLiteStore(tmp_path)


def _row(capability: str, state: str) -> dict[str, Any]:
    now = utc_now()
    return {
        "capability": capability,
        "state": state,
        "requested_by": "p",
        "requested_at": now,
        "activated_by": "p",
        "activated_at": now,
        "reason": "test",
        "readiness_snapshot_json": "",
        "created_at": now,
        "updated_at": now,
    }


class _Broken:
    """A store whose every read raises, to prove the failure rule."""

    def account_scope(self, principal_id: str | None) -> str | None:
        return None

    def get_capability_gate_state(self, capability: str) -> Any:
        raise RuntimeError("storage unavailable")

    def get_capability_decision_mode(self, capability: str) -> Any:
        raise RuntimeError("storage unavailable")

    def get_latest_runtime_mode(self) -> Any:
        raise RuntimeError("storage unavailable")


# ── The rule none of the three resolutions may break ────────────────────────


@pytest.mark.parametrize(
    "capability",
    ["shell_execution", "web_fetch", "code_map_indexing"],
)
def test_a_broken_read_is_off_whatever_the_shipped_table_says(capability: str) -> None:
    """The fail-open this refactor could have introduced, asserted shut.

    `web_fetch` resolves an *empty* table to the shipped default, which is
    enabled. Collapsing "the read failed" into "nothing persisted" would have
    turned a storage error into an enabled egress capability.
    """
    admission = capability_admission(_Broken(), "anyone", capability)  # type: ignore[arg-type]
    assert admission.gate_enabled is False
    assert admission.refusal == "disabled_by_capability_gate"


# ── The three resolutions, and which capability uses which ──────────────────


def test_nothing_persisted_is_off_by_default(store: SQLiteStore) -> None:
    assert gate_enabled(store, None, "shell_execution") is False


def test_web_fetch_falls_back_to_the_shipped_table_for_any_caller(
    store: SQLiteStore,
) -> None:
    """RAIKER-2021 — an owner who turns web access off writes a row."""
    assert unset_resolution_for("web_fetch") == UNSET_SHIPPED_DEFAULT
    assert gate_enabled(store, None, "web_fetch") is True


def test_a_persisted_row_always_wins_over_the_shipped_table(store: SQLiteStore) -> None:
    store.upsert_capability_gate_state(_row("web_fetch", "disabled"))
    assert gate_enabled(store, None, "web_fetch") is False


def test_the_unscoped_fallback_applies_only_without_an_account(
    store: SQLiteStore, tmp_path: Path
) -> None:
    """The code map's documented three-branch resolution, in one assertion."""
    assert unset_resolution_for("code_map_indexing") == UNSET_SHIPPED_DEFAULT_UNSCOPED
    # No account: the shipped table answers.
    assert gate_enabled(store, None, "code_map_indexing") is True


def test_the_resolution_is_a_table_rather_than_a_call_site_decision() -> None:
    """Why the fork is data: the surface that *describes* a gate reads it too.

    The live drift this closed was between an enforcing path and the context
    bundle that described it, not between two enforcing paths.
    """
    assert unset_resolution_for("shell_execution") == UNSET_OFF
    assert set(CAPABILITY_UNSET_RESOLUTION) == {"web_fetch", "code_map_indexing", "subagents"}


def test_an_invalid_resolution_is_refused_rather_than_guessed(store: SQLiteStore) -> None:
    with pytest.raises(ValueError, match="capability_admission_unset_invalid"):
        capability_admission(store, None, "shell_execution", unset="whatever")


# ── Decision mode and refusal ───────────────────────────────────────────────


def test_the_default_decision_mode_is_ask(store: SQLiteStore) -> None:
    assert capability_admission(store, None, "shell_execution").decision_mode is DecisionMode.ASK


def test_deny_is_reported_separately_from_a_closed_gate(store: SQLiteStore) -> None:
    """An owner meets two different remedies, so they get two reason codes."""
    store.upsert_capability_gate_state(_row("shell_execution", "enabled_runtime"))
    store.upsert_capability_decision_mode({
        "capability": "shell_execution",
        "decision_mode": "deny",
        "set_by": "p",
        "reason": "test",
        "created_at": utc_now(),
        "updated_at": utc_now(),
    })
    admission = capability_admission(store, None, "shell_execution")
    assert admission.gate_enabled is True
    assert admission.admitted is False
    assert admission.refusal == "denied_by_decision_mode"


def test_an_enabled_gate_with_no_deny_is_admitted(store: SQLiteStore) -> None:
    store.upsert_capability_gate_state(_row("shell_execution", "enabled_runtime"))
    admission = capability_admission(store, None, "shell_execution")
    assert admission.admitted is True
    assert admission.refusal is None


# ── The runtime status: reported, never enforced ────────────────────────────


def test_the_runtime_status_is_carried_and_not_acted_on(store: SQLiteStore) -> None:
    """GEP-02 is an owner's decision, so the helper answers it and stops there.

    Whether stopping the agent runtime should also stop a read that leaves the
    machine has never been decided. Carrying the answer costs nothing; acting on
    it would decide an owner's question for them.
    """
    store.upsert_capability_gate_state(_row("web_fetch", "enabled_runtime"))
    admission = capability_admission(store, None, "web_fetch")
    # No runtime row at all: Raiker runs one runtime and it is on.
    assert admission.runtime_active is True
    # And the gate answer does not consult it either way.
    assert admission.admitted is True


# ── What the Permissions page is told (BUG-239) ─────────────────────────────
# FIXED-279 made the enforcing paths and the model's context bundle read the
# same table. It left the surface an owner actually decides from reading its
# own: on a fresh account Permissions said `web_fetch` was **Off** while the
# tool would have fetched. The gate view now carries both answers, so the page
# cannot describe a capability as off when the enforcing path would run it.


def test_a_gate_view_reports_the_resolution_its_enforcing_path_uses(
    tmp_path: Path,
) -> None:
    from raiker.cli.principal_resolver import bootstrap_owner
    from raiker.control.service import RuntimeControlService

    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    gates = {
        gate.capability: gate
        for gate in RuntimeControlService(tmp_path).list_capability_gates("principal_owner")
    }

    assert gates["web_fetch"].unset_resolution == UNSET_SHIPPED_DEFAULT
    assert gates["code_map_indexing"].unset_resolution == UNSET_SHIPPED_DEFAULT_UNSCOPED
    assert gates["shell_execution"].unset_resolution == UNSET_OFF


def test_the_view_says_a_capability_is_on_when_the_enforcing_path_would_run_it(
    tmp_path: Path,
) -> None:
    """The defect, stated as an assertion.

    An *account* is what makes the per-principal reading fail-closed, so it is
    the account case that used to disagree with itself: nothing is persisted,
    `state` reads disabled, and the tool would nevertheless fetch.
    """
    from raiker.cli.principal_resolver import bootstrap_owner
    from raiker.control.service import RuntimeControlService

    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    now = utc_now()
    SQLiteStore(tmp_path).upsert_account(
        "principal_owner", "owner", "x", "argon2id", now, now
    )
    gates = {
        gate.capability: gate
        for gate in RuntimeControlService(tmp_path).list_capability_gates("principal_owner")
    }

    assert gates["web_fetch"].state == "disabled"
    assert gates["web_fetch"].enforced_enabled is True
    # And the ordinary case is unchanged — off means off.
    assert gates["shell_execution"].state == "disabled"
    assert gates["shell_execution"].enforced_enabled is False


def test_every_gate_view_quotes_the_enforcing_paths_own_answer(tmp_path: Path) -> None:
    """The invariant, not the instance: one row disagreeing is the whole defect."""
    from raiker.cli.principal_resolver import bootstrap_owner
    from raiker.control.service import RuntimeControlService

    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    now = utc_now()
    store = SQLiteStore(tmp_path)
    store.upsert_account("principal_owner", "owner", "x", "argon2id", now, now)
    for gate in RuntimeControlService(tmp_path).list_capability_gates("principal_owner"):
        assert gate.enforced_enabled == gate_enabled(
            store, "principal_owner", gate.capability
        ), gate.capability
        assert gate.unset_resolution == unset_resolution_for(gate.capability)


def test_an_owners_stored_refusal_wins_in_the_view_as_it_does_in_the_path(
    tmp_path: Path,
) -> None:
    from raiker.cli.principal_resolver import bootstrap_owner
    from raiker.control.service import RuntimeControlService

    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    store = SQLiteStore(tmp_path)
    store.upsert_capability_gate_state(_row("web_fetch", "disabled"))
    gate = next(
        g
        for g in RuntimeControlService(tmp_path).list_capability_gates("principal_owner")
        if g.capability == "web_fetch"
    )
    assert gate.enforced_enabled is False
