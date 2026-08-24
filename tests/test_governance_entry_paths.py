"""The governance entry paths cannot change without the enumeration changing.

`docs/plans/GOVERNANCE_ENTRY_PATHS.md` enumerates every way an action reaches an
executor. A document like that is worth exactly as much as the test that stops it
rotting, because its failure mode is silent: a new path appears beside the
governed ones, nothing breaks, and the enumeration quietly stops being true.

Each invariant here would have caught a defect this repository has actually had.
I3 in particular is the one whose absence let two egress implementations coexist
for months, one of them with none of the address guard.
"""

from __future__ import annotations

import re
from pathlib import Path

ENTRY_PATHS_DOC = Path("docs/plans/GOVERNANCE_ENTRY_PATHS.md")

#: Modules permitted to call `RuntimeAuthority.route_action`. Adding one is an
#: architectural change: it is a new way for an action to reach an executor.
ROUTE_ACTION_CALLERS = {
    "raiker/approvals/execution.py",
    "raiker/control/service.py",
    "raiker/runtime/authority/router.py",
    "raiker/runtime/executors/tier1_approval.py",
    "raiker/tools/broker.py",
}

#: Modules permitted to construct an `AgentGateway`. This is what makes "every
#: interface enters through the Agent Gateway" checkable rather than asserted.
GATEWAY_CONSTRUCTORS = {
    "raiker/api/routes_approvals.py",
    "raiker/api/routes_prompts.py",
    "raiker/cli/commands.py",
    "raiker/tasks/scheduler.py",
}

#: Modules that read a capability gate themselves instead of routing through
#: `RuntimeAuthority`. Each is listed in §4 of the document with the checks it
#: therefore does not get. A tenth appearing silently is the thing to prevent.
#:
#: They no longer each carry a copy of the lookup — GEP-01 replaced eight copies
#: with `capability_admission` — so the shape this test watches for changed from
#: "a local `_ENABLED_GATE_STATES`" to "a caller of the shared helper". That is
#: strictly better: the old marker could be dropped while the drift stayed, and
#: this one names the actual seam.
LOCAL_GATE_CHECK_MODULES = {
    "raiker/graph/codemap_service.py",
    "raiker/memory/candidates.py",
    "raiker/models/policy_state.py",
    "raiker/runtime/advisor.py",
    "raiker/runtime/connectors.py",
    "raiker/runtime/retrieval.py",
    "raiker/runtime/web_access.py",
    "raiker/tools/mcp_tools.py",
    # GEP-04 — delegation answers to the `subagents` gate now. It is read here
    # rather than at chokepoint B because `spawn_subagent` is read-shaped, the
    # same reason `code_map_search` reads its own gate.
    "raiker/tools/subagent_tools.py",
    # Reads the gate to *describe* it to the model rather than to enforce it.
    # It is in this list for the same reason the others are: it used to resolve
    # an empty gate table differently from the path it was describing, and told
    # the model `web_fetch: disabled` on an install where web_fetch worked.
    "raiker/context/gatherer.py",
}

#: Capabilities with a real executor that no product path constructs. Each is
#: listed in §3.5 with its status. They are recorded rather than removed because
#: an unreachable registered executor is the shape a future hole takes.
KNOWN_UNREACHABLE_CAPABILITIES = {
    "process_execution",
}


def _sources() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for path in sorted(Path("raiker").rglob("*.py")):
        out.append((path.as_posix(), path.read_text(encoding="utf-8", errors="ignore")))
    return out


def test_i1_route_action_callers_are_the_enumerated_ones() -> None:
    """I1 — a seventh entry into chokepoint B is an architectural change."""
    found = {
        path
        for path, text in _sources()
        if re.search(r"(?<!def )route_action\(", text)
    }
    assert found == ROUTE_ACTION_CALLERS, (
        "route_action call sites changed. Update ROUTE_ACTION_CALLERS *and* §2 of "
        f"{ENTRY_PATHS_DOC}: added={sorted(found - ROUTE_ACTION_CALLERS)}, "
        f"removed={sorted(ROUTE_ACTION_CALLERS - found)}"
    )


def test_i2_agent_gateway_is_constructed_only_by_enumerated_surfaces() -> None:
    """I2 — no surface reaches the orchestrator without the gateway."""
    found = {
        path
        for path, text in _sources()
        if "AgentGateway(" in text and path != "raiker/gateway/agent_gateway.py"
    }
    assert found == GATEWAY_CONSTRUCTORS, (
        "AgentGateway construction sites changed. Update GATEWAY_CONSTRUCTORS *and* "
        f"§3.1 of {ENTRY_PATHS_DOC}: "
        f"added={sorted(found - GATEWAY_CONSTRUCTORS)}, "
        f"removed={sorted(GATEWAY_CONSTRUCTORS - found)}"
    )


