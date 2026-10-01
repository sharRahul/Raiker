"""Model profiles, context usage, pricing, provider listings and Models."""

from __future__ import annotations

import sys
from dataclasses import asdict, dataclass, field
from typing import Any

from raiker.contracts.views import View

# Capability states that mean the gate is off / fail-closed.
_DISABLED_STATES = {"disabled", "planned"}


def _runs_on_this_platform(profile: Any) -> bool:
    """Whether a profile's runtime can exist on the machine Raiker is on.

    MLX is an Apple-silicon framework, so on Windows and Linux its four slot
    profiles were four rows in every provider list, four entries in the model
    picker, and four things to set up that nothing on the machine could ever
    serve. A profile whose runtime cannot exist here is not a choice, so it is
    not published. Profiles that declare nothing are published everywhere —
    llama.cpp included, which runs on macOS as happily as it does anywhere.
    """
    required = profile.raw.get("requires_platform")
    if not required:
        return True
    platforms = required if isinstance(required, list) else [required]
    return sys.platform in {str(name) for name in platforms}


#: The declaration a profile carries when it is only meant to be offered once its
#: provider has been found. Shipped on every managed local slot and on the Ollama
#: native default; inert until BUG-270 gave it an enforcer.
DETECT_FIRST_STATE = "disabled_until_provider_detected"


def _names_an_available_model(
    profile: Any,
    effective_model: str,
    presence: dict[str, bool | None],
    deployed_profile_ids: frozenset[str],
) -> bool:
    """Whether a surface may name ``effective_model`` as a model this owner has.

    Three questions in order, and each one is about a different kind of absence:

    1. **Is there a model string at all?** The `<model>` placeholder means the
       owner has not chosen one. This was the whole of the old predicate.
    2. **Does the profile ask to be detected first?** Only profiles declaring
       ``disabled_until_provider_detected`` do, and they are exactly the ones
       whose model string is a promise about software on this machine — the
       Ollama native default naming a third-party model, and the managed
       llama.cpp/MLX slots naming the `local-gguf…` aliases Raiker itself
       invents when a model is deployed into a slot.
    3. **Has that promise been kept?** A saved connection or a completed
       deployment is the owner's own evidence and settles it outright. Failing
       that, the runtime must have been *detected present* — not merely
       "not known to be absent", because an unknown answer about someone else's
       machine is not a licence to claim a model they may not have.
    """
    if not effective_model or "<" in effective_model:
        return False
    if str(getattr(profile, "default_state", "")) != DETECT_FIRST_STATE:
        return True
    if profile.profile_id in deployed_profile_ids:
        return True
    # A managed slot's alias exists only once a model is deployed into it; the
    # runtime binary being installed is no evidence of that.
    if profile.raw.get("managed_slot"):
        return False
    return presence.get(profile.provider) is True


