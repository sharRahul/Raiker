"""What a brand-new account may do before its owner has decided anything.

**Why this exists (BUG-239).** Three rules decide what an empty gate table means
— :data:`~raiker.runtime.authority.admission.CAPABILITY_UNSET_RESOLUTION` names
them — and the owner's decision was to **keep all three** rather than collapse
them, because collapsing either way changes behaviour without looking at what
each capability is for: everything-``off`` re-opens the defect RAIKER-2021
closed, and everything-fallback loosens seven paths including three egress ones.

So the expansion happens somewhere else, and explicitly. A new account is seeded
with a **versioned baseline** of capabilities whose work is local, reversible and
already inside the authority the owner has granted by opening the product at all.
Nothing is inferred; a row is written, the row says it came from the baseline,
and Permissions shows it as a decision that exists rather than as an absence that
happens to resolve on.

The three properties that make this safe to do at all:

1. **It only ever runs at account creation.** An existing workspace is never
   re-seeded, so an owner who turned something off does not find it back on
   after an update. :func:`baseline_rows` is called from the one atomic path
   that creates an account and from the CLI bootstrap; nothing else calls it.
2. **Enabled means *available through governance*, not unattended.** Every row
   here keeps its decision mode — ``ask`` unless the owner changes it — so a
   baseline capability still proposes, still meets policy, and still meets an
   approval where its action requires one. Being on is not being allowed.
3. **Nothing external, destructive or authority-changing is in it.** The list is
   checked against
   :data:`~raiker.runtime.authority.capability_authority.CAPABILITY_AUTHORITY`
   in ``tests/test_account_capability_baseline.py``: a capability whose side
   effect leaves the machine, cannot be undone, or changes what Raiker may do
   next cannot be added to the baseline, whatever anyone writes here.

Unknown capabilities and failed reads are unaffected and stay fail-closed: this
writes rows, it does not change how a *missing* row is read.
"""
from __future__ import annotations

from dataclasses import dataclass

#: Bump when the set below changes. It is recorded in each row it writes, so a
#: workspace can be asked which baseline it was created under, and a later
#: migration can find exactly the rows a baseline put there — and only those.
ACCOUNT_BASELINE_VERSION = 1

#: The `requested_by` / `activated_by` written on every baseline row. A row an
#: owner can tell apart from one they wrote themselves is the difference between
#: a default and a decision they have forgotten making.
BASELINE_ACTOR = "system_account_baseline"


@dataclass(frozen=True)
class BaselineCapability:
    """One capability a new account starts with, and why it is defensible."""

    capability: str
    #: The sentence recorded on the gate row, so the reason travels with it.
    reason: str


#: Seeded for every account created from now on, in the order the owner's
#: decision prioritised them: the two repository reads first, then the two local
#: planning mutations, then the owner's own export.
ACCOUNT_CAPABILITY_BASELINE: tuple[BaselineCapability, ...] = (
    BaselineCapability(
        "language_intelligence",
        "Symbols and parse diagnostics over files the agent is already "
        "authorised to read. It writes nothing, not even a derived index.",
    ),
    BaselineCapability(
        "code_map_indexing",
        "A symbol index of the repository Build is pointed at, built on demand, "
        "respecting the repository's own exclusions, and removable.",
    ),
    BaselineCapability(
        "task_management_runtime",
        "Creating a task is a local, owner-scoped, reversible record. It carries "
        "no filesystem authority and its approval rules are unchanged.",
    ),
    BaselineCapability(
        "project_assignment_runtime",
        "Filing a session to a project is a local label under the owner's own "
        "account scope, and reversible by re-filing it.",
    ),
    BaselineCapability(
        "audit_export",
        "The owner's own record, redacted and written locally on request. It "
        "reaches no network and grants nothing; telemetry export is separate.",
    ),
)

BASELINE_CAPABILITIES: frozenset[str] = frozenset(
    row.capability for row in ACCOUNT_CAPABILITY_BASELINE
)

#: What the baseline is deliberately *not*. Kept beside it rather than in a
#: document, because the useful form of this list is the one a reviewer reads
#: when somebody proposes adding a sixth row.
#:
#: Shell and process execution, delegation and teams, durable memory writes,
#: scheduling, plugin and MCP execution, remote and cloud execution, external
#: channels, git pushes and telemetry export stay explicit opt-ins. Each either
#: leaves the machine, cannot be undone, or changes what Raiker may do next —
#: which are exactly the three side-effect classes the test refuses here.
BASELINE_EXCLUDED_SIDE_EFFECTS: frozenset[str] = frozenset(
    {"external", "destructive", "critical"}
)


def baseline_rows(now: str) -> tuple[dict[str, str], ...]:
    """The capability-gate rows to write for a newly created account.

    Shaped for ``upsert_principal_capability_gate_state``. ``enabled_runtime``
    rather than ``enabled``: the baseline's whole point is that these are usable
    without a second step, and the decision mode still decides what happens when
    one is *proposed*.
    """
    return tuple(
        {
            "capability": row.capability,
            "state": "enabled_runtime",
            "requested_by": BASELINE_ACTOR,
            "requested_at": now,
            "activated_by": BASELINE_ACTOR,
            "activated_at": now,
            "reason": f"Account baseline v{ACCOUNT_BASELINE_VERSION}. {row.reason}",
            "readiness_snapshot_json": "",
            "created_at": now,
            "updated_at": now,
        }
        for row in ACCOUNT_CAPABILITY_BASELINE
    )


def is_baseline_row(requested_by: str | None) -> bool:
    """True when a gate row was written by the baseline rather than by an owner."""
    return (requested_by or "") == BASELINE_ACTOR