def test_i3_every_real_executor_capability_is_named_in_the_enumeration() -> None:
    """I3 — the invariant whose absence let two egress implementations coexist.

    Deliberately narrow, because it has to be exact to be worth anything.
    Reachability cannot be computed reliably by inspection — a capability name
    appearing in `control/service.py` may be a list entry rather than a
    constructed action, and a first attempt at this test classified four
    capabilities wrongly on exactly that mistake. So this asserts the one thing
    that *is* exact: **every capability with a real executor is named in the
    entry-path enumeration**, with its path stated there.

    That is enough to close the gap this test exists for. A new registered
    executor cannot appear without someone writing down how it is reached, which
    is the step nobody took for `network_execution` before it was deleted (BUG-232).
    """
    from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES

    doc = ENTRY_PATHS_DOC.read_text(encoding="utf-8")
    missing = sorted(cap for cap in REAL_EXECUTOR_CAPABILITIES if cap not in doc)
    assert missing == [], (
        "A capability has a real executor and is not named in the entry-path "
        f"enumeration. Add it to §3.6 of {ENTRY_PATHS_DOC} with the path that "
        f"reaches it, or to §3.5 if nothing does: {missing}"
    )


def test_i3b_the_tool_reachable_set_is_exactly_sixteen() -> None:
    """The one reachability fact that *is* exactly computable.

    Sixteen capabilities are reached by a model tool through
    `CAPABILITY_GATE_MAP`. Everything else is reached by an approval, by the
    control plane, by a tool that checks its own gate (§4), or by nothing at all
    (§3.5). A change here moves a capability between those categories and the
    document has to move with it.
    """
    from raiker.models.tool_registry import TOOL_DEFINITIONS
    from raiker.runtime.authority.router import CAPABILITY_GATE_MAP
    from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES

    by_tool = {
        CAPABILITY_GATE_MAP.get(d.name, d.name) for d in TOOL_DEFINITIONS
    } & REAL_EXECUTOR_CAPABILITIES
    assert len(by_tool) == 16, (
        "The number of capabilities a model tool can name changed "
        f"({len(by_tool)}, was 16). Update §3.6 of {ENTRY_PATHS_DOC}: "
        f"{sorted(by_tool)}"
    )


def test_i4_local_gate_checks_are_the_enumerated_ones() -> None:
    """I4 — a further module reading the gate itself cannot appear silently."""
    found = {
        path
        for path, text in _sources()
        if path != "raiker/runtime/authority/admission.py"
        and re.search(r"\b(capability_admission|capability_gate_record|gate_enabled)\b", text)
        and "raiker.runtime.authority.admission import" in text
    }
    assert found == LOCAL_GATE_CHECK_MODULES, (
        "The set of modules reading a capability gate directly changed. Each one "
        "misses check_self_approval, check_self_grant, check_principal_active, "
        "check_domain_scope, check_runtime_gate_enable, classify_critical and the "
        f"posture check. Update LOCAL_GATE_CHECK_MODULES *and* §4 of {ENTRY_PATHS_DOC}: "
        f"added={sorted(found - LOCAL_GATE_CHECK_MODULES)}, "
        f"removed={sorted(LOCAL_GATE_CHECK_MODULES - found)}"
    )


def test_i4b_no_module_carries_its_own_copy_of_the_gate_lookup() -> None:
    """GEP-01 — one copy of the enabled-state set, and it lives in `admission`.

    The eight copies were each correct. What made them worth removing is that
    the same empty gate table meant three different things across them, and two
    of the three were only discoverable by reading all eight side by side.
    """
    offenders = sorted(
        path
        for path, text in _sources()
        if path != "raiker/runtime/authority/admission.py"
        and re.search(r"^_?ENABLED_GATE_STATES\s*[:=]", text, re.M)
    )
    assert offenders == [], (
        "A module declared its own set of enabled gate states. Call "
        "`raiker.runtime.authority.admission.capability_admission` instead — it "
        f"is the one copy, and it names which unset-resolution it uses: {offenders}"
    )


def test_i5_a_hook_can_never_grant() -> None:
    """I5 — nothing a hook returns may allow what the runtime refused.

    `allow` stays in the decision vocabulary because a config file written for
    the reference format should parse here; what must never happen is `combine`
    turning one into an outcome that widens the action.
    """
    from raiker.hooks.contracts import HOOK_DECISIONS, HOOK_SCOPES
    from raiker.hooks.decision import HandlerDecision, combine

    assert "allow" in HOOK_DECISIONS, "the vocabulary should still accept `allow`"
    for scope in HOOK_SCOPES:
        for decision in sorted(HOOK_DECISIONS):
            for has_authority in (True, False):
                result = combine(
                    [HandlerDecision(scope=scope, decision=decision, has_authority=has_authority)]
                )
                assert result in {"deny", "ask", "no_decision"}, (
                    f"combine() returned {result!r} for scope={scope!r} "
                    f"decision={decision!r} has_authority={has_authority}. A hook "
                    "must only ever make an action stricter; see "
                    "REFERENCE_PLATFORM_COMPATIBILITY.md §4.3."
                )

    # An authoritative `allow` alongside an authoritative `deny` must not rescue
    # the action — the deny is what the runtime honours.
    mixed = combine(
        [
            HandlerDecision(scope="user", decision="allow", has_authority=True),
            HandlerDecision(scope="project", decision="deny", has_authority=True),
        ]
    )
    assert mixed == "deny", "an `allow` must never override a `deny`"


