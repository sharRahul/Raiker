"""The one catalogue of Raiker's global agentic read capabilities (WEB-01).

Every model-backed work surface — Chat, Build, Design's planning layer, Tasks,
Schedule, agents — is supposed to see the same set of ways to read the world.
"Supposed to" was the problem: nothing said so in one place, so the answer to
*does Build have `web_search`?* was reconstructed from the projection list, the
capability router, the gate map and whichever view happened to render a menu.
Four derivations of one fact drift, and the drift is invisible until an owner
switches Project and watches a tool disappear.

So the contract lives here, once, and the surfaces read it rather than restate
it. Three rules it exists to make structural:

* **Projection is global; authority is local to the action.** Everything in
  :data:`GLOBAL_READ_CAPABILITIES` is visible on every agentic surface, and
  visibility is worth exactly nothing. A projected tool still passes the
  capability gate, the decision mode, the policy engine, the egress guard and —
  where policy says so — the approval queue before a byte leaves the machine.
  *Discovering, listing, projecting or searching for a tool never creates
  authority to execute it.*
* **A Project is work context, not a tool inventory.** Nothing here is keyed by
  project. Switching from Project A to Project B changes which files and which
  memories are in scope; it cannot change whether `web_fetch` exists.
* **Readiness and authority are different questions, answered separately.**
  `web_search · Needs provider` and `web_search · Blocked by policy` are not the
  same state and must never be collapsed into one greyed-out row. The first is a
  setup step; the second is a decision the owner made. :class:`ToolReadiness`
  carries both fields so a surface cannot accidentally report one as the other.

Administrative pages are deliberately absent from the surface list. Models,
Settings, Approvals and Observability are not model-backed work surfaces, and
giving them a composer to satisfy a parity table would be inventing an agentic
surface to make a test pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from raiker.contracts.ids import utc_now

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

#: The model-backed work surfaces that receive the global read catalogue.
#:
#: `subagent` is here and is *not* equal to the others: it receives the
#: delegable subset (:data:`DELEGABLE_READ_CAPABILITIES`), because a bounded
#: read-only delegation that could reach the open internet on its own would be
#: a wider grant than the parent turn made.
AGENTIC_SURFACES: tuple[str, ...] = (
    "chat",
    "build",
    "design",
    "tasks",
    "schedule",
    "agent",
    "subagent",
)

#: Pages that are administration rather than agentic work. Named so a parity
#: test can assert the *absence* — the rule is only enforceable if the exclusion
#: is written down rather than inferred from whichever views lack a composer.
ADMINISTRATIVE_SURFACES: tuple[str, ...] = (
    "models",
    "settings",
    "approvals",
    "permissions",
    "observability",
)

#: The external read capabilities every agentic surface can see.
EXTERNAL_READ_CAPABILITIES: tuple[str, ...] = (
    "web_search",
    "web_fetch",
    "web_extract",
    "weather_lookup",
)

#: The local read capabilities that travel with them. Listed here so the
#: catalogue answers "how does a turn read anything?" rather than only "how does
#: a turn reach the internet?" — the split between the two is what the surface
#: parity contract is actually about.
LOCAL_READ_CAPABILITIES: tuple[str, ...] = (
    "memory_search",
    "conversation_search",
    "read_file",
    "glob",
    "grep",
    "list_directory",
    "code_map_search",
)

#: The whole global read set, in one tuple.
GLOBAL_READ_CAPABILITIES: tuple[str, ...] = (
    *EXTERNAL_READ_CAPABILITIES,
    *LOCAL_READ_CAPABILITIES,
)

#: What a bounded read-only subagent may be delegated. Deliberately local-only:
#: the parent turn decides what leaves the machine, and a delegated step that
#: could fetch a URL of its own would move that decision somewhere nobody
#: approved. Kept in sync with the registry's own `delegable` flag by the
#: import-time check below, so the two cannot disagree.
DELEGABLE_READ_CAPABILITIES: tuple[str, ...] = tuple(
    name for name in LOCAL_READ_CAPABILITIES
)

#: Capability classes that are *not* part of the global read set, and why.
#: A browser can run page JavaScript, hold a session, click, type and be seen
#: acting by a third party. That is a different authority class from reading a
#: document, and `web_fetch` being on by default must never imply it.
INTERACTIVE_CAPABILITIES: tuple[str, ...] = ("browser_automation",)


#: Typed readiness states. A surface renders these; it never invents a state.
READY = "ready"
NEEDS_PROVIDER = "needs_provider"
BLOCKED = "blocked"
UNAVAILABLE = "unavailable"
TRANSIENT_FAILURE = "transient_failure"


@dataclass(frozen=True)
class ToolReadiness:
    """Whether a capability can answer now, said separately from whether it may.

    ``available`` is projection: the build has this tool and every agentic
    surface lists it. ``ready`` is operational: a provider is configured, a
    runtime is installed, the request would actually reach something.
    ``state`` says which of the two failed, so a surface can offer the setup
    path for `needs_provider` and the Permissions route for `blocked` instead of
    showing one grey row that means either.
    """

    tool: str
    available: bool
    ready: bool
    state: str
    reason_code: str | None = None
    reason_text: str | None = None
    provider: str | None = None
    remediation_route: str | None = None
    checked_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "tool": self.tool,
            "available": self.available,
            "ready": self.ready,
            "state": self.state,
            "checked_at": self.checked_at,
        }
        for key, value in (
            ("reason_code", self.reason_code),
            ("reason_text", self.reason_text),
            ("provider", self.provider),
            ("remediation_route", self.remediation_route),
        ):
            if value:
                payload[key] = value
        return payload


def read_capabilities_for(surface: str) -> tuple[str, ...]:
    """What *surface* may see.

    An unknown surface gets nothing rather than everything. A typo in a caller
    must not be the thing that widens a catalogue.
    """
    normalised = (surface or "").strip().lower()
    if normalised == "subagent":
        return DELEGABLE_READ_CAPABILITIES
    if normalised in AGENTIC_SURFACES:
        return GLOBAL_READ_CAPABILITIES
    return ()


def web_read_readiness(
    workspace_root: str | Path,
    store: SQLiteStore,
    principal_id: str | None,
) -> list[ToolReadiness]:
    """The current readiness of every external read capability, as typed rows.

    Derived from the same admission read and the same provider configuration the
    executor uses, so a surface cannot show `Ready` for a call the runtime is
    about to refuse — the failure mode the plan calls *fabricated readiness*.
    """
    from raiker.runtime.authority.admission import capability_admission
    from raiker.runtime.authority.decision_modes import DecisionMode
    from raiker.runtime.web_access import WebAccessService

    checked_at = utc_now()
    admission = capability_admission(store, principal_id, "web_fetch")
    rows: list[ToolReadiness] = []

    def gated(tool: str) -> ToolReadiness | None:
        if not admission.gate_enabled:
            return ToolReadiness(
                tool=tool,
                available=True,
                ready=False,
                state=BLOCKED,
                reason_code="web_gate_disabled",
                reason_text="Web access is turned off in Permissions.",
                remediation_route="capabilities",
                checked_at=checked_at,
            )
        if admission.decision_mode == DecisionMode.DENY:
            return ToolReadiness(
                tool=tool,
                available=True,
                ready=False,
                state=BLOCKED,
                reason_code="web_denied_by_decision_mode",
                reason_text="Web access is set to Deny in Permissions.",
                remediation_route="capabilities",
                checked_at=checked_at,
            )
        return None

    for tool in ("web_fetch", "web_extract"):
        rows.append(
            gated(tool)
            or ToolReadiness(
                tool=tool, available=True, ready=True, state=READY, checked_at=checked_at
            )
        )

    search_block = gated("web_search")
    if search_block is not None:
        rows.append(search_block)
    else:
        configured = WebAccessService.search_configured()
        rows.append(
            ToolReadiness(
                tool="web_search",
                available=True,
                ready=True,
                state=READY,
                provider="owner-configured endpoint" if configured else "built-in default",
                checked_at=checked_at,
            )
        )

    weather_block = gated("weather_lookup")
    rows.append(
        weather_block
        or ToolReadiness(
            tool="weather_lookup",
            available=True,
            ready=True,
            state=READY,
            provider="Open-Meteo",
            checked_at=checked_at,
        )
    )
    return rows


def _check_delegable_matches_registry() -> None:
    """The registry's `delegable` flag and this list have to agree.

    Two places naming the delegable set is one place too many; since the
    registry is the thing the runner actually enforces, this asserts against it
    at import so a divergence fails loudly here rather than quietly widening or
    narrowing what a subagent can be handed.
    """
    from raiker.models.tool_registry import DELEGABLE_TOOL_NAMES

    widened = set(DELEGABLE_READ_CAPABILITIES) - set(DELEGABLE_TOOL_NAMES)
    if widened:  # pragma: no cover - a definition error, not a runtime state
        raise ValueError(f"delegable_read_capabilities_not_delegable:{sorted(widened)}")


_check_delegable_matches_registry()
