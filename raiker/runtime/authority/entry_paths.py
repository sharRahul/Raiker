"""What actually reaches each capability, and what actually governs it.

**Why this exists (GEP-04).** Every capability with a real executor has a gate,
and the Capabilities page renders that gate as a switch. For fifteen of the
forty-five, flipping the switch changed nothing: either nothing in the product
constructed a governed action for the capability at all, or the work it names
happens through a *different* control that the gate never consults.

A switch in the "off" position beside a feature that is running is worse than no
switch. It is the one failure mode a governance product cannot have, because the
owner's belief about what they control is the product.

So this module records, for every capability with a real executor:

* **reality** — does this capability's own gate decide whether it runs
  (:data:`OWN_GATE`), does the work happen under a different named control
  (:data:`GOVERNED_ELSEWHERE`), or does nothing in the product reach the executor
  at all (:data:`NO_PATH`)?
* **entries** — how a governed action for it is constructed, when one is.
* **note** — for anything that is not ``OWN_GATE``, the sentence an owner needs:
  what really governs this, or why nothing runs.

``tests/test_governance_entry_paths.py`` asserts this table against
``REAL_EXECUTOR_CAPABILITIES``, ``TOOL_DEFINITIONS`` and
``EXECUTABLE_ON_APPROVAL``, so a new executor, a new tool or a new relay cannot
land without classifying itself. That test is invariant **I3** in
``docs/plans/GOVERNANCE_ENTRY_PATHS.md`` §5 — the invariant whose absence
produced the finding this module answers.

The API serves this to the web app, which renders it beside the gate rather than
letting the switch speak for itself.
"""
from __future__ import annotations

from dataclasses import dataclass

# ── How a governed action for a capability is constructed ────────────────────

#: A model names a tool and the broker routes it through chokepoint B.
ENTRY_MODEL_TOOL = "model_tool"
#: An approved action is relayed into execution by ``ApprovalExecutionBridge``.
ENTRY_APPROVAL_RELAY = "approval_relay"
#: A control-plane service method builds the action — human-only, owner-scoped.
ENTRY_CONTROL_PLANE = "control_plane"
#: The caller reads the gate itself through ``capability_admission`` rather than
#: routing an action. §4 of ``GOVERNANCE_ENTRY_PATHS.md``.
ENTRY_LOCAL_ADMISSION = "local_admission"

ENTRY_KINDS = frozenset({
    ENTRY_MODEL_TOOL,
    ENTRY_APPROVAL_RELAY,
    ENTRY_CONTROL_PLANE,
    ENTRY_LOCAL_ADMISSION,
})

# ── What the gate actually decides ──────────────────────────────────────────

#: The capability's own gate decides whether it runs. The switch means what it says.
OWN_GATE = "own_gate"
#: The work happens, and a different named control governs it. The switch is inert.
GOVERNED_ELSEWHERE = "governed_elsewhere"
#: Nothing in the product reaches this executor. The switch governs nothing yet.
NO_PATH = "no_path"

REALITIES = frozenset({OWN_GATE, GOVERNED_ELSEWHERE, NO_PATH})


@dataclass(frozen=True)
class CapabilityEntry:
    """One capability's traced entry paths and what its gate really decides."""

    capability: str
    reality: str
    entries: tuple[str, ...]
    note: str = ""

    def __post_init__(self) -> None:
        if self.reality not in REALITIES:
            raise ValueError(f"capability_entry_reality_invalid:{self.capability}")
        for entry in self.entries:
            if entry not in ENTRY_KINDS:
                raise ValueError(f"capability_entry_kind_invalid:{self.capability}:{entry}")
        if self.reality == OWN_GATE and not self.entries:
            raise ValueError(f"capability_entry_own_gate_needs_entry:{self.capability}")
        if self.reality != OWN_GATE and not self.note.strip():
            # The whole point of the non-OWN_GATE rows is the sentence. A row
            # without one would restate the problem it exists to name.
            raise ValueError(f"capability_entry_note_required:{self.capability}")
        if self.reality == NO_PATH and self.entries:
            raise ValueError(f"capability_entry_no_path_has_entry:{self.capability}")


def _own(capability: str, *entries: str) -> CapabilityEntry:
    return CapabilityEntry(capability, OWN_GATE, tuple(entries))