def test_the_entry_path_document_names_both_chokepoints() -> None:
    """The document is the artefact; these are the two names it cannot lose."""
    doc = ENTRY_PATHS_DOC.read_text(encoding="utf-8")
    for required in ("PolicyEngine.review", "RuntimeAuthority.route_action"):
        assert required in doc, f"{ENTRY_PATHS_DOC} must name {required}"


# ── GEP-04: what each gate actually decides ─────────────────────────────────
# The finding that motivated these: fifteen capabilities had a gate, a switch on
# the Capabilities page, and no traced path. Some had none because nothing
# reaches the executor; some because the work happens under a *different*
# control. Either way the owner was shown a switch that governed nothing, which
# is the one failure mode a governance product cannot have.


def test_every_real_executor_capability_is_classified() -> None:
    """A new registered executor must say how it is reached before it ships."""
    from raiker.runtime.authority.entry_paths import CAPABILITY_ENTRY_PATHS
    from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES

    missing = sorted(REAL_EXECUTOR_CAPABILITIES - set(CAPABILITY_ENTRY_PATHS))
    extra = sorted(set(CAPABILITY_ENTRY_PATHS) - REAL_EXECUTOR_CAPABILITIES)
    assert missing == [], (
        "A capability has a real executor and no entry-path classification. Add "
        "it to raiker/runtime/authority/entry_paths.py saying what reaches it, "
        f"or that nothing does: {missing}"
    )
    assert extra == [], (
        "An entry-path row names a capability with no real executor. Remove it "
        f"or register the executor: {extra}"
    )


def test_model_tool_entries_match_the_tool_registry() -> None:
    """`ENTRY_MODEL_TOOL` is a claim the tool registry can confirm or refute."""
    from raiker.models.tool_registry import TOOL_DEFINITIONS
    from raiker.runtime.authority.entry_paths import (
        CAPABILITY_ENTRY_PATHS,
        ENTRY_MODEL_TOOL,
    )
    from raiker.runtime.authority.router import CAPABILITY_GATE_MAP
    from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES

    by_tool = {
        CAPABILITY_GATE_MAP.get(d.name, d.name) for d in TOOL_DEFINITIONS
    } & REAL_EXECUTOR_CAPABILITIES
    claimed = {
        cap
        for cap, entry in CAPABILITY_ENTRY_PATHS.items()
        if ENTRY_MODEL_TOOL in entry.entries
    }
    assert claimed == by_tool, (
        "The set of capabilities a model tool names disagrees with the "
        f"entry-path table: claimed_only={sorted(claimed - by_tool)}, "
        f"registry_only={sorted(by_tool - claimed)}"
    )


def test_approval_relay_entries_match_the_relayable_set() -> None:
    """`ENTRY_APPROVAL_RELAY` is a claim `EXECUTABLE_ON_APPROVAL` can confirm."""
    from raiker.approvals.execution import EXECUTABLE_ON_APPROVAL
    from raiker.runtime.authority.entry_paths import (
        CAPABILITY_ENTRY_PATHS,
        ENTRY_APPROVAL_RELAY,
    )

    claimed = {
        cap
        for cap, entry in CAPABILITY_ENTRY_PATHS.items()
        if ENTRY_APPROVAL_RELAY in entry.entries
    }
    assert claimed == set(EXECUTABLE_ON_APPROVAL), (
        "The set of capabilities an approval relays disagrees with the "
        f"entry-path table: claimed_only={sorted(claimed - EXECUTABLE_ON_APPROVAL)}, "
        f"relay_only={sorted(EXECUTABLE_ON_APPROVAL - claimed)}"
    )


def test_an_inert_gate_says_what_really_governs_it() -> None:
    """The sentence is the deliverable, so it cannot be empty or a restatement."""
    from raiker.runtime.authority.entry_paths import (
        CAPABILITY_ENTRY_PATHS,
        OWN_GATE,
    )

    for cap, entry in sorted(CAPABILITY_ENTRY_PATHS.items()):
        if entry.reality == OWN_GATE:
            continue
        assert len(entry.note.split()) >= 12, (
            f"{cap} is not governed by its own gate and its note is too short to "
            f"tell an owner what is: {entry.note!r}"
        )


def test_the_known_unreachable_set_is_derived_not_duplicated() -> None:
    """§3.5's list and the table cannot disagree, because one derives the other."""
    from raiker.runtime.authority.entry_paths import CAPABILITY_ENTRY_PATHS, NO_PATH

    no_path = {
        cap for cap, entry in CAPABILITY_ENTRY_PATHS.items() if entry.reality == NO_PATH
    }
    assert no_path >= KNOWN_UNREACHABLE_CAPABILITIES, (
        "A capability recorded in §3.5 as unreachable is classified as reached: "
        f"{sorted(KNOWN_UNREACHABLE_CAPABILITIES - no_path)}"
    )
