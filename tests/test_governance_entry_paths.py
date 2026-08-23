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
#: therefore does not get. A ninth appearing silently is the thing to prevent.
LOCAL_GATE_CHECK_MODULES = {
    "raiker/graph/codemap_service.py",
    "raiker/memory/candidates.py",
    "raiker/models/policy_state.py",
    "raiker/runtime/advisor.py",
    "raiker/runtime/connectors.py",
    "raiker/runtime/retrieval.py",
    "raiker/runtime/web_access.py",
    "raiker/tools/mcp_tools.py",
}

#: Capabilities with a real executor that no product path constructs. Each is
#: listed in §3.5 with its status. They are recorded rather than removed because
#: an unreachable registered executor is the shape a future hole takes.
KNOWN_UNREACHABLE_CAPABILITIES = {
    "network_execution",
    "process_execution",
    "checkpoint_restore_execution",
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
    is the step nobody took for `network_execution`.
    """
    from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES

    doc = ENTRY_PATHS_DOC.read_text(encoding="utf-8")
    missing = sorted(cap for cap in REAL_EXECUTOR_CAPABILITIES if cap not in doc)
    assert missing == [], (
        "A capability has a real executor and is not named in the entry-path "
        f"enumeration. Add it to §3.6 of {ENTRY_PATHS_DOC} with the path that "
        f"reaches it, or to §3.5 if nothing does: {missing}"
    )


def test_i3b_the_tool_reachable_set_is_exactly_fifteen() -> None:
    """The one reachability fact that *is* exactly computable.

    Fifteen capabilities are reached by a model tool through
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
    assert len(by_tool) == 15, (
        "The number of capabilities a model tool can name changed "
        f"({len(by_tool)}, was 15). Update §3.6 of {ENTRY_PATHS_DOC}: "
        f"{sorted(by_tool)}"
    )


def test_i4_local_gate_checks_are_the_enumerated_eight() -> None:
    """I4 — a ninth module re-implementing the gate check cannot appear silently."""
    found = {
        path
        for path, text in _sources()
        if re.search(r"^_ENABLED_GATE_STATES\s*[:=]", text, re.M)
    }
    assert found == LOCAL_GATE_CHECK_MODULES, (
        "The set of modules reading a capability gate directly changed. Each one "
        "misses check_self_approval, check_self_grant, check_principal_active, "
        "check_domain_scope, check_runtime_gate_enable, classify_critical and the "
        f"posture check. Update LOCAL_GATE_CHECK_MODULES *and* §4 of {ENTRY_PATHS_DOC}: "
        f"added={sorted(found - LOCAL_GATE_CHECK_MODULES)}, "
        f"removed={sorted(LOCAL_GATE_CHECK_MODULES - found)}"
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