@dataclass(frozen=True)
class ModelProfileView(View):
    profile_id: str
    provider: str
    model: str
    default_state: str
    local_only: bool
    requires_network: bool
    endpoint_kind: str
    requires_egress_policy: bool
    requires_budget_policy: bool
    runtime_gate: str | None
    off_machine: bool
    selected: bool
    connection_configured: bool = False
    usage_admin_configured: bool = False
    workspace_configured: bool = False
    # Prompt-cache TTL breakpoint the provider uses for this profile ("5m"/"1h"),
    # or None when the provider/profile does not cache. Read-only status.
    prompt_cache_ttl: str | None = None
    # Context capacity and pricing are configuration-owned facts. They stay
    # unset for placeholder or provider-discovered models rather than guessed.
    context_window_tokens: int | None = None
    context_window_source: str | None = None
    # BUG-270 — "does this profile name a model that exists here", which is more
    # than "does it name a model string". A profile that declares
    # `disabled_until_provider_detected` has to earn it: the runtime is detected
    # on this machine, or the owner has connected it or deployed into it.
    configured: bool = False
    # Why `configured` came out the way it did, for the profiles whose answer
    # depends on this host. `True`/`False` are detection results; `None` means
    # either nothing has looked yet or the profile's availability does not
    # depend on a local runtime, and the UI says nothing in that case rather
    # than claiming an absence it has not established.
    provider_detected: bool | None = None
    readiness_state: str = "not_configured"
    readiness_summary: str = "No readiness check exists for this exact model."
    readiness_reason_code: str = "model_not_checked"
    readiness_checked_at: str | None = None
    readiness_expires_at: str | None = None
    readiness_remediation: str = "Set up or check this model before sending."
    ready: bool = False
    # Only a provider Raiker authenticates with an API key can accrue an API
    # bill, so only those carry cost. A local runtime reports `billable=False`
    # and the UI says "no API cost" rather than an unexplained blank.
    billable: bool = False
    # All-time usage on this provider for the acting owner. `cost` is None when
    # no price is resolvable — never 0, which would read as "free".
    models_used: int = 0
    turns_used: int = 0
    total_tokens: int = 0
    total_cost: str | None = None
    cost_currency: str | None = None
    # Where the active model's price came from: "owner" | "provider" | "config".
    price_source: str | None = None
    price_as_of: str | None = None
    # Provider-declared capability facts. The UI never infers them from a
    # model name or fabricates effort values.
    supports_reasoning: bool = False
    supports_reasoning_effort: bool = False
    reasoning_effort_values: tuple[str, ...] = ()
    # BUG-207 slice B — a provider declares reasoning as an *effort* (OpenAI) or
    # as a *mode* (Anthropic). Sending only the effort values meant the composer
    # could offer a reasoning control for one provider and none for the other,
    # which is why the thinking the product asked for was never asked for.
    reasoning_modes: tuple[str, ...] = ()
    supports_reasoning_summary: bool = False
    # The image models this provider declares, default first, empty for a
    # provider that generates no images. This was read by the Design page and
    # never sent by this view, so the surface asked every profile whether it had
    # an image model and every profile answered `undefined` — the picker was
    # empty on every real install, and only looked correct in a fixture that had
    # no image provider either.
    image_models: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContextUsageView(View):
    """What one conversation has used, and what it has cost.

    Every figure is optional and every one names its source. A missing price, a
    provider that reports no usage, or a model with no published capacity all
    resolve to None here and to an explicit "unavailable" in the UI — this view
    never substitutes a zero or an estimate for a fact it does not have.
    """

    session_id: str
    profile_id: str | None
    provider: str | None
    model: str | None
    # Provider-reported prompt tokens for the newest turn, when one exists.
    used_tokens: int | None
    context_window_tokens: int | None
    context_window_source: str | None
    # "provider" once a turn has run; "unavailable" before that, at which point
    # the browser falls back to its own labelled transcript estimate.
    usage_source: str
    billable: bool
    session_cost: str | None
    provider_total_cost: str | None
    currency: str | None
    price_source: str | None
    price_as_of: str | None
    session_turns: int = 0
    session_input_tokens: int = 0
    session_output_tokens: int = 0
    # BUG-21 — the individual rate components behind `session_cost`, read from
    # the normalised registry. All four are optional and independently sourced:
    # a provider that publishes no cache rate leaves those None rather than
    # having one inferred from the input rate.
    price_input_per_mtok: str | None = None
    price_output_per_mtok: str | None = None
    price_cache_write_per_mtok: str | None = None
    price_cache_read_per_mtok: str | None = None
    price_effective_from: str | None = None
    # True when the conversation runs on a billable provider for which no exact
    # rate exists. The popover states "Unknown" and offers Configure → rather
    # than showing nothing or implying the turn was free.
    price_unknown: bool = False
    # Latest automatic provider-context compaction. This is deliberately
    # metadata-only; the summary remains in the encrypted workspace store and
    # transcript turns are never rewritten.
    latest_compaction: dict[str, Any] | None = None
    # Backlog #16 — how much of the tool catalogue this turn carries.
    # `tools_deferred` is the count whose schemas are fetched on request rather
    # than sent every time; both are stated because "25 of 50" is the honest
    # form of a saving, and an owner should be able to see that a tool being
    # absent from a request is not a tool being withheld.
    tools_projected: int = 0
    tools_deferred: int = 0


@dataclass(frozen=True)
class ModelPricingEntryView:
    """One exact model's pricing row for the Models → Pricing surface (BUG-21)."""

    provider: str
    model: str
    profile_id: str | None
    source: str | None
    currency: str | None
    input_per_mtok: str | None
    output_per_mtok: str | None
    cache_write_per_mtok: str | None
    cache_read_per_mtok: str | None
    effective_from: str | None
    as_of: str | None
    reviewed_at: str | None
    review_due_at: str | None
    review_status: str | None
    recorded_at: str | None
    recorded_by: str | None
    reason: str | None
    has_owner_override: bool
    history: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["history"] = [dict(entry) for entry in self.history]
        return data


@dataclass(frozen=True)
class ModelPricingView(View):
    """Everything Models → Pricing has to state, in one governed read."""

    entries: tuple[ModelPricingEntryView, ...]
    sync: tuple[dict[str, Any], ...]
    can_override: bool


@dataclass(frozen=True)
class ProviderModelListView(View):
    """On-demand, user-initiated listing of the models a provider serves.

    ``status`` is honest: "available" only when the provider actually answered;
    policy denials and unreachable/unsupported backends never fabricate model
    names.

    A failed listing may still carry ``models``, but only ones
    this provider published on a previous, successful call. ``remembered`` says
    which of the two happened, and ``listed_at`` when the provider last spoke, so
    a stale answer is offered as stale rather than as current. The status and
    reason code are unchanged by remembering: a provider that is unreachable is
    still reported unreachable.
    """

    profile_id: str
    provider: str
    status: str  # "available" | "policy_denied" | "unsupported" | "unavailable"
    reason_code: str | None
    models: tuple[str, ...]
    remembered: bool = False
    listed_at: str | None = None


