"""Every registered tool answers to a reviewed authority (beta plan AG-2).

A tool reaches the runtime only through the broker, and the broker asks the
authority router for the tool's capability gate. A tool whose definition names
no capability has no switch an owner can turn off, so it must be a reviewed
exception with a reason. This test fails when:

* a tool names a capability that has no gate, so the router would answer
  ``unknown_capability_gate`` instead of the owner's switch;
* a tool names no capability and is not listed in :data:`UNGATED` with the
  authority it answers to instead — so a new ungated tool cannot land unnoticed;
* a listed tool now has a capability, or no longer exists — so the list stays
  current;
* a tool in the *project read* category is anything but a low-risk read.
"""

from __future__ import annotations

from raiker.models.tool_registry import TOOL_DEFINITIONS
from raiker.phase_gates import default_capability_gates
from raiker.runtime.authority.router import CAPABILITY_GATE_MAP

#: Reads inside the session's task tree or Raiker's own records: no effect, no
#: network, the path authority bounds what they can see.
PROJECT_READ = "project read"
#: Governed by the connected account's own grant: the connector invoker checks
#: the account, its scopes and its manifest operation before any request.
CONNECTOR_GRANT = "connector grant"
#: Governed by the session's command grant and the native sandbox; refused on a
#: host whose sandbox probe is not enforced.
COMMAND_GRANT = "command grant"
#: Checks its own gate inside the tool (fail closed), not through the map.
OWN_GATE = "own gate"
#: Changes only the turn itself: asks the owner, records a plan, suggests.
TURN_ONLY = "turn only"

UNGATED: dict[str, str] = {
    "read_file": PROJECT_READ,
    "list_directory": PROJECT_READ,
    "stat_path": PROJECT_READ,
    "glob": PROJECT_READ,
    "grep": PROJECT_READ,
    "diff_files": PROJECT_READ,
    "git_status": PROJECT_READ,
    "git_diff": PROJECT_READ,
    "git_log": PROJECT_READ,
    "memory_get": PROJECT_READ,
    "memory_list": PROJECT_READ,
    "memory_search": PROJECT_READ,
    "vector_get": PROJECT_READ,
    "conversation_search": PROJECT_READ,
    "help_read": PROJECT_READ,
    "skill_search": PROJECT_READ,
    "skill_load": PROJECT_READ,
    "tool_search": PROJECT_READ,
    "suggest_connection": PROJECT_READ,
    "connector_read": CONNECTOR_GRANT,
    "connector_write": CONNECTOR_GRANT,
    "github_read": CONNECTOR_GRANT,
    "gmail_read": CONNECTOR_GRANT,
    "gcal_read": CONNECTOR_GRANT,
    "slack_read": CONNECTOR_GRANT,
    "run_command": COMMAND_GRANT,
    "background_run": COMMAND_GRANT,
    "consult_advisor": OWN_GATE,
    "ask_owner_question": TURN_ONLY,
    "update_plan": TURN_ONLY,
}


def test_every_named_capability_has_a_gate() -> None:
    gates = default_capability_gates()
    missing = sorted(
        (item.name, item.capability)
        for item in TOOL_DEFINITIONS
        if item.capability is not None and item.capability not in gates
    )
    assert missing == [], f"tools naming a capability with no gate: {missing}"
    unmapped = sorted(
        (tool, capability) for tool, capability in CAPABILITY_GATE_MAP.items() if capability not in gates
    )
    assert unmapped == [], f"router entries naming no gate: {unmapped}"


def test_every_gated_tool_is_found_by_the_router() -> None:
    lost = sorted(
        item.name
        for item in TOOL_DEFINITIONS
        if item.capability is not None and CAPABILITY_GATE_MAP.get(item.name) != item.capability
    )
    assert lost == [], f"the router would not find these tools' gates: {lost}"


def test_no_tool_is_ungated_without_a_reviewed_reason() -> None:
    ungated = {item.name for item in TOOL_DEFINITIONS if item.capability is None}
    unreviewed = sorted(ungated - set(UNGATED))
    assert unreviewed == [], (
        f"tools with no capability gate and no reviewed authority: {unreviewed}. "
        "Give the tool a capability, or list it in UNGATED with the authority it answers to."
    )
    stale = sorted(set(UNGATED) - ungated)
    assert stale == [], f"UNGATED lists tools that are now gated or gone: {stale}"


def test_a_project_read_is_a_low_risk_read() -> None:
    by_name = {item.name: item for item in TOOL_DEFINITIONS}
    wrong = sorted(
        name
        for name, category in UNGATED.items()
        if category == PROJECT_READ
        and (by_name[name].risk != "low" or not by_name[name].read_shaped)
    )
    assert wrong == [], f"ungated 'project read' tools that are not low-risk reads: {wrong}"
