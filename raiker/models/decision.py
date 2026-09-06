"""One authoritative answer to "which model is this, and which one will run".

MODEL-01. Raiker already persisted every part of this correctly, and that was
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
    must keep showing.
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
from typing import Any

from raiker.models.readiness import ModelReadiness, ModelReadinessService

#: The work surfaces that may hold their own default model.
#:
#: Chat, Build and Design are the three Work modes: each is a way of giving
#: Raiker something to do, and each wants a different kind of model — a
#: conversational one, a coding one, one that draws. Tasks and Schedule are not
#: modes; they *capture* the model onto the task they create, so a run that
#: fires next Tuesday uses the model that was chosen when it was scheduled
#: rather than whatever the owner has selected by then.
#:
#: MODEL-02 added ``design``. Its absence was not a missing feature so much as a
#: contradiction: the product model is Chat | Build | Design, and two of the
#: three had explicit surface state while the third silently borrowed the global
#: default. An owner who set Chat to a small local model would have had their
#: image prompts follow it.
SURFACES: tuple[str, ...] = ("chat", "build", "design", "tasks", "schedule")

#: Where a selection came from, most specific first. The order is the resolution
#: order, and the interface uses it to explain *why* this model is selected.
SELECTION_SOURCES: tuple[str, ...] = ("surface_default", "global_default", "native_default")


@dataclass(frozen=True)
class ModelChoice:
    """A profile and a concrete model, with why it is the one being named."""

    profile_id: str
    model: str
    #: For ``selected``: one of ``SELECTION_SOURCES``.
    #: For ``effective``: ``selected``, ``fallback`` or ``no_ready_candidate``.
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {"profile_id": self.profile_id, "model": self.model, "source": self.source}


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": {"surface": self.surface, "project_id": self.project_id},
            "selected": self.selected.to_dict(),
            # `effective.source` answers "why this one", which for the effective
            # pair is the reason it displaced the selection — so the field is
            # spelled `reason` on the wire, matching how the interface reads it.
            "effective": {
                "profile_id": self.effective.profile_id,
                "model": self.effective.model,
                "reason": self.effective.source,
            },
            "ready": self.ready,
            "running": self.running,
            "problem": self.problem,
            "revision": self.revision,
        }


class ModelDecisionService:
    """Assembles the decision for one owner and one surface.

    Every read is best-effort in the same direction: a store that cannot be
    read degrades to a less specific source rather than to an error, because a
    composer that will not render is worse for the owner than a composer
    showing the global default. The one thing it never does is *invent*
    readiness — an unreadable configuration reports itself as a problem.
    """

    def __init__(self, store: Any, readiness: ModelReadinessService | None = None) -> None:
        self.store = store
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

        try:
            profile_id, model = self.readiness.resolve_request_target(
                owner_principal_id, None, None
            )
        except Exception:  # noqa: BLE001
            return ModelChoice("", "", "native_default")
        # `resolve_request_target` ends at the shipped native default when the
        # owner has never chosen, which is a real answer and a different one
        # from a stored global selection. Telling them apart is what lets the
        # interface say "you have not chosen a model yet" without guessing.
        source = "global_default" if self._has_global_selection(owner_principal_id) else (
            "native_default"
        )
        return ModelChoice(profile_id, model, source)

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

        return ModelDecision(
            surface=surface,
            project_id=project_id or None,
            selected=selected,
            effective=effective,
            ready=first_ready is not None,
            running=self._running(effective.profile_id),
            problem=problem,
            revision=self._revision(owner_principal_id, selected, effective),
        )

    # ── runtime ──────────────────────────────────────────────────────────────

    def _running(self, profile_id: str) -> bool | None:
        """Whether a managed local process is serving this profile.

        ``None`` for anything without a local slot. "Not running" is not a true
        statement about a hosted endpoint, and rendering it as `false` puts a
        stopped-looking state next to a model that is working perfectly.
        """
        if not profile_id:
            return None
        try:
            from raiker.models.local_runtime import ManagedLlamaRuntime, slot_for_profile
            from raiker.models.mlx_runtime import MLX_SLOTS, ManagedMlxRuntime
        except Exception:  # noqa: BLE001 — no local runtime support on this host
            return None

        if slot_for_profile(profile_id) is not None:
            try:
                return bool(ManagedLlamaRuntime().status(profile_id).running)
            except Exception:  # noqa: BLE001 — a runtime that cannot be asked is unknown
                return None
        if any(slot.profile_id == profile_id for slot in MLX_SLOTS):
            try:
                return bool(ManagedMlxRuntime().status(profile_id).running)
            except Exception:  # noqa: BLE001
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
