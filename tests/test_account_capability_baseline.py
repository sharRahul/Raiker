"""A new account starts with a baseline; an old one is never re-seeded.

BUG-239. The owner's decision was to keep the three unset-gate resolutions and
expand fresh-account defaults *selectively and explicitly* instead — so this
holds the expansion to the three properties that make it defensible:

1. It is bounded. Nothing external, destructive or authority-changing can get
   into the list, whatever anyone writes in `baseline.py`, because the check is
   against `CAPABILITY_AUTHORITY`'s side-effect class rather than against a
   second copy of the list.
2. It only ever runs at account creation, and it never overwrites a row an owner
   wrote. An expanded default is for accounts that do not exist yet.
3. Enabled means *available through governance*. Decision modes are untouched,
   so every baseline capability still asks.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.contracts.ids import utc_now
from raiker.contracts.models import Role, User
from raiker.runtime.authority.admission import capability_admission
from raiker.runtime.authority.baseline import (
    ACCOUNT_BASELINE_VERSION,
    ACCOUNT_CAPABILITY_BASELINE,
    BASELINE_CAPABILITIES,
    BASELINE_EXCLUDED_SIDE_EFFECTS,
    baseline_rows,
    is_baseline_row,
)
from raiker.runtime.authority.capability_authority import CAPABILITY_AUTHORITY
from raiker.runtime.authority.decision_modes import DecisionMode
from raiker.runtime.authority.models import RAIKER_RUNTIME
from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES
from raiker.storage.sqlite import SQLiteStore

OWNER_ROLES = ("rl_owner",)


def _create_account(store: SQLiteStore, *, user_id: str = "u1") -> str:
    now = utc_now()
    store.insert_role(Role(
        role_id=OWNER_ROLES[0], name="owner",
        description="", is_system_role=True, created_at=now,
    ))
    principal_id = f"principal_{user_id}"
    created = store.create_initial_account_atomic(
        user=User(user_id, "Owner", None, True, now, now),
        principal_id=principal_id,
        role_ids=OWNER_ROLES,
        max_runtime_mode=RAIKER_RUNTIME,
        # With credentials, so `account_scope` resolves the principal to an
        # account and the per-principal gate rows are the ones read back. An
        # account-less principal falls through to the workspace-wide table,
        # which is a different question from the one these tests ask.
        username=f"owner-{user_id}",
        password_hash="argon2id$stub",
        hash_algo="argon2id",
    )
    assert created
    return principal_id


# ── What may be in it ───────────────────────────────────────────────────────


@pytest.mark.parametrize("row", ACCOUNT_CAPABILITY_BASELINE, ids=lambda r: r.capability)
def test_the_baseline_holds_nothing_that_reaches_outside_this_machine(row: object) -> None:
    """The bound, checked against the side-effect class rather than a list.

    This is the assertion that makes the baseline safe to extend: somebody
    adding `git_push_execution` or `shell_execution` here does not have to
    remember why they should not — the class says so and the test refuses.
    """
    capability = row.capability  # type: ignore[attr-defined]
    authority = CAPABILITY_AUTHORITY.get(capability)
    assert authority is not None, (
        f"{capability} is in the account baseline and has no authority record, "
        "so nothing states what it would cost"
    )
    assert authority.side_effect not in BASELINE_EXCLUDED_SIDE_EFFECTS, (
        f"{capability} is classified {authority.side_effect!r} and cannot be a "
        "fresh-account default: the baseline is local, reversible work only"
    )


def test_every_baseline_capability_can_actually_run() -> None:
    """Seeding a gate for something with no executor would be a default that
    turns on nothing, which is the inverse of the defect BUG-239 is about."""
    missing = sorted(BASELINE_CAPABILITIES - REAL_EXECUTOR_CAPABILITIES)
    assert missing == [], (
        f"The account baseline enables capabilities with no real executor: {missing}"
    )


def test_each_row_records_why_it_is_there() -> None:
    """A default nobody can read the reason for is one nobody can review."""
    for row in ACCOUNT_CAPABILITY_BASELINE:
        assert len(row.reason.split()) >= 10, (
            f"{row.capability}'s baseline reason is too short to be one: {row.reason!r}"
        )
    for record in baseline_rows(utc_now()):
        assert f"v{ACCOUNT_BASELINE_VERSION}" in record["reason"], (
            "A baseline row does not carry the baseline version it came from, "
            "so a later migration cannot tell which rows it wrote"
        )
        assert is_baseline_row(record["requested_by"])


# ── What it does to a workspace ─────────────────────────────────────────────


def test_a_new_account_starts_with_the_baseline_available(tmp_path: Path) -> None:
    """The point of the whole change: the two repository reads answer on a
    fresh account instead of waiting for the owner to find two switches."""
    store = SQLiteStore(tmp_path)
    principal_id = _create_account(store)
    for capability in sorted(BASELINE_CAPABILITIES):
        admission = capability_admission(store, principal_id, capability)
        assert admission.gate_enabled, (
            f"{capability} is in the account baseline and is not enabled for a "
            "newly created account"
        )


def test_the_baseline_does_not_enable_anything_else(tmp_path: Path) -> None:
    """A fresh account is still fail-closed everywhere the baseline does not
    name. `web_fetch` is the exception and is not this table's doing: its
    *unset resolution* ships on, which is RAIKER-2021 and predates this."""
    store = SQLiteStore(tmp_path)
    principal_id = _create_account(store)
    for capability in ("shell_execution", "git_push_execution", "subagents",
                       "memory_write_execution", "telemetry_export"):
        admission = capability_admission(store, principal_id, capability)
        assert not admission.gate_enabled, (
            f"{capability} is enabled on a fresh account and is not in the baseline"
        )


def test_the_baseline_leaves_every_decision_mode_alone(tmp_path: Path) -> None:
    """Enabled is *available through governance*, not unattended: a baseline
    capability still asks, because the baseline writes gates and nothing else."""
    store = SQLiteStore(tmp_path)
    principal_id = _create_account(store)
    for capability in sorted(BASELINE_CAPABILITIES):
        admission = capability_admission(store, principal_id, capability)
        assert admission.decision_mode == DecisionMode.ASK, (
            f"{capability} came out of the baseline in {admission.decision_mode} "
            "rather than asking"
        )


def test_an_owner_decision_is_never_replaced_by_the_baseline(tmp_path: Path) -> None:
    """Re-running it cannot undo a choice. The write is INSERT OR IGNORE, and
    this is the property that makes it safe if it is ever reached twice."""
    store = SQLiteStore(tmp_path)
    principal_id = _create_account(store)
    now = utc_now()
    store.upsert_principal_capability_gate_state(principal_id, {
        "capability": "code_map_indexing",
        "state": "disabled",
        "requested_by": principal_id,
        "requested_at": now,
        "activated_by": principal_id,
        "activated_at": now,
        "reason": "the owner turned it off",
        "readiness_snapshot_json": "",
        "created_at": now,
        "updated_at": now,
    })

    store.apply_account_capability_baseline(principal_id, utc_now())

    row = store.get_principal_capability_gate_state(principal_id, "code_map_indexing")
    assert row is not None
    assert row["state"] == "disabled", "the baseline overwrote an owner's own decision"
    assert row["reason"] == "the owner turned it off"


def test_an_existing_workspace_is_not_re_seeded(tmp_path: Path) -> None:
    """The baseline is applied inside account creation and nowhere else, so a
    workspace that predates it keeps whatever its owner decided."""
    store = SQLiteStore(tmp_path)
    now = utc_now()
    # A workspace whose account was created before the baseline existed: a
    # principal row and controls, with no gate rows of its own.
    store.insert_role(Role(
        role_id=OWNER_ROLES[0], name="owner",
        description="", is_system_role=True, created_at=now,
    ))
    store.insert_principal(
        principal_id="principal_legacy",
        principal_type="human",
        display_name="Legacy owner",
        role_ids=OWNER_ROLES,
        is_active=True,
    )
    store.initialize_principal_controls("principal_legacy")
    assert now  # the fixture above carries no gate rows; nothing to assert on it

    for capability in sorted(BASELINE_CAPABILITIES):
        row = store.get_principal_capability_gate_state("principal_legacy", capability)
        assert row is None, (
            f"{capability} was seeded into an existing workspace. The baseline "
            "runs at account creation only."
        )
