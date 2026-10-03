"""One authoritative answer to "which model is this, and which one will run".

Raiker already persisted every part of this correctly, and that was
the problem: *global selection*, *surface default*, *readiness*, *fallback
sequence* and *local runtime state* were five stores read through five paths,
and each surface assembled its own answer from whichever subset it happened to
need. The Models page, the composer picker, Chat, Build, Design and task
creation therefore agreed only by coincidence, and when they disagreed there was
no way to say which of them was wrong — each was reporting a true fact about a
different question.

The five questions, kept separate here because conflating any two of them is
what produced the confusion the review describes:

``selected``
    The owner's choice for this scope. It is a *preference*, it persists, and it
    may name a model that cannot currently run. This is the one the interface
    must keep showing. It is **empty when the owner has chosen nothing** — the
    shipped default is not a choice they made, and reporting it as one is
    BUG-286.
``effective``
    What a turn started right now would actually use, after the fallback
    sequence has been walked. Usually the same pair; when it is not, that is a
    fact the owner is entitled to read rather than a silent substitution.
``ready``
    Whether the readiness gate says the *effective* pair can serve a turn.
``running``
    Whether a managed local process is serving. Only meaningful for a profile
    that has a local slot; ``None`` for anything hosted, because "not running"
    is not a true thing to say about somebody else's endpoint.
``problem``
    Present only when the selection cannot serve. It carries the reason and the
    remediation from readiness, so the interface never has to invent either.

The invariant this file exists to enforce:

    A selected model must never disappear because it is not currently ready.

Nothing here writes. Selection is written through
``DashboardControl.set_model_selection`` and the surface-default routes, which
already validate against the provider factory; a read model that could also
write would be a second way to set a model, which is the shape of the original
problem.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal, cast

from raiker.contracts.views import View
from raiker.models.readiness import ModelReadiness, ModelReadinessService
from raiker.models.wire import (
    DecisionProblem,
    ModelDecisionView,
    NextAction,
    ReadinessStep,
    ReadinessStepState,
)

SelectionSource = Literal["surface_default", "global_default", "native_default"]
EffectiveReason = Literal["selected", "fallback", "no_ready_candidate"]

#: The work surfaces that may hold their own default model.
#:
#: Chat, Build and Design are the three Work modes: each is a way of giving
#: Raiker something to do, and each wants a different kind of model — a
#: conversational one, a coding one, one that draws. Tasks and Schedule are not
#: modes; they *capture* the model onto the task they create, so a run that
#: fires next Tuesday uses the model that was chosen when it was scheduled
#: rather than whatever the owner has selected by then.
#:
#: ``design`` was added later. Its absence was not a missing feature so much as a
#: contradiction: the product model is Chat | Build | Design, and two of the
#: three had explicit surface state while the third silently borrowed the global
#: default. An owner who set Chat to a small local model would have had their
#: image prompts follow it.
SURFACES: tuple[str, ...] = ("chat", "build", "design", "tasks", "schedule")

#: Where a selection came from, most specific first. The order is the resolution
#: order, and the interface uses it to explain *why* this model is selected.
SELECTION_SOURCES: tuple[str, ...] = ("surface_default", "global_default", "native_default")


@dataclass(frozen=True)
class ModelChoice(View):
    """A profile and a concrete model, with why it is the one being named."""

    profile_id: str
    model: str
    #: For ``selected``: one of ``SELECTION_SOURCES``.
    #: For ``effective``: ``selected``, ``fallback`` or ``no_ready_candidate``.
    source: str


@dataclass(frozen=True)
class ModelDecision:
    surface: str
    project_id: str | None
    selected: ModelChoice
    effective: ModelChoice
    ready: bool
    running: bool | None
    problem: dict[str, str] | None
    revision: str
    steps: tuple[ReadinessStep, ...] = ()
    next_action: NextAction | None = None

    def to_dict(self) -> ModelDecisionView:
        return {
            "scope": {"surface": self.surface, "project_id": self.project_id},
            "selected": {
                "profile_id": self.selected.profile_id,
                "model": self.selected.model,
                "source": cast(SelectionSource, self.selected.source),
            },
            # `effective.source` answers "why this one", which for the effective
            # pair is the reason it displaced the selection — so the field is
            # spelled `reason` on the wire, matching how the interface reads it.
            "effective": {
                "profile_id": self.effective.profile_id,
                "model": self.effective.model,
                "reason": cast(EffectiveReason, self.effective.source),
            },
            "ready": self.ready,
            "running": self.running,
            "problem": cast("DecisionProblem | None", self.problem),
            "revision": self.revision,
            "steps": list(self.steps),
            "next_action": self.next_action,
        }


class ModelDecisionService:
    """Assembles the decision for one owner and one surface.

    Every read is best-effort in the same direction: a store that cannot be
    read degrades to a less specific source rather than to an error, because a
    composer that will not render is worse for the owner than a composer
    showing the global default. The one thing it never does is *invent*
    readiness — an unreadable configuration reports itself as a problem.
    """

    def __init__(
        self,
        store: Any,
        readiness: ModelReadinessService | None = None,
        *,
        runtimes: tuple[Any, ...] = (),
    ) -> None:
        self.store = store
        # The host's own managed pools. A pool built here would hold no
        # processes and report every local slot stopped, which is what `_running`
        # did while it constructed one per call.
        self.runtimes = runtimes
        if readiness is None:
            # The catalogue probe is the same one the readiness routes build, so
            # a caller that does not already hold a service gets the identical
            # verdicts rather than a second, quieter opinion.
            from raiker.models.readiness import ProviderCatalogueProbe

            readiness = ModelReadinessService(store, probe=ProviderCatalogueProbe(store))
        self.readiness = readiness

    # ── selection ────────────────────────────────────────────────────────────

    def _surface_default(self, owner_principal_id: str, surface: str) -> tuple[str, str] | None:
        """The pair this surface remembers, or None when it has no opinion."""
        if surface not in SURFACES:
            return None
        try:
            rows = self.store.list_surface_model_defaults(owner_principal_id)
        except Exception:  # noqa: BLE001 — an unreadable preference is no preference
            return None
        for stored_surface, profile_id, model in rows or []:
            if stored_surface == surface and profile_id and model:
                return str(profile_id), str(model)
        return None

    def selected_for(self, owner_principal_id: str, surface: str) -> ModelChoice:
        """The owner's choice for this surface, most specific source first.

        A surface default that names a profile the registry no longer has is
        skipped rather than raised: a profile can disappear when a provider is
        removed, and the honest answer is the next source down, not a broken
        page.
        """
        stored = self._surface_default(owner_principal_id, surface)
        if stored is not None:
            try:
                profile_id, model = self.readiness.resolve_request_target(
                    owner_principal_id, stored[0], stored[1]
                )
                if model and "<" not in model:
                    return ModelChoice(profile_id, model, "surface_default")
            except Exception:  # noqa: BLE001 — fall through to the global choice
                pass

        # BUG-286 — the owner has stored nothing, so there is nothing to report.
        #
        # `resolve_request_target` ends at the *shipped* native default when no
        # selection exists, and a selection nobody made is not a selection —
        # reporting it as `selected` would make every consumer tell two kinds of
        # `selected` apart. The empty pair is the
        # honest answer, `decide` turns it into the `no_model_selected` problem
        # below, and the interface stops having to tell two kinds of `selected`
        # apart. What a turn sent *without* a model would run is a different
        # question, asked of the gateway's own router and not of this read.
        if not self._has_global_selection(owner_principal_id):
            return ModelChoice("", "", "native_default")

        try:
            profile_id, model = self.readiness.resolve_request_target(
                owner_principal_id, None, None
            )
        except Exception:  # noqa: BLE001
            return ModelChoice("", "", "native_default")
        return ModelChoice(profile_id, model, "global_default")

    def _has_global_selection(self, owner_principal_id: str) -> bool:
        from raiker.models.session_state import TERMINAL_MODEL_SESSION_ID

        try:
            if self.store.get_account(owner_principal_id) is not None:
                return self.store.load_principal_model_state(owner_principal_id) is not None
            return self.store.load_model_session_state(TERMINAL_MODEL_SESSION_ID) is not None
        except Exception:  # noqa: BLE001
            return False

    # ── effective ────────────────────────────────────────────────────────────

    def decide(
        self,
        owner_principal_id: str,
        surface: str,
        project_id: str | None = None,
    ) -> ModelDecision:
        selected = self.selected_for(owner_principal_id, surface)

        chain: list[ModelReadiness] = []
        if selected.profile_id:
            try:
                chain = self.readiness.resolve_chain(
                    owner_principal_id, selected.profile_id, selected.model
                )
            except Exception:  # noqa: BLE001 — an unresolvable chain is reported below
                chain = []

        first_ready = next((entry for entry in chain if entry.ready), None)
        head = chain[0] if chain else None

        if first_ready is not None and head is not None and first_ready is head:
            effective = ModelChoice(selected.profile_id, selected.model, "selected")
            problem = None
        elif first_ready is not None:
            # The runtime would really use this one. Saying so is the whole
            # point: the alternative is a picker that quietly renames itself and
            # an owner who cannot tell a persistence bug from a fallback.
            effective = ModelChoice(
                first_ready.key.profile_id, first_ready.key.model, "fallback"
            )
            problem = _problem(head)
        else:
            # Nothing in the chain can serve. The selection stays exactly where
            # it is — it is still what the owner chose — and the reason it
            # cannot run travels beside it.
            effective = ModelChoice(
                selected.profile_id, selected.model, "no_ready_candidate"
            )
            problem = _problem(head)

        steps, next_action = readiness_steps(
            selected=selected,
            head=head,
            has_connection=self._has_connection(owner_principal_id, selected.profile_id),
            catalogue_lists_model=self._catalogue_lists(owner_principal_id, selected),
        )
        return ModelDecision(
            surface=surface,
            project_id=project_id or None,
            selected=selected,
            effective=effective,
            ready=first_ready is not None,
            running=self._running(effective.profile_id),
            problem=problem,
            revision=self._revision(owner_principal_id, selected, effective),
            steps=steps,
            next_action=next_action,
        )

    # ── readiness steps ──────────────────────────────────────────────────────

    def _has_connection(self, owner_principal_id: str, profile_id: str) -> bool | None:
        """Whether the owner can reach this profile's provider at all.

        With a profile: a local runtime needs no saved connection, and a hosted
        one needs the owner's own. Without one: whether *any* provider is
        connected, because the first step of "nothing chosen yet" is still
        "is there anything to choose from". ``None`` when the store cannot say.
        """
        from raiker.models.connections import list_model_connections

        try:
            connected = set(list_model_connections(self.store, owner_principal_id))
        except Exception:  # noqa: BLE001 — unknown, not "not connected"
            return None
        if not profile_id:
            return bool(connected)
        if profile_id in connected:
            return True
        try:
            from raiker.models.registry import ModelProfileRegistry

            profile = ModelProfileRegistry.load().resolve_profile_id(profile_id)
        except Exception:  # noqa: BLE001
            return None
        # A local runtime and a hosted profile whose key lives in the
        # environment are both reachable without a saved connection; whether
        # they really answer is the readiness check's question, not this one.
        return True if profile.local_only else None

    def _catalogue_lists(self, owner_principal_id: str, selected: ModelChoice) -> bool | None:
        """Whether the provider's last catalogue named the selected model."""
        if not selected.profile_id or not selected.model:
            return None
        try:
            listed = self.store.list_provider_catalogue(owner_principal_id, selected.profile_id)
        except Exception:  # noqa: BLE001
            return None
        if not listed:
            return None
        return selected.model in listed

    # ── runtime ──────────────────────────────────────────────────────────────

    def _running(self, profile_id: str) -> bool | None:
        """Whether a managed local process is serving this profile.

        ``None`` for anything without a local slot, and when no pool was given
        to ask. "Not running" is not a true statement about a hosted endpoint,
        and rendering it as `false` puts a stopped-looking state next to a model
        that is working perfectly.
        """
        for runtime in self.runtimes:
            if any(slot.profile_id == profile_id for slot in runtime.slots):
                try:
                    return bool(runtime.status(profile_id).running)
                except Exception:  # noqa: BLE001 — a runtime that cannot be asked is unknown
                    return None
        return None

    # ── revision ─────────────────────────────────────────────────────────────

    def _revision(
        self, owner_principal_id: str, selected: ModelChoice, effective: ModelChoice
    ) -> str:
        """A token that changes exactly when the decision changes.

        Deliberately a fingerprint and not a counter. A counter claims an
        ordering, and Raiker keeps no monotonic sequence for model selection —
        producing one here would mean either scanning the event log on every
        read or writing a new row on every selection, and the caller's actual
        need is only "is this the same answer I already have". A digest of the
        inputs answers that honestly and costs nothing.
        """
        try:
            surfaces = sorted(
                (str(s), str(p), str(m))
                for s, p, m in (self.store.list_surface_model_defaults(owner_principal_id) or [])
            )
        except Exception:  # noqa: BLE001
            surfaces = []
        material = json.dumps(
            {
                "selected": selected.to_dict(),
                "effective": effective.to_dict(),
                "surfaces": surfaces,
            },
            sort_keys=True,
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


#: The four steps, in the order an owner meets them (UX-MODEL-02).
_STEP_LABELS: tuple[tuple[str, str], ...] = (
    ("connect", "Provider connected"),
    ("discover", "Model found"),
    ("choose", "Model chosen"),
    ("run", "Runs"),
)

#: Which step a readiness verdict stops at, and the one action that moves it.
#: Keyed by reason code first, because one state can mean two different steps:
#: ``unsupported`` is a catalogue the provider will not list *or* an execution
#: check it will not run, and they are fixed in different places.
_REASON_STEP: dict[str, tuple[str, NextAction]] = {
    "provider_not_configured": ("connect", {"label": "Connect the provider", "target": "add"}),
    "local_runtime_missing": ("connect", {"label": "Install the runtime", "target": "runtime"}),
    "provider_authentication_failed": ("connect", {"label": "Update the credential", "target": "add"}),
    "provider_workspace_required": ("connect", {"label": "Add the workspace ID", "target": "add"}),
    "provider_workspace_invalid": ("connect", {"label": "Check the workspace ID", "target": "add"}),
    "provider_model_missing": ("discover", {"label": "Choose an available model", "target": "models"}),
    "local_model_missing": ("discover", {"label": "Download the model", "target": "models"}),
    "model_catalogue_unsupported": ("discover", {"label": "Choose a supported provider", "target": "add"}),
    "local_runtime_unreachable": ("run", {"label": "Start the runtime", "target": "runtime"}),
    "provider_policy_blocked": ("run", {"label": "Review model policy", "target": "permissions"}),
    "provider_quota_exhausted": ("run", {"label": "Check again after adding credit", "target": "check"}),
}
_STATE_STEP: dict[str, tuple[str, NextAction]] = {
    "not_configured": ("connect", {"label": "Connect the provider", "target": "add"}),
    "authentication_failed": ("connect", {"label": "Update the credential", "target": "add"}),
    "runtime_missing": ("connect", {"label": "Install the runtime", "target": "runtime"}),
    "model_missing": ("discover", {"label": "Choose an available model", "target": "models"}),
    "configuration_unreadable": ("choose", {"label": "Choose the model again", "target": "models"}),
    "runtime_stopped": ("run", {"label": "Start the runtime", "target": "runtime"}),
}


def readiness_steps(
    *,
    selected: ModelChoice,
    head: ModelReadiness | None,
    has_connection: bool | None,
    catalogue_lists_model: bool | None,
) -> tuple[tuple[ReadinessStep, ...], NextAction | None]:
    """Say the decision as four steps and one next action (UX-MODEL-02).

    "Provider connected", "models discovered", "model selected" and "runtime
    available" were four facts the owner had to read off four places and put in
    order themselves. This puts them in order: every step before the one that
    stops the work is done, that one is ``blocked`` and carries the action, and
    every step after it is ``waiting`` — not failed, because nothing has been
    asked of it yet. A pair that has never been checked is ``unchecked`` at
    ``run``; it is not reported as broken, and the action is to check it.

    Pure, so the table can be tested one verdict at a time; nothing here reads a
    store or invents a verdict readiness did not give.
    """
    blocked_at: str | None = None
    unchecked_run = False
    action: NextAction | None = None

    if not selected.profile_id or not selected.model:
        if has_connection is False:
            blocked_at = "connect"
            action = {"label": "Connect a provider", "target": "add"}
        else:
            blocked_at = "choose"
            action = {"label": "Choose a model", "target": "models"}
    elif head is None or head.ready:
        blocked_at = None
    elif head.reason_code == "model_not_checked" or head.state.value in ("stale", "checking"):
        unchecked_run = True
        action = {"label": "Check it now", "target": "check"}
    else:
        step, action = _REASON_STEP.get(head.reason_code) or _STATE_STEP.get(
            head.state.value, ("run", {"label": "Check again", "target": "check"})
        )
        blocked_at = step

    steps: list[ReadinessStep] = []
    reached_block = False
    for step_id, label in _STEP_LABELS:
        state: ReadinessStepState
        if reached_block:
            state = "waiting"
        elif step_id == blocked_at:
            state = "blocked"
            reached_block = True
        elif unchecked_run and step_id == "run":
            state = "unchecked"
        elif (
            unchecked_run
            and step_id == "connect"
            and has_connection is not True
        ) or (unchecked_run and step_id == "discover" and catalogue_lists_model is not True):
            # Never checked, and nothing else on record says this step passed:
            # say so rather than tick it.
            state = "unchecked"
        else:
            state = "done"
        steps.append(
            cast(ReadinessStep, {"id": step_id, "label": label, "state": state})
        )
    if selected.profile_id and selected.model and head is None:
        # `resolve_chain` could not be read: the decision already carries the
        # problem, and no step claims to have passed a check it never saw.
        steps = [
            cast(ReadinessStep, {**step, "state": "unchecked"}) for step in steps
        ]
        action = {"label": "Check it now", "target": "check"}
    return tuple(steps), action


def _problem(entry: ModelReadiness | None) -> dict[str, str] | None:
    """The selection's own obstacle, in the words readiness already chose."""
    if entry is None:
        return {
            "reason_code": "no_model_selected",
            "summary": "No model is selected.",
            "remediation": "Choose a model on the Models page.",
        }
    if entry.ready:
        return None
    return {
        "reason_code": entry.reason_code,
        "summary": entry.summary,
        "remediation": entry.remediation,
    }
