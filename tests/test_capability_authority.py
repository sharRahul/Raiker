"""Every side-effect capability answers the two questions nothing asked before.

BUG-293 / RR-AUTHORITY-01. `DEC-16` step 8 wants five columns per real
side-effect capability. Three were mechanical — an executor, an entry path, a
Permissions description — and two had no home: **what it would cost if it ran
ungoverned**, and **the test that proves it will not.**

`raiker/runtime/authority/capability_authority.py` is the first. This file is
the second, and it is deliberately parameterised over the capability rather than
asserted once over a set: a test id that carries the capability's own name is a
per-capability proof, and an intersection of two sets is not. That distinction
is the whole of the finding — the bypass property *was* established here, but
structurally: `route_action`'s callers are enumerated, so no current path skips
the chokepoint. That says nothing about whether each of the forty-eight
capabilities is refused when its own gate is off.

What writing the table out found is recorded as FIXED-542: `image_generation`
had a real executor, a switch on Permissions, a docstring promising the gate
applied — and no row in `CAPABILITY_GATE_MAP`, so `check_capability_gate` found
no gate and returned `None`. The generic test below fails for exactly that
shape, which is why it is the proof rather than a formality.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import PolicyDecision, Role
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority import GovernedAction, RuntimeAuthority
from raiker.runtime.authority.capability_authority import (
    CAPABILITY_AUTHORITY,
    GENERIC_BYPASS_TEST,
    SIDE_EFFECT_CLASSES,
)
from raiker.runtime.authority.entry_paths import CAPABILITY_ENTRY_PATHS
from raiker.runtime.authority.models import Principal, PrincipalType, RiskLevelValue
from raiker.runtime.authority.router import CAPABILITY_GATE_MAP
from raiker.runtime.executors import (
    REAL_EXECUTOR_CAPABILITIES,
    ExecutionResult,
    ExecutorRegistry,
)
from raiker.storage.sqlite import SQLiteStore

CAPABILITIES = sorted(REAL_EXECUTOR_CAPABILITIES)


# ── The registry holds itself to its own bar ────────────────────────────────


def test_every_real_executor_capability_states_what_it_would_cost() -> None:
    """A capability that can run is one whose cost somebody has written down."""
    missing = sorted(REAL_EXECUTOR_CAPABILITIES - set(CAPABILITY_AUTHORITY))
    assert missing == [], (
        "A capability has a real executor and no authority record, so nothing "
        "says what it would cost if it ran ungoverned or what stops it. Add it "
        f"to capability_authority.py: {missing}"
    )


def test_the_registry_names_no_capability_that_cannot_run() -> None:
    """The other direction: a row for something with no executor is a claim
    about a thing that does not happen, which is worse than no row."""
    extra = sorted(set(CAPABILITY_AUTHORITY) - REAL_EXECUTOR_CAPABILITIES)
    assert extra == [], (
        "An authority record names a capability with no real executor. Remove "
        f"it, or register the executor: {extra}"
    )


@pytest.mark.parametrize("capability", CAPABILITIES)
def test_the_threat_sentence_is_not_the_capability_name_again(capability: str) -> None:
    """The bar `test_an_inert_gate_says_what_really_governs_it` already sets.

    A threat model that reads "web fetch could fetch the web" is the failure
    this column exists to prevent, so the sentence has to be long enough to say
    something and must not be the humanised capability name with a verb.
    """
    row = CAPABILITY_AUTHORITY[capability]
    assert row.side_effect in SIDE_EFFECT_CLASSES
    words = row.ungoverned.split()
    assert len(words) >= 16, (
        f"{capability}'s ungoverned-consequence sentence is too short to be a "
        f"threat model: {row.ungoverned!r}"
    )
    humanised = capability.replace("_", " ")
    assert humanised not in row.ungoverned.lower(), (
        f"{capability}'s threat sentence restates its own name rather than "
        f"naming a consequence: {row.ungoverned!r}"
    )
    assert len(row.authority.split()) >= 10, (
        f"{capability}'s authority requirement is too short to be one: "
        f"{row.authority!r}"
    )


@pytest.mark.parametrize("capability", CAPABILITIES)
def test_the_named_bypass_test_exists(capability: str) -> None:
    """A named test that does not exist is worse than an unnamed one.

    Checks the file, the function and — for the generic parameterised proof —
    that the bracketed parameter is this capability rather than another one's,
    which is the copy-paste this column is most likely to acquire.
    """
    node_id = CAPABILITY_AUTHORITY[capability].bypass_test
    path_part, _, rest = node_id.partition("::")
    function, _, param = rest.partition("[")
    source = Path(path_part)
    assert source.is_file(), f"{capability} names a bypass test file that is not there: {path_part}"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    defined = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    assert function in defined, (
        f"{capability} names {function!r} in {path_part}, which does not define it"
    )
    if param:
        assert param.rstrip("]") == capability, (
            f"{capability} names the bypass test of another capability: {node_id}"
        )


def test_the_generic_proof_covers_every_capability_that_defaults_to_it() -> None:
    """The default is only honest while the parameterisation is the full set."""
    defaulted = {
        cap
        for cap, row in CAPABILITY_AUTHORITY.items()
        if row.bypass_test.startswith(GENERIC_BYPASS_TEST)
    }
    assert defaulted <= set(CAPABILITIES), (
        "A row defaults to the generic proof for a capability the generic proof "
        f"is not parameterised over: {sorted(defaulted - set(CAPABILITIES))}"
    )


def test_every_capability_that_can_run_has_a_gate_to_refuse_it() -> None:
    """FIXED-542 — the finding, kept as the regression it came from.

    `image_generation` had an executor, a switch and a docstring promising the
    gate applied, and `CAPABILITY_GATE_MAP` had no key for it — so the gate
    check found nothing to check and returned `None`. This is the one-line
    version of the parameterised proof below, named separately so the reason it
    exists survives a refactor of the proof.
    """
    gated = set(CAPABILITY_GATE_MAP.values())
    ungated = sorted(REAL_EXECUTOR_CAPABILITIES - gated)
    assert ungated == [], (
        "A capability has a real executor and no name in CAPABILITY_GATE_MAP, "
        "so routing its action consults no gate and the owner's switch decides "
        f"nothing: {ungated}"
    )


# ── The negative proof itself ───────────────────────────────────────────────


@dataclass
class _AllowEverythingPolicy:
    """Says allow to everything, so the only thing that can refuse is the gate.

    The point of a negative bypass test is to remove every *other* reason the
    action might not run. A policy that denied would make all forty-eight pass
    while proving nothing about the gate.
    """

    def review(self, tool_action: Any) -> PolicyDecision:
        return PolicyDecision(
            decision_id=new_id("pol_"),
            action_id=tool_action.action_id,
            decision="allow",
            reasons=["bypass_probe"],
            requires_user_approval=False,
            risk_level=tool_action.risk_level,
        )


class _RanAnyway(Exception):
    """Raised by the probe executor. Reaching it is the failure."""


class _ProbeExecutor:
    """An executor that cannot be reached without the gate having allowed it."""

    def __init__(self, capability: str) -> None:
        self.capability = capability
        self.called = False

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        self.called = True
        raise _RanAnyway(self.capability)


def _owner(store: SQLiteStore) -> Principal:
    now = utc_now()
    store.insert_role(Role(
        role_id="rl_owner", name="owner",
        description="", is_system_role=True, created_at=now,
    ))
    store.insert_principal(
        principal_id="p_owner",
        principal_type=PrincipalType.HUMAN.value,
        display_name="Owner",
        role_ids=("rl_owner",),
        is_active=True,
    )
    return Principal(
        principal_id="p_owner",
        principal_type=PrincipalType.HUMAN,
        display_name="Owner",
        role_ids=("rl_owner",),
        is_active=True,
    )


def _disable(store: SQLiteStore, capability: str) -> None:
    """The owner's off switch, written the way the control plane writes it."""
    now = utc_now()
    store.upsert_capability_gate_state({
        "capability": capability,
        "state": "disabled",
        "requested_by": "p_owner",
        "requested_at": now,
        "activated_by": "p_owner",
        "activated_at": now,
        "reason": "negative bypass probe",
        "readiness_snapshot_json": "",
        "created_at": now,
        "updated_at": now,
    })