@dataclass(frozen=True)
class ProviderCatalogueRefreshView(View):
    """Safe outcome for one provider in an explicit catalogue refresh."""

    profile_id: str
    provider: str
    status: str
    reason_code: str | None
    model_count: int


@dataclass(frozen=True)
class ModelsView:
    profiles: tuple[ModelProfileView, ...]
    # Profiles with a concrete configured model are the only choices surfaced
    # by the conversational composer. The full list remains for Models setup.
    chat_profiles: tuple[ModelProfileView, ...]
    current_profile_id: str | None
    hosted_model_gate_state: str
    private_network_model_gate_state: str
    # What the *enforcing* path answers for these two gates right now, which is
    # not the same question as what the gate row says. A saved connection is the
    # owner's consent to use that provider (`provider_runtime_policy_from_gates`,
    # resolution 3), so a hosted provider runs with the gate row still unset.
    # Reporting only `..._state` printed "Off" directly above a connected
    # provider that had just answered — FIXED-322's defect, on a second surface.
    # `state` is untouched, so nothing that already consumes it changes meaning.
    hosted_model_gate_enforced: bool
    private_network_model_gate_enforced: bool
    model_egress_allowlist_configured: bool
    remote_profile_count: int
    ready_provider_count: int = 0
    # BUG-270 — how many models the owner actually has set up, counted where the
    # facts are: an empty llama.cpp slot's `local-gguf…` alias and an undetected
    # Ollama default are model strings, not models.
    usable_provider_count: int = 0
    # User-owned ordered model fallback sequence (profile ids). When the selected
    # provider is unavailable, the runtime walks this list in order; each candidate
    # is still gated by provider policy, so hosted access is never granted silently.
    fallback_sequence: tuple[str, ...] = ()
    # The runtime never silently falls back to hosted providers; hosted runtime is not enabled.
    no_silent_hosted_fallback: bool = True
    # Concrete model bound by the current selection (the persisted per-profile
    # model override when present, else the selected profile's own model).
    # None when nothing is selected or the selection is an unresolved placeholder.
    current_model: str | None = None
    # User-owned advisor model (web-app task 2): the profile a local model may
    # consult through the governed `consult_advisor` tool. Persisting it grants
    # nothing — the consult is gated by advisor_model_runtime + decision mode +
    # provider policy at call time.
    advisor_profile_id: str | None = None
    advisor_model_gate_state: str = "unknown"
    # BUG-82 — the advisor is a second model this runtime calls, chosen in the
    # same UI as the chat model and, until now, never readiness-checked: no
    # probe, no state, no chip, and no row in `GET /api/model-readiness`. An
    # owner could pin an advisor whose provider had no credential, no credit or
    # no running runtime and see nothing wrong until a consult failed mid-turn.
    # These four report the exact model a consult would call and what the last
    # check of *that* model found, so the selector can carry the same chip and
    # repair sentence a provider card does.
    advisor_model: str | None = None
    advisor_readiness_state: str = "not_configured"
    advisor_readiness_summary: str | None = None
    advisor_readiness_remediation: str | None = None
    advisor_readiness_checked_at: str | None = None
    # The one catalogue every composer reads, keyed by
    # profile: the last models each provider published, from the store rather
    # than from a probe, so this read stays free of the network.
    #
    # `chat_profiles` above is unchanged and still decides what a picker offers
    # *at rest*. This is what search may reach, which is the distinction
    # The rule is: curation orders the quick list, it does not
    # decide what exists.
    catalogues: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profiles": [p.to_dict() for p in self.profiles],
            "chat_profiles": [p.to_dict() for p in self.chat_profiles],
            "catalogues": {
                profile_id: list(models) for profile_id, models in self.catalogues.items()
            },
            "current_profile_id": self.current_profile_id,
            "current_model": self.current_model,
            "advisor_profile_id": self.advisor_profile_id,
            "advisor_model_gate_state": self.advisor_model_gate_state,
            "advisor_model": self.advisor_model,
            "advisor_readiness_state": self.advisor_readiness_state,
            "advisor_readiness_summary": self.advisor_readiness_summary,
            "advisor_readiness_remediation": self.advisor_readiness_remediation,
            "advisor_readiness_checked_at": self.advisor_readiness_checked_at,
            "hosted_model_gate_state": self.hosted_model_gate_state,
            "private_network_model_gate_state": self.private_network_model_gate_state,
            "hosted_model_gate_enforced": self.hosted_model_gate_enforced,
            "private_network_model_gate_enforced": self.private_network_model_gate_enforced,
            "model_egress_allowlist_configured": self.model_egress_allowlist_configured,
            "remote_profile_count": self.remote_profile_count,
            "ready_provider_count": self.ready_provider_count,
            "usable_provider_count": self.usable_provider_count,
            "fallback_sequence": list(self.fallback_sequence),
            "no_silent_hosted_fallback": self.no_silent_hosted_fallback,
        }