def _elsewhere(capability: str, note: str, *entries: str) -> CapabilityEntry:
    return CapabilityEntry(capability, GOVERNED_ELSEWHERE, tuple(entries), note)


def _no_path(capability: str, note: str) -> CapabilityEntry:
    return CapabilityEntry(capability, NO_PATH, (), note)


_ENTRIES: tuple[CapabilityEntry, ...] = (
    # ── Reached by a model tool, each entering chokepoint B by name ─────────
    _own("file_write_execution", ENTRY_MODEL_TOOL, ENTRY_APPROVAL_RELAY),
    _own("patch_apply_execution", ENTRY_MODEL_TOOL, ENTRY_APPROVAL_RELAY),
    _own("shell_execution", ENTRY_MODEL_TOOL, ENTRY_APPROVAL_RELAY),
    _own("git_write_execution", ENTRY_MODEL_TOOL, ENTRY_APPROVAL_RELAY),
    _own("git_push_execution", ENTRY_MODEL_TOOL, ENTRY_APPROVAL_RELAY),
    _own("connector_github_runtime", ENTRY_MODEL_TOOL, ENTRY_APPROVAL_RELAY,
         ENTRY_LOCAL_ADMISSION),
    _own("memory_write_execution", ENTRY_MODEL_TOOL, ENTRY_APPROVAL_RELAY),
    _own("memory_forget_execution", ENTRY_MODEL_TOOL, ENTRY_APPROVAL_RELAY),
    _own("task_management_runtime", ENTRY_MODEL_TOOL, ENTRY_APPROVAL_RELAY),
    _own("project_assignment_runtime", ENTRY_MODEL_TOOL, ENTRY_APPROVAL_RELAY),
    _own("remote_execution_cap", ENTRY_MODEL_TOOL, ENTRY_APPROVAL_RELAY),
    _own("cloud_execution_cap", ENTRY_MODEL_TOOL, ENTRY_APPROVAL_RELAY),
    _own("code_map_indexing", ENTRY_MODEL_TOOL, ENTRY_LOCAL_ADMISSION),
    _own("graph_indexing_runtime", ENTRY_MODEL_TOOL),
    _own("web_fetch", ENTRY_MODEL_TOOL, ENTRY_LOCAL_ADMISSION),
    # B7 — delegation answers to its own switch. The subagent's steps are still
    # re-brokered one at a time against the read-only delegable set, so the gate
    # decides *whether the owner allows delegation at all*, not what a subagent
    # may touch once delegated.
    _own("subagents", ENTRY_MODEL_TOOL, ENTRY_LOCAL_ADMISSION),
    # ── Reached only by an approval relay ──────────────────────────────────
    _own("checkpoint_restore_execution", ENTRY_APPROVAL_RELAY),
    # ── Reached by the control plane ───────────────────────────────────────
    _own("approval_execution_relay", ENTRY_CONTROL_PLANE),
    _own("audit_export", ENTRY_CONTROL_PLANE),
    _own("mcp_builder_runtime", ENTRY_CONTROL_PLANE),
    _own("mcp_connector_runtime", ENTRY_CONTROL_PLANE, ENTRY_LOCAL_ADMISSION),
    _own("external_channel_runtime", ENTRY_CONTROL_PLANE),
    # BUG-234 / GEP-04 — the install is a governed action now, raised by the
    # terminal's `/plugin-plan <manifest> --install` and routed like any other.
    _own("plugin_install", ENTRY_CONTROL_PLANE),
    # ── Reached by a caller that reads the gate itself (§4) ────────────────
    _own("advisor_model_runtime", ENTRY_LOCAL_ADMISSION),
    _own("connector_gmail_runtime", ENTRY_LOCAL_ADMISSION),
    _own("connector_gcal_runtime", ENTRY_LOCAL_ADMISSION),
    _own("connector_slack_runtime", ENTRY_LOCAL_ADMISSION),
    _own("vector_embedding_runtime", ENTRY_LOCAL_ADMISSION),
    _own("hosted_model_runtime", ENTRY_LOCAL_ADMISSION),
    _own("private_network_model_runtime", ENTRY_LOCAL_ADMISSION),
    _own("model_provider_runtime", ENTRY_LOCAL_ADMISSION),
    # ── The work happens, and something else governs it ────────────────────
    _elsewhere(
        "multi_agent_teams",
        "No surface offers a team yet. When one does, each member runs as a "
        "subagent under the `subagents` gate and every step is brokered "
        "individually, exactly as a single delegation is.",
    ),
    _elsewhere(
        "scheduled_routines",
        "A scheduled task runs as one whole governed turn through the Agent "
        "Gateway, so every action inside it answers to that action's own gate "
        "and decision mode. Pausing the host is what stops new scheduled work.",
    ),
    _elsewhere(
        "semantic_memory_runtime",
        "Memory recall answers to `vector_embedding_runtime`, which is the gate "
        "the retrieval path reads and the one the Memory page shows.",
    ),
    _elsewhere(
        "container_execution_cap",
        "Running a tool inside a container is chosen by enabling a container "
        "execution profile, and every tool call inside it is still brokered "
        "under that tool's own gate. Configuring the profile is the owner's "
        "act of authorisation; a second switch in front of it would be a wall "
        "in front of a choice they already made.",
    ),
    _elsewhere(
        "plugin_execution_cap",
        "A plugin's brokered tool call runs through the ordinary tool broker "
        "against the plugin's validated read-only set, so each call answers to "
        "the gate of the tool it names. No plugin code runs.",
    ),
    # ── Nothing reaches these ──────────────────────────────────────────────
    _no_path(
        "process_execution",
        "No tool names it and no approval relays it. It enters the same "
        "CommandService lifecycle `shell_execution` does, so it is an unused "
        "path rather than a weaker one.",
    ),
    _no_path(
        "plugin_runtime_cap",
        "Running an installed plugin's entrypoint has no owner surface. The "
        "executor exists and nothing invokes it.",
    ),
    _no_path(
        "plugin_sandboxed_runtime_cap",
        "The container-isolated plugin runtime has no owner surface. The "
        "executor exists and nothing invokes it.",
    ),
    _no_path(
        "plugin_sandbox_image_pull_cap",
        "Pulling a sandbox image has no owner surface, because nothing runs a "
        "sandboxed plugin yet.",
    ),
    _no_path(
        "plugin_revocation_cap",
        "Revocation is performed by the plugin registry directly when the owner "
        "revokes an install; no governed action is constructed for it.",
    ),
    _no_path(
        "channel_approval_relay",
        "An inbound channel message never becomes work, so no approval is ever "
        "relayed to a channel. Tracked as BUG-225.",
    ),
    _no_path(
        "reminder_runtime",
        "Reminders are stored locally and have no owner surface and no model "
        "tool. Nothing creates, lists or delivers one.",
    ),
    _no_path(
        "calendar_runtime",
        "The local calendar has no owner surface and no model tool. Nothing "
        "syncs, and nothing creates an event.",
    ),
    _no_path(
        "email_runtime",
        "Local email drafts have no owner surface and no model tool. Nothing "
        "drafts, and nothing has ever sent.",
    ),
)

CAPABILITY_ENTRY_PATHS: dict[str, CapabilityEntry] = {
    entry.capability: entry for entry in _ENTRIES
}
if len(CAPABILITY_ENTRY_PATHS) != len(_ENTRIES):  # pragma: no cover - construction guard
    raise ValueError("capability_entry_duplicate")


def entry_for(capability: str) -> CapabilityEntry | None:
    """The traced entry record for *capability*, or ``None`` if it has none."""
    return CAPABILITY_ENTRY_PATHS.get(capability)


def gate_is_effective(capability: str) -> bool:
    """True when flipping this capability's own gate changes what can run.

    A capability with no traced record is treated as effective: the invariant
    test refuses an untraced executor, so the only way to reach this branch is a
    capability with no executor at all, whose gate is already the thing that
    keeps it fail-closed.
    """
    entry = CAPABILITY_ENTRY_PATHS.get(capability)
    return entry is None or entry.reality == OWN_GATE


def governance_note(capability: str) -> str:
    """The sentence to show an owner beside an inert switch (``""`` if none)."""
    entry = CAPABILITY_ENTRY_PATHS.get(capability)
    return entry.note if entry is not None else ""