@pytest.mark.parametrize("capability", CAPABILITIES)
def test_the_gate_refuses_before_the_executor_runs(
    capability: str, tmp_path: Path
) -> None:
    """With the gate off, the executor is never reached — per capability.

    The probe executor raises if it is entered, so this cannot pass by the
    executor happening to refuse for its own reasons: the claim is about the
    *gate*, which is the boundary an owner is looking at when they turn a
    switch off.

    Every action type that maps to the capability is probed, not just one, so a
    capability with several doors — `web_fetch` has four, `file_write_execution`
    has four — cannot leave one of them open.
    """
    store = SQLiteStore(tmp_path)
    writer = EventLogWriter(store)
    principal = _owner(store)
    _disable(store, capability)

    action_types = sorted(
        action for action, cap in CAPABILITY_GATE_MAP.items() if cap == capability
    )
    assert action_types, (
        f"{capability} has a real executor and no action type routes to it, so "
        "no gate decides whether it runs"
    )

    for action_type in action_types:
        probe = _ProbeExecutor(capability)
        registry = ExecutorRegistry()
        registry.register(capability, probe)
        authority = RuntimeAuthority(
            store, writer,
            policy_engine=_AllowEverythingPolicy(),  # type: ignore[arg-type]
            executor_registry=registry,
        )
        result = authority.route_action(
            GovernedAction(
                action_id=new_id("act_"),
                principal_id=principal.principal_id,
                action_type=action_type,
                tool_or_service_name=action_type,
                arguments={},
                domain_scope="",
                risk_level=RiskLevelValue.LOW,
            ),
            principal,
        )
        assert result.decision == "disabled_by_capability_gate", (
            f"{capability} ran through {action_type!r} with its gate off: "
            f"{result.decision} / {result.message}"
        )
        assert probe.called is False, (
            f"{capability}'s executor was entered through {action_type!r} "
            "although the owner had turned the capability off"
        )


@pytest.mark.parametrize("capability", CAPABILITIES)
def test_the_authority_record_agrees_with_the_traced_entry_path(
    capability: str,
) -> None:
    """The two tables describe the same capability, so they cannot disagree.

    An `own_gate` capability's authority requirement leads with its gate,
    because that *is* what governs it. One classified `governed_elsewhere` or
    `no_path` must not lead with a gate of its own, which is precisely the
    misdescription BUG-297 and GEP-04 each found once.

    The check is on the *opening* claim rather than on the whole sentence: two
    of these rows go on to say that every step inside them still answers to
    *that step's* own gate, which is the true and important half of what
    `governed_elsewhere` means.
    """
    row = CAPABILITY_AUTHORITY[capability]
    entry = CAPABILITY_ENTRY_PATHS.get(capability)
    assert entry is not None, f"{capability} has an authority record and no entry path"
    opening = row.authority.split(".", 1)[0].lower()
    leads_with_own_gate = opening.startswith("an owner-enabled gate") or opening.startswith(
        "its own gate"
    )
    if entry.reality == "own_gate":
        assert leads_with_own_gate, (
            f"{capability}'s gate is what decides whether it runs, and its "
            f"authority requirement does not lead with it: {row.authority!r}"
        )
    else:
        assert not leads_with_own_gate, (
            f"{capability} is {entry.reality} and its authority requirement "
            f"leads with a gate of its own: {row.authority!r}"
        )
