# mypy: disable-error-code="misc"
"""Models and connections: selection, pricing, capacity, provider catalogues,
context usage and diagnostics (GCR-43).

One part of :class:`raiker.control.dashboard.DashboardService`, which inherits it. Every method
is typed against the whole store (``self: DashboardService``), so a call into another
part is checked exactly as it was when every method lived in one class. mypy
reports that self-type as ``misc`` on a mixin, which is the one code this file
turns off.
"""

from __future__ import annotations

import contextlib
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from raiker.approval_previews import redact_secret_like_text
from raiker.build_identity import version as raiker_version
from raiker.contracts.ids import new_id, utc_now
from raiker.control.dtos import ControlResult
from raiker.control.views.extensions import ConnectionsView, ConnectorView
from raiker.control.views.models import (
    _DISABLED_STATES,
    ContextUsageView,
    ModelPricingEntryView,
    ModelPricingView,
    ModelProfileView,
    ModelsView,
    ProviderCatalogueRefreshView,
    ProviderModelListView,
    _names_an_available_model,
    _runs_on_this_platform,
)
from raiker.control.views.security import DiagnosticsView, ProviderHealthView
from raiker.events.writer import EventLogWriter
from raiker.models.endpoint_policy import MODEL_EGRESS_ALLOWLIST_ENV
from raiker.models.exceptions import (
    ModelProviderError,
    ProviderPolicyError,
    provider_error_code,
    safe_error,
)
from raiker.models.factory import ModelProviderFactory
from raiker.models.policy_state import (
    HOSTED_MODEL_GATE,
    PRIVATE_NETWORK_MODEL_GATE,
    provider_runtime_policy_from_gates,
)
from raiker.models.registry import ModelProfileRegistry, profile_with_model, resolve_builtin_config
from raiker.models.router import ModelRouter
from raiker.models.session_state import TERMINAL_MODEL_SESSION_ID, ModelSessionState
from raiker.models.tool_projection import ALWAYS_PROJECTED, DEFERRABLE_TOOL_NAMES
from raiker.runtime.executors.tier2_image import declared_image_models
from raiker.runtime.model_facts_store import ModelFactsStore

if TYPE_CHECKING:
    from raiker.control.dashboard import DashboardService


#: Providers whose availability is a fact about *this machine* — the runtime has
#: to be installed here before any surface may name a model it would serve.
LOCAL_RUNTIME_PROVIDERS: frozenset[str] = frozenset({"ollama", "llama.cpp", "mlx", "vllm"})


class ModelService:

    def get_models(self: DashboardService, acting_principal_id: str | None = None) -> ModelsView:
        registry = ModelProfileRegistry.load()
        scoped_principal = (
            acting_principal_id
            if acting_principal_id and self.store.get_account(acting_principal_id) is not None
            else None
        )
        state = (
            self.store.load_principal_model_state(scoped_principal)
            if scoped_principal
            else self.store.load_model_session_state(TERMINAL_MODEL_SESSION_ID)
        )
        native_default = next(
            (
                profile
                for profile in registry.list_profiles()
                if profile.raw.get("is_native_default")
            ),
            None,
        )
        # BUG-270 — what this machine actually has. Detection is a PATH lookup
        # cached in a row, so this read never contacts anything; `detect` only
        # re-probes a runtime whose row is missing or an hour old.
        from raiker.models import local_presence

        presence: dict[str, bool | None] = {
            runtime: result.present
            for runtime, result in local_presence.detect(self.store).items()
        }
        # A model the owner deployed into a managed slot, or connected. Either is
        # the owner's own evidence that the profile serves something, and it
        # outranks detection: a slot with a model in it is not "undetected".
        configured_pairs = (
            self.store.list_configured_models(acting_principal_id) if acting_principal_id else []
        )
        deployed_profile_ids = frozenset(profile_id for profile_id, _ in configured_pairs)
        # The implicit native default is adopted only when it names a model this
        # machine can actually serve. Before BUG-270 a fresh install adopted it
        # unconditionally, which is how `gemma4:31b-cloud` reached the Global
        # model control and both composer chips on a host with no Ollama. An
        # *explicit* selection is still honoured whatever detection says — the
        # owner is the authority on their own machine, and a selection they made
        # is not Raiker's to quietly drop.
        native_default_available = native_default is not None and _names_an_available_model(
            native_default,
            str(native_default.raw.get("model", "")),
            presence,
            deployed_profile_ids,
        )
        current = (
            state.profile_id
            if state is not None
            else (
                native_default.profile_id
                if native_default is not None and native_default_available
                else None
            )
        )
        # The persisted per-profile model override (e.g. an Ollama/OpenAI model
        # picked at selection time) is what the runtime actually binds, so the
        # selected profile card shows it instead of the profile's placeholder.
        override = state.model if state is not None and state.model else None
        hosted_gate = self.control.get_capability_gate(HOSTED_MODEL_GATE, acting_principal_id)
        private_gate = self.control.get_capability_gate(
            PRIVATE_NETWORK_MODEL_GATE, acting_principal_id
        )
        advisor_gate = self.control.get_capability_gate(
            "advisor_model_runtime", acting_principal_id
        )
        # The same resolution the provider factory is built with everywhere else,
        # so the posture tiles report the answer the enforcing path gives rather
        # than the gate row alone.
        enforced_policy = provider_runtime_policy_from_gates(self.store, acting_principal_id)
        from raiker.models.connections import get_model_connection
        from raiker.models.readiness import ModelReadinessService, ProviderCatalogueProbe
        from raiker.runtime.model_usage import ModelUsageLedger, sum_totals

        # One ledger read for the whole page, grouped by provider, so each card
        # can show its own spend without a query per card.
        usage_by_provider: dict[str, list[Any]] = {}
        if acting_principal_id:
            for row in ModelUsageLedger(self.store).provider_usage(acting_principal_id):
                usage_by_provider.setdefault(row.provider, []).append(row)
        readiness_service = ModelReadinessService(
            self.store,
            probe=ProviderCatalogueProbe(self.store),
        )

        def _usage_fields(profile: Any) -> dict[str, Any]:
            rows = usage_by_provider.get(profile.provider, [])
            totals = sum_totals(rows)
            billable = self._profile_is_billable(profile)
            cost = None
            currency = None
            price_source = None
            price_as_of = None
            if billable and rows:
                # Price each model at its own rate and add them up: a provider's
                # cheap and expensive models differ by an order of magnitude, so
                # one blended rate across the provider would be meaningless.
                total = Decimal(0)
                priced_any = False
                for row in rows:
                    facts = self._resolve_facts(profile, row.model, acting_principal_id)
                    row_cost = row.totals.cost(facts)
                    if row_cost is None:
                        continue
                    priced_any = True
                    total += row_cost
                    if facts.price is not None and price_source is None:
                        currency = facts.price.currency
                        price_source = facts.price.source
                        price_as_of = facts.price.as_of
                if priced_any:
                    cost = str(total)
            return {
                "billable": billable,
                "models_used": len({row.model for row in rows}),
                "turns_used": totals.turns,
                "total_tokens": totals.total_tokens,
                "total_cost": cost,
                "cost_currency": currency,
                "price_source": price_source,
                "price_as_of": price_as_of,
            }

        registry_profiles = tuple(
            p
            for p in registry.list_profiles()
            if not bool(p.raw.get("test_only", False))
            and not bool(p.raw.get("setup_hidden", False))
            and _runs_on_this_platform(p)
        )

        def _profile_view(
            profile: Any, effective_model: str, *, selected: bool
        ) -> ModelProfileView:
            facts = self._resolve_facts(profile, effective_model, acting_principal_id)
            saved_connection = (
                get_model_connection(self.store, acting_principal_id, profile.profile_id)
                if acting_principal_id
                else None
            )
            readiness = (
                readiness_service.current_selected(
                    acting_principal_id,
                    profile.profile_id,
                    effective_model,
                )
                if acting_principal_id and effective_model and "<" not in effective_model
                else None
            )
            return ModelProfileView(
                profile_id=profile.profile_id,
                provider=profile.provider,
                model=effective_model,
                default_state=profile.default_state,
                local_only=profile.local_only,
                requires_network=profile.requires_network,
                endpoint_kind=str(profile.raw.get("endpoint_kind", "unknown")),
                requires_egress_policy=bool(profile.raw.get("requires_egress_policy", False)),
                requires_budget_policy=bool(profile.raw.get("requires_budget_policy", False)),
                runtime_gate=self._runtime_gate_for_profile(
                    str(profile.raw.get("endpoint_kind", "unknown"))
                ),
                off_machine=str(profile.raw.get("endpoint_kind", "unknown"))
                in {"remote_hosted", "private_network"},
                selected=selected,
                connection_configured=bool(saved_connection),
                usage_admin_configured=bool(
                    saved_connection and saved_connection.get("admin_api_key")
                ),
                # BUG-274 — whether a workspace is named, never which one. The
                # card needs to know the field is filled so it can say so and
                # offer to clear it; the value itself stays in the vault.
                workspace_configured=bool(
                    saved_connection and saved_connection.get("workspace_id")
                ),
                prompt_cache_ttl=(
                    str(profile.raw.get("prompt_cache_ttl"))
                    if profile.raw.get("prompt_cache_ttl")
                    else None
                ),
                context_window_tokens=facts.context_window_tokens,
                context_window_source=facts.context_window_source,
                configured=_names_an_available_model(
                    profile, effective_model, presence, deployed_profile_ids
                ),
                provider_detected=(
                    presence.get(profile.provider)
                    if profile.provider in LOCAL_RUNTIME_PROVIDERS
                    else None
                ),
                readiness_state=(readiness.state.value if readiness else "not_configured"),
                readiness_summary=(
                    readiness.summary
                    if readiness
                    else "Choose a concrete model before checking readiness."
                ),
                readiness_reason_code=(
                    readiness.reason_code if readiness else "model_not_configured"
                ),
                readiness_checked_at=(readiness.checked_at if readiness else None),
                readiness_expires_at=(readiness.expires_at if readiness else None),
                readiness_remediation=(
                    readiness.remediation
                    if readiness
                    else "Choose a model, then check the connection."
                ),
                ready=bool(readiness and readiness.ready),
                supports_reasoning=bool(profile.raw.get("supports_reasoning", False)),
                supports_reasoning_effort=bool(profile.raw.get("supports_reasoning_effort", False)),
                reasoning_effort_values=tuple(
                    str(value) for value in profile.raw.get("reasoning_effort_values", [])
                ),
                reasoning_modes=tuple(
                    str(value) for value in profile.raw.get("reasoning_modes", [])
                ),
                supports_reasoning_summary=bool(
                    profile.raw.get("supports_reasoning_summary", False)
                ),
                image_models=declared_image_models(profile.raw),
                **_usage_fields(profile),
            )

        configured_by_profile: dict[str, list[str]] = {}
        for profile_id, configured_model in configured_pairs:
            configured_by_profile.setdefault(profile_id, []).append(configured_model)

        def _card_model(profile: Any) -> str:
            if override and profile.profile_id == current:
                return override
            choices = configured_by_profile.get(profile.profile_id, [])
            if profile.model == "<model>" and choices:
                return choices[-1]
            return profile.model

        profiles = tuple(
            _profile_view(
                profile,
                _card_model(profile),
                selected=profile.profile_id == current,
            )
            for profile in registry_profiles
        )

        chat_profiles: list[ModelProfileView] = []
        seen_choices: set[tuple[str, str]] = set()
        for profile in registry_profiles:
            # A runtime slot's `model` is the alias it *would* serve under, not
            # a model anybody has: four llama.cpp slots put "Local GGUF",
            # "Local GGUF 2", "Local GGUF 3" and "Local GGUF 4" into every
            # picker on a machine with no GGUF served and nothing to serve it.
            # A slot earns a place here by being deployed, which is what writes
            # its configured model.
            #
            # BUG-270 — the same reasoning covers a profile that names a
            # *third-party* model the machine may not have. `ollama-local` ships
            # `gemma4:31b-cloud`, which is not a slot alias, so it passed the
            # test above and reached every picker and both composer chips on a
            # host with no Ollama. A profile that asks to be detected first only
            # contributes its declared model once it has been.
            slot_alias = str(profile.raw.get("served_model_name") or "")
            declared = (
                []
                if profile.model == "<model>"
                or (slot_alias and profile.model == slot_alias)
                or not _names_an_available_model(
                    profile, profile.model, presence, deployed_profile_ids
                )
                else [profile.model]
            )
            choices = declared + configured_by_profile.get(profile.profile_id, [])
            for configured_model in choices:
                key = (profile.profile_id, configured_model)
                if key in seen_choices:
                    continue
                seen_choices.add(key)
                chat_profiles.append(
                    _profile_view(
                        profile,
                        configured_model,
                        selected=(
                            profile.profile_id == current
                            and configured_model == (override or profile.model)
                        ),
                    )
                )
        # The remembered catalogue for every profile the
        # owner has listed, read from the store in one pass. No probe and no
        # network: this is what each provider last published, which is exactly
        # what a picker's search should be able to reach.
        catalogues: dict[str, tuple[str, ...]] = {}
        if acting_principal_id:
            for profile in registry_profiles:
                with contextlib.suppress(Exception):
                    known = self.store.list_provider_catalogue(
                        acting_principal_id, profile.profile_id
                    )
                    if known:
                        catalogues[profile.profile_id] = tuple(known)
        return ModelsView(
            profiles=profiles,
            chat_profiles=tuple(chat_profiles),
            catalogues=catalogues,
            current_profile_id=current,
            hosted_model_gate_state=hosted_gate.state if hosted_gate is not None else "unknown",
            private_network_model_gate_state=private_gate.state
            if private_gate is not None
            else "unknown",
            hosted_model_gate_enforced=enforced_policy.allow_hosted_provider,
            private_network_model_gate_enforced=(
                enforced_policy.allow_private_network_provider
            ),
            model_egress_allowlist_configured=bool(
                os.environ.get(MODEL_EGRESS_ALLOWLIST_ENV, "").strip()
            ),
            remote_profile_count=sum(1 for p in profiles if p.off_machine),
            ready_provider_count=sum(1 for p in profiles if p.ready),
            usable_provider_count=sum(1 for p in profiles if p.configured),
            fallback_sequence=tuple(
                self.store.load_principal_model_fallback_sequence(scoped_principal)
                if scoped_principal
                else self.store.load_model_fallback_sequence(TERMINAL_MODEL_SESSION_ID)
            ),
            current_model=(
                self._current_model(registry, state)
                if state is not None
                else (
                    native_default.model
                    if native_default is not None and native_default_available
                    else None
                )
            ),
            advisor_profile_id=(
                self.store.load_principal_model_advisor(scoped_principal)
                if scoped_principal
                else self.store.load_model_advisor(TERMINAL_MODEL_SESSION_ID)
            ),
            advisor_model_gate_state=advisor_gate.state if advisor_gate is not None else "unknown",
            **self._advisor_readiness_fields(readiness_service, acting_principal_id),
        )

    def _advisor_readiness_fields(
        self: DashboardService, readiness_service: Any, acting_principal_id: str | None
    ) -> dict[str, Any]:
        """Readiness for the exact model a consult would call (BUG-82).

        Resolved through the same per-profile pin the chat chain uses, so a
        hosted advisor chosen in Models → Routing is the model reported on —
        rather than the profile's `<model>` placeholder, which is what made the
        consult refuse `advisor_model_unresolved` for owners who had pinned one.
        """
        from raiker.runtime.advisor import AdvisorService

        blank = {
            "advisor_model": None,
            "advisor_readiness_state": "not_configured",
            "advisor_readiness_summary": None,
            "advisor_readiness_remediation": None,
            "advisor_readiness_checked_at": None,
        }
        if not acting_principal_id:
            return blank
        try:
            resolved = AdvisorService(
                self.workspace_root, self.store, principal_id=acting_principal_id
            ).resolved_advisor()
        except Exception:  # noqa: BLE001 — an unreadable advisor reports "none chosen"
            return blank
        if resolved is None:
            return blank
        profile_id, model = resolved
        try:
            readiness = readiness_service.current_selected(acting_principal_id, profile_id, model)
        except Exception:  # noqa: BLE001 — an unresolvable endpoint is "not checked"
            return {**blank, "advisor_model": model}
        return {
            "advisor_model": model,
            "advisor_readiness_state": readiness.state.value,
            "advisor_readiness_summary": readiness.summary,
            "advisor_readiness_remediation": readiness.remediation,
            "advisor_readiness_checked_at": readiness.checked_at,
        }

    def get_connections(self: DashboardService, acting_principal_id: str | None = None) -> ConnectionsView:
        """Read-only status of every governed service connector.

        Never reaches the network and never exposes a credential value. Each
        connector reports its capability gate state, decision mode, whether the
        owner credential env is set, and whether its host is on the connector
        egress allowlist — so the owner can see exactly what is still
        fail-closed. Enabling a connector is done through the existing capability
        gate + decision-mode control plane (gate-manager only), not here.
        """
        from raiker.runtime.connectors import (
            GCAL_HOST,
            GCAL_TOKEN_ENV,
            GITHUB_HOST,
            GITHUB_TOKEN_ENV,
            GMAIL_HOST,
            GMAIL_TOKEN_ENV,
            SLACK_HOST,
            SLACK_TOKEN_ENV,
        )
        from raiker.runtime.executors.sandbox import connector_egress_allowlist

        allowlist = connector_egress_allowlist()
        connectors: list[ConnectorView] = []
        gh_gate = self.control.get_capability_gate("connector_github_runtime", acting_principal_id)
        connectors.append(
            ConnectorView(
                connector_id="github",
                display_name="GitHub (read-only)",
                capability="connector_github_runtime",
                gate_state=gh_gate.state if gh_gate is not None else "unknown",
                capability_enabled=bool(gh_gate.runtime_enabled) if gh_gate is not None else False,
                decision_mode=gh_gate.decision_mode if gh_gate is not None else "ask",
                credential_env=GITHUB_TOKEN_ENV,
                credential_configured=bool(os.environ.get(GITHUB_TOKEN_ENV, "").strip()),
                egress_host=GITHUB_HOST,
                egress_allowed=GITHUB_HOST in allowlist,
                actions=("read_issue", "read_pull_request"),
                kind="read_only",
            )
        )
        gmail_gate = self.control.get_capability_gate(
            "connector_gmail_runtime", acting_principal_id
        )
        connectors.append(
            ConnectorView(
                connector_id="gmail",
                display_name="Gmail (read-only)",
                capability="connector_gmail_runtime",
                gate_state=gmail_gate.state if gmail_gate is not None else "unknown",
                capability_enabled=(
                    bool(gmail_gate.runtime_enabled) if gmail_gate is not None else False
                ),
                decision_mode=gmail_gate.decision_mode if gmail_gate is not None else "ask",
                credential_env=GMAIL_TOKEN_ENV,
                credential_configured=bool(os.environ.get(GMAIL_TOKEN_ENV, "").strip()),
                egress_host=GMAIL_HOST,
                egress_allowed=GMAIL_HOST in allowlist,
                actions=("read_message", "read_thread"),
                kind="read_only",
            )
        )
        gcal_gate = self.control.get_capability_gate("connector_gcal_runtime", acting_principal_id)
        connectors.append(
            ConnectorView(
                connector_id="gcal",
                display_name="Google Calendar (read-only)",
                capability="connector_gcal_runtime",
                gate_state=gcal_gate.state if gcal_gate is not None else "unknown",
                capability_enabled=(
                    bool(gcal_gate.runtime_enabled) if gcal_gate is not None else False
                ),
                decision_mode=gcal_gate.decision_mode if gcal_gate is not None else "ask",
                credential_env=GCAL_TOKEN_ENV,
                credential_configured=bool(os.environ.get(GCAL_TOKEN_ENV, "").strip()),
                egress_host=GCAL_HOST,
                egress_allowed=GCAL_HOST in allowlist,
                actions=("read_event", "read_calendar"),
                kind="read_only",
            )
        )
        slack_gate = self.control.get_capability_gate(
            "connector_slack_runtime", acting_principal_id
        )
        connectors.append(
            ConnectorView(
                connector_id="slack",
                display_name="Slack (read-only)",
                capability="connector_slack_runtime",
                gate_state=slack_gate.state if slack_gate is not None else "unknown",
                capability_enabled=(
                    bool(slack_gate.runtime_enabled) if slack_gate is not None else False
                ),
                decision_mode=slack_gate.decision_mode if slack_gate is not None else "ask",
                credential_env=SLACK_TOKEN_ENV,
                credential_configured=bool(os.environ.get(SLACK_TOKEN_ENV, "").strip()),
                egress_host=SLACK_HOST,
                egress_allowed=SLACK_HOST in allowlist,
                actions=("read_channel_info", "read_channel_history"),
                kind="read_only",
            )
        )
        return ConnectionsView(
            connectors=tuple(connectors),
            connector_egress_allowlist_configured=bool(
                os.environ.get("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", "").strip()
            ),
        )

    @staticmethod
    def _current_model(
        registry: ModelProfileRegistry, state: ModelSessionState | None
    ) -> str | None:
        """The concrete model the current selection binds, or None."""
        if state is None:
            return None
        try:
            profile = registry.resolve_profile_id(state.profile_id)
        except Exception:  # noqa: BLE001 — a stale selection must not break the read
            return None
        effective = state.model or profile.model
        if not effective or "<" in effective:
            return None
        return effective

    def set_model_fallback_sequence(
        self: DashboardService, profile_ids: list[str], acting_principal_id: str | None
    ) -> ControlResult:
        """Persist the user-owned ordered fallback sequence (human gate-manager only).

        Only known, non-test model profile ids are accepted; unknown ids fail
        closed with ``unknown_profile:<id>``. Authorization mirrors the capability
        control plane: the acting principal must be a human ``runtime_gate_manager``.
        Persisting the ordered list does not itself enable any provider — each
        candidate is still gated by provider policy when a turn actually falls back.
        """
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if not self.control._is_gate_manager(principal):  # noqa: SLF001
            return ControlResult(ok=False, reason_code="not_authorized_gate_manager")
        registry = ModelProfileRegistry.load()
        known: dict[str, Any] = {p.profile_id: p for p in registry.list_profiles()}
        cleaned: list[str] = []
        for profile_id in profile_ids:
            profile = known.get(profile_id)
            if profile is None:
                return ControlResult(ok=False, reason_code=f"unknown_profile:{profile_id}")
            if bool(profile.raw.get("test_only", False)):
                return ControlResult(ok=False, reason_code=f"test_profile_not_allowed:{profile_id}")
            if profile_id not in cleaned:
                cleaned.append(profile_id)
        if self.store.get_account(principal.principal_id) is not None:
            self.store.save_principal_model_fallback_sequence(principal.principal_id, cleaned)
        else:
            self.store.save_model_fallback_sequence(TERMINAL_MODEL_SESSION_ID, cleaned)
        return ControlResult(ok=True, data={"fallback_sequence": cleaned})

    def set_model_advisor(
        self: DashboardService, profile_id: str | None, acting_principal_id: str | None
    ) -> ControlResult:
        """Persist the user-owned advisor model profile (human gate-manager only).

        ``None``/empty clears the advisor. Only known, non-test profiles with a
        concrete model are accepted — placeholder-``<model>`` profiles fail
        closed (pick a concrete model for the profile first). Persisting the
        advisor never enables anything: the consult path is gated by
        ``advisor_model_runtime``, its decision mode, and provider policy.
        """
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if not self.control._is_gate_manager(principal):  # noqa: SLF001
            return ControlResult(ok=False, reason_code="not_authorized_gate_manager")
        cleaned = (profile_id or "").strip()
        if not cleaned:
            if self.store.get_account(principal.principal_id) is not None:
                self.store.save_principal_model_advisor(principal.principal_id, None)
            else:
                self.store.save_model_advisor(TERMINAL_MODEL_SESSION_ID, None)
            return ControlResult(ok=True, data={"advisor_profile_id": None})
        registry = ModelProfileRegistry.load()
        try:
            profile = registry.resolve_profile_id(cleaned)
        except Exception:  # noqa: BLE001 — unknown profile fails closed
            return ControlResult(ok=False, reason_code=f"unknown_profile:{cleaned}")
        if bool(profile.raw.get("test_only", False)):
            return ControlResult(ok=False, reason_code=f"test_profile_not_allowed:{cleaned}")
        state = (
            self.store.load_principal_model_state(principal.principal_id)
            if self.store.get_account(principal.principal_id) is not None
            else self.store.load_model_session_state(TERMINAL_MODEL_SESSION_ID)
        )
        effective_model = profile.model
        if state is not None and state.profile_id == profile.profile_id and state.model:
            effective_model = state.model
        if not effective_model or "<" in effective_model:
            return ControlResult(ok=False, reason_code=f"model_required_for_profile:{cleaned}")
        if self.store.get_account(principal.principal_id) is not None:
            self.store.save_principal_model_advisor(principal.principal_id, profile.profile_id)
        else:
            self.store.save_model_advisor(TERMINAL_MODEL_SESSION_ID, profile.profile_id)
        return ControlResult(ok=True, data={"advisor_profile_id": profile.profile_id})


    @staticmethod
    def _profile_is_billable(profile: Any) -> bool:
        """True only for off-machine providers Raiker authenticates with a key.

        A local runtime costs nothing per token however many tokens it burns, so
        attaching money to it would be a lie. An API key alone is not enough to
        decide: LM Studio reads `LM_API_TOKEN` yet runs on `127.0.0.1` and bills
        nothing. Both conditions must hold — the endpoint leaves this machine
        **and** a credential authenticates it.
        """
        raw = getattr(profile, "raw", {}) or {}
        endpoint_kind = str(raw.get("endpoint_kind", ""))
        off_machine = endpoint_kind in {"remote_hosted", "private_network"}
        # The shipped profiles do not persist this runtime classification. Their
        # policy metadata is still authoritative: a non-local provider that
        # requires network access is off-machine even before its first request.
        if not off_machine:
            off_machine = bool(
                getattr(profile, "requires_network", raw.get("requires_network", False))
            ) and not bool(getattr(profile, "local_only", raw.get("local_only", False)))
        if not off_machine:
            return False
        keyed = bool(raw.get("requires_api_key")) or bool(raw.get("api_key_env"))
        return keyed

    def _resolve_facts(self: DashboardService, profile: Any, model: str, principal_id: str | None) -> Any:
        """Merge owner override, cached provider report, and shipped config.

        BUG-21 — the normalised price registry is consulted first, because it is
        the only source that carries effective dating and the cache-write and
        cache-read components. Its answer is exact-model-id only, so a model the
        registry has never seen falls through to the pre-registry resolution
        below rather than borrowing a sibling's rate.
        """
        from raiker.models.price_registry import PriceRegistry
        from raiker.models.pricing import resolve_model_facts

        facts_store = ModelFactsStore(self.store)
        registered = (
            PriceRegistry(self.store).resolve(principal_id, profile.provider, model)
            if principal_id and model
            else None
        )
        owner_price = (
            facts_store.owner_price(principal_id, profile.provider, model)
            if principal_id and model
            else None
        )
        provider_facts = (
            facts_store.provider_facts(principal_id, profile.provider, model)
            if principal_id and model
            else None
        )
        raw = getattr(profile, "raw", {}) or {}
        configured_window = raw.get("context_window_tokens")
        if registered is not None:
            # A registered rate outranks all three legacy sources: it *is* one
            # of them, resolved by the same precedence, but dated and complete.
            owner_price = registered.rates.to_price(registered.source, registered.as_of)
        resolved = resolve_model_facts(
            provider=profile.provider,
            model=model,
            owner_price=owner_price,
            provider_facts=provider_facts,
            config_pricing=raw.get("pricing"),
            config_context_window=(
                configured_window
                if isinstance(configured_window, int) and not isinstance(configured_window, bool)
                else None
            ),
        )
        owner_capacity = (
            facts_store.owner_context_capacity(principal_id, profile.provider, model)
            if principal_id and model
            else None
        )
        if owner_capacity is not None:
            resolved = replace(
                resolved,
                context_window_tokens=owner_capacity[0],
                context_window_source="owner",
            )
        return resolved

    def get_context_usage(
        self: DashboardService, session_id: str, acting_principal_id: str | None = None
    ) -> ContextUsageView:
        """Usage and cost for one conversation, plus the provider's all-time total.

        Reads only what the ledger recorded. A session with no completed turn
        reports `usage_source="unavailable"`, which is the browser's signal to
        show its own clearly-labelled transcript estimate instead of pretending
        this is provider-reported.
        """
        from raiker.runtime.model_usage import ModelUsageLedger, sum_totals

        registry = ModelProfileRegistry.load()
        state = (
            self.store.load_principal_model_state(acting_principal_id)
            if acting_principal_id and self.store.get_account(acting_principal_id) is not None
            else self.store.load_model_session_state(TERMINAL_MODEL_SESSION_ID)
        )
        profile_id = state.profile_id if state is not None else None
        profile = None
        if profile_id:
            try:
                profile = registry.resolve_profile_id(profile_id)
            except Exception:  # noqa: BLE001 — an unknown selection is simply unpriced
                profile = None

        ledger = ModelUsageLedger(self.store)
        principal = acting_principal_id or ""
        session_rows = ledger.session_usage(principal, session_id) if principal else []
        session_totals = sum_totals(session_rows)

        # The model that actually served this conversation beats the currently
        # selected one: re-pricing history at a newly picked model's rate would
        # misreport what the user already spent.
        model = (
            session_rows[-1].model
            if session_rows
            else (
                (state.model if state is not None and state.model else None)
                or (profile.model if profile is not None else None)
            )
        )
        if model in (None, "", "<model>"):
            model = None

        billable = bool(profile is not None and self._profile_is_billable(profile))
        facts = (
            self._resolve_facts(profile, model, acting_principal_id)
            if profile is not None and model
            else None
        )

        def _priced_total(rows: list[Any]) -> Decimal | None:
            """Sum cost by pricing each model at its own rate.

            Summing tokens first and applying one model's rate would charge a
            cheap model's tokens at an expensive model's price — Claude models
            differ by roughly 15x, so a mixed history would be badly wrong.
            Returns None when no row could be priced at all.
            """
            total = Decimal(0)
            priced_any = False
            for row in rows:
                row_facts = self._resolve_facts(profile, row.model, acting_principal_id)
                row_cost = row.totals.cost(row_facts)
                if row_cost is None:
                    continue
                priced_any = True
                total += row_cost
            return total if priced_any else None

        session_cost = _priced_total(session_rows) if billable and profile is not None else None
        provider_total: Decimal | None = None
        if billable and profile is not None and principal:
            matching = [
                row for row in ledger.provider_usage(principal) if row.provider == profile.provider
            ]
            provider_total = _priced_total(matching) if matching else None

        price = facts.price if facts is not None else None
        # BUG-21 — a billable conversation with no exact rate says so. Silence
        # here reads as "free", which is the one thing it certainly is not.
        price_unknown = bool(billable and price is None)
        registered = None
        if profile is not None and model and acting_principal_id:
            from raiker.models.price_registry import PriceRegistry

            registered = PriceRegistry(self.store).resolve(
                acting_principal_id, profile.provider, model
            )
        latest_compaction = None
        if acting_principal_id:
            from raiker.runtime.conversation_compaction import ContextCompactionStore

            compacted = ContextCompactionStore(self.store).latest(acting_principal_id, session_id)
            if compacted is not None:
                latest_compaction = {
                    "status": compacted.status,
                    "created_at": compacted.created_at,
                    "source_turn_count": compacted.source_turn_count,
                    "estimated_input_tokens_before": (compacted.estimated_input_tokens_before),
                    "estimated_summary_tokens": compacted.estimated_summary_tokens,
                    "reason_code": compacted.reason_code,
                }
        return ContextUsageView(
            session_id=session_id,
            profile_id=profile.profile_id if profile is not None else None,
            provider=profile.provider if profile is not None else None,
            model=model,
            used_tokens=session_rows[-1].totals.input_tokens if session_rows else None,
            context_window_tokens=facts.context_window_tokens if facts is not None else None,
            context_window_source=facts.context_window_source if facts is not None else None,
            usage_source="provider" if session_rows else "unavailable",
            billable=billable,
            session_cost=str(session_cost) if session_cost is not None else None,
            provider_total_cost=str(provider_total) if provider_total is not None else None,
            currency=price.currency if price is not None else None,
            price_source=price.source if price is not None else None,
            price_as_of=price.as_of if price is not None else None,
            session_turns=session_totals.turns,
            session_input_tokens=session_totals.input_tokens,
            session_output_tokens=session_totals.output_tokens,
            price_input_per_mtok=str(price.input_per_mtok) if price is not None else None,
            price_output_per_mtok=str(price.output_per_mtok) if price is not None else None,
            price_cache_write_per_mtok=(
                str(price.cache_write_per_mtok)
                if price is not None and price.cache_write_per_mtok is not None
                else None
            ),
            price_cache_read_per_mtok=(
                str(price.cache_read_per_mtok)
                if price is not None and price.cache_read_per_mtok is not None
                else None
            ),
            price_effective_from=registered.effective_from if registered is not None else None,
            price_unknown=price_unknown,
            latest_compaction=latest_compaction,
            # Backlog #16 — the built-in half of the catalogue. MCP tools are
            # projected per turn from what the owner has connected and are not
            # counted here: this is the fixed cost the deferral removes, and a
            # figure that changed with a connection would not answer that.
            tools_projected=len(ALWAYS_PROJECTED) + 1,
            tools_deferred=len(DEFERRABLE_TOOL_NAMES),
        )


    def list_model_pricing(
        self: DashboardService, acting_principal_id: str | None, *, history_limit: int = 10
    ) -> ModelPricingView:
        """Every priced model this owner has, with source, dates, and history.

        The list is the union of what the registry holds and what the shipped
        profiles document, so a model whose price has never been synchronised
        still appears — with its documented rate and its ``as_of`` date — rather
        than being invisible until a network call succeeds.
        """
        from raiker.models.price_registry import PriceRegistry
        from raiker.models.price_sync import PriceSynchroniser

        owner = acting_principal_id or ""
        registry = PriceRegistry(self.store)
        synchroniser = PriceSynchroniser(self.store, registry)
        if not owner:
            return ModelPricingView(entries=(), sync=(), can_override=False)

        # Seed the reviewed-documentation adapter for anything not yet recorded,
        # so first open is populated without pretending a provider was called.
        self._sync_documented_prices(owner, force=False)

        profile_registry = ModelProfileRegistry.load()
        profile_by_model: dict[tuple[str, str], str] = {}
        review_by_model: dict[tuple[str, str], tuple[str, str, str]] = {}
        for profile in profile_registry.list_profiles():
            if bool(profile.raw.get("test_only", False)):
                continue
            pricing_block = profile.raw.get("pricing")
            models = pricing_block.get("models") if isinstance(pricing_block, dict) else None
            if isinstance(models, dict) and isinstance(pricing_block, dict):
                for model_id in models:
                    if isinstance(model_id, str):
                        profile_by_model.setdefault(
                            (profile.provider, model_id), profile.profile_id
                        )
                        reviewed_at = pricing_block.get("reviewed_at")
                        interval = pricing_block.get("review_interval_days", 92)
                        if isinstance(reviewed_at, str) and reviewed_at:
                            try:
                                reviewed = datetime.fromisoformat(reviewed_at).replace(tzinfo=UTC)
                                due = reviewed + timedelta(days=max(int(interval), 1))
                                review_by_model[(profile.provider, model_id)] = (
                                    reviewed_at,
                                    due.date().isoformat(),
                                    "overdue" if datetime.now(UTC) > due else "current",
                                )
                            except (TypeError, ValueError):
                                review_by_model[(profile.provider, model_id)] = (
                                    reviewed_at,
                                    "",
                                    "invalid",
                                )
            if isinstance(profile.model, str) and profile.model not in ("", "<model>"):
                profile_by_model.setdefault((profile.provider, profile.model), profile.profile_id)

        entries: list[ModelPricingEntryView] = []
        for provider, model in registry.models(owner):
            current = registry.resolve(owner, provider, model)
            if current is None:
                continue
            history = registry.history(owner, provider, model, limit=history_limit)
            entries.append(
                # A documented rate's human review is a different clock from
                # provider synchronisation. Overrides and provider catalogue
                # rows have no shipped-document review to claim.
                ModelPricingEntryView(
                    provider=provider,
                    model=model,
                    profile_id=profile_by_model.get((provider, model)),
                    source=current.source,
                    currency=current.rates.currency,
                    input_per_mtok=str(current.rates.input_per_mtok),
                    output_per_mtok=str(current.rates.output_per_mtok),
                    cache_write_per_mtok=(
                        None
                        if current.rates.cache_write_per_mtok is None
                        else str(current.rates.cache_write_per_mtok)
                    ),
                    cache_read_per_mtok=(
                        None
                        if current.rates.cache_read_per_mtok is None
                        else str(current.rates.cache_read_per_mtok)
                    ),
                    effective_from=current.effective_from,
                    as_of=current.as_of,
                    reviewed_at=(review_by_model.get((provider, model)) or (None, None, None))[0]
                    if current.source == "config"
                    else None,
                    review_due_at=(review_by_model.get((provider, model)) or (None, None, None))[1]
                    if current.source == "config"
                    else None,
                    review_status=(review_by_model.get((provider, model)) or (None, None, None))[2]
                    if current.source == "config"
                    else None,
                    recorded_at=current.recorded_at,
                    recorded_by=current.recorded_by,
                    reason=current.reason,
                    has_owner_override=any(row.source == "owner" for row in history),
                    history=tuple(row.to_dict() for row in history),
                )
            )

        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        can_override = principal is not None and self.control._is_gate_manager(principal)  # noqa: SLF001
        return ModelPricingView(
            entries=tuple(entries),
            sync=tuple(state.to_dict() for state in synchroniser.states(owner)),
            can_override=bool(can_override),
        )

    def _sync_documented_prices(self: DashboardService, owner_principal_id: str, *, force: bool) -> list[Any]:
        """Run the reviewed-documentation adapter for every shipped profile.

        ``force`` bypasses the 6–24 hour cadence for an explicit refresh. Without
        it a provider that is not yet due is skipped, which is what keeps opening
        the Models page from re-recording prices on every visit.
        """
        from raiker.models.price_sync import PriceSynchroniser

        synchroniser = PriceSynchroniser(self.store)
        blocks: dict[str, dict[str, Any]] = {}
        for profile in ModelProfileRegistry.load().list_profiles():
            if bool(profile.raw.get("test_only", False)):
                continue
            pricing_block = profile.raw.get("pricing")
            if not isinstance(pricing_block, dict):
                continue
            merged = blocks.setdefault(
                profile.provider,
                {
                    "currency": pricing_block.get("currency", "USD"),
                    "as_of": pricing_block.get("as_of"),
                    "models": {},
                },
            )
            models = pricing_block.get("models")
            if isinstance(models, dict):
                merged["models"].update(models)

        results = []
        for provider, block in sorted(blocks.items()):
            if not force and not synchroniser.due(owner_principal_id, provider):
                continue
            results.append(
                synchroniser.sync_from_documentation(owner_principal_id, provider, block)
            )
        return results

    def refresh_model_pricing(self: DashboardService, acting_principal_id: str | None) -> ControlResult:
        """Run the synchronisation now, on explicit demand.

        Only the reviewed adapters run here. A provider catalogue is contacted
        exclusively by the user-initiated model listing, which feeds the registry
        on its way past — this route never opens a connection of its own.
        """
        if not acting_principal_id:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        results = self._sync_documented_prices(acting_principal_id, force=True)
        return ControlResult(
            ok=True,
            data={
                "providers": [result.to_dict() for result in results],
                "changes_written": sum(result.changes_written for result in results),
            },
        )

    def model_capacity_status(self: DashboardService, acting_principal_id: str | None) -> ControlResult:
        if not acting_principal_id:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        models = self.get_models(acting_principal_id)
        facts_store = ModelFactsStore(self.store)
        entries: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for profile in (*models.profiles, *models.chat_profiles):
            key = (profile.profile_id, profile.provider, profile.model)
            if profile.model == "<model>" or key in seen:
                continue
            seen.add(key)
            entries.append(
                {
                    "profile_id": profile.profile_id,
                    "provider": profile.provider,
                    "model": profile.model,
                    "endpoint_identity": f"{profile.profile_id}:{profile.endpoint_kind}",
                    "context_window_tokens": profile.context_window_tokens,
                    "source": profile.context_window_source,
                    "history": facts_store.capacity_history(
                        acting_principal_id, profile.provider, profile.model
                    ),
                }
            )
        sync = facts_store.capacity_refresh_state(acting_principal_id)
        registry = ModelProfileRegistry.load()
        local_ids = [
            profile.profile_id
            for profile in registry.list_profiles()
            if profile.local_only and not bool(profile.raw.get("test_only", False))
        ]
        due = any(
            facts_store.capacity_refresh_due(acting_principal_id, profile_id)
            for profile_id in local_ids
        )
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        return ControlResult(
            ok=True,
            data={
                "entries": entries,
                "sync": sync,
                "refresh_due": due,
                "cadence_hours": 24,
                "can_override": bool(principal and self.control._is_gate_manager(principal)),  # noqa: SLF001
            },
        )

    async def refresh_local_model_capacities(
        self: DashboardService, acting_principal_id: str | None, *, force: bool = False
    ) -> ControlResult:
        if not acting_principal_id:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        registry = ModelProfileRegistry.load()
        facts_store = ModelFactsStore(self.store)
        refreshed: list[dict[str, Any]] = []
        for profile in registry.list_profiles():
            if not profile.local_only or bool(profile.raw.get("test_only", False)):
                continue
            if not force and not facts_store.capacity_refresh_due(
                acting_principal_id, profile.profile_id
            ):
                continue
            view = await self.list_provider_models(profile.profile_id, acting_principal_id)
            status_value = view.status if view is not None else "unavailable"
            reason_code = view.reason_code if view is not None else "unknown_model_profile"
            facts_store.record_capacity_refresh(
                acting_principal_id, profile.profile_id, status_value, reason_code
            )
            refreshed.append(
                {
                    "profile_id": profile.profile_id,
                    "status": status_value,
                    "reason_code": reason_code,
                }
            )
        return ControlResult(ok=True, data={"profiles": refreshed})

    def set_model_context_capacity(
        self: DashboardService,
        profile_id: str,
        model: str,
        tokens: int | None,
        reason: str,
        acting_principal_id: str | None,
    ) -> ControlResult:
        if not acting_principal_id:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None or not self.control._is_gate_manager(principal):  # noqa: SLF001
            return ControlResult(ok=False, reason_code="not_authorized_gate_manager")
        if not model or model == "<model>":
            return ControlResult(ok=False, reason_code="model_not_specified")
        try:
            profile = ModelProfileRegistry.load().resolve_profile_id(profile_id)
        except Exception:
            return ControlResult(ok=False, reason_code="unknown_model_profile")
        try:
            ModelFactsStore(self.store).set_owner_context_capacity(
                acting_principal_id,
                profile.provider,
                model,
                tokens=tokens,
                endpoint_identity=f"{profile.profile_id}:{profile.raw.get('endpoint_kind', 'unknown')}",
                reason=redact_secret_like_text(reason.strip()),
                recorded_by=acting_principal_id,
            )
        except ValueError as exc:
            return ControlResult(ok=False, reason_code=str(exc))
        return ControlResult(
            ok=True, data={"profile_id": profile_id, "model": model, "tokens": tokens}
        )

    def set_model_price(
        self: DashboardService,
        profile_id: str,
        model: str,
        *,
        input_per_mtok: str | None,
        output_per_mtok: str | None,
        currency: str = "USD",
        acting_principal_id: str | None,
        cache_write_per_mtok: str | None = None,
        cache_read_per_mtok: str | None = None,
        effective_from: str | None = None,
        reason: str | None = None,
    ) -> ControlResult:
        """Set or clear one model's administrator price override (BUG-21).

        Both input and output absent clears the override, returning the model to
        its provider-published or documented rate. An override is administrator
        work rather than a personal preference — it changes what every figure in
        the product claims a turn cost — so it requires the gate-manager role and
        is recorded in the registry with who set it and why. It is still scoped
        to the acting principal, so it can never change another account's costs.
        """
        if not acting_principal_id:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if not self.control._is_gate_manager(principal):  # noqa: SLF001
            return ControlResult(ok=False, reason_code="not_authorized_gate_manager")
        if not model or model == "<model>":
            return ControlResult(ok=False, reason_code="model_not_specified")
        registry = ModelProfileRegistry.load()
        try:
            profile = registry.resolve_profile_id(profile_id)
        except Exception:  # noqa: BLE001 — unknown profile fails closed
            return ControlResult(ok=False, reason_code="unknown_model_profile")

        from raiker.models.price_registry import PriceRates, PriceRegistry, PriceRegistryError

        price_registry = PriceRegistry(self.store)
        facts_store = ModelFactsStore(self.store)
        if input_per_mtok is None and output_per_mtok is None:
            facts_store.clear_owner_price(acting_principal_id, profile.provider, model)
            price_registry.clear_source(acting_principal_id, profile.provider, model, "owner")
            self._record_price_audit(
                acting_principal_id, profile.provider, model, "cleared", reason
            )
            return ControlResult(ok=True, data={"model": model, "cleared": True})

        def _rate(value: str | None) -> Decimal | None:
            if value is None or str(value).strip() == "":
                return None
            parsed = Decimal(str(value))
            if not parsed.is_finite() or parsed < 0:
                raise ValueError("model_price_invalid")
            return parsed

        try:
            price_in = _rate(input_per_mtok)
            price_out = _rate(output_per_mtok)
            cache_write = _rate(cache_write_per_mtok)
            cache_read = _rate(cache_read_per_mtok)
        except Exception:  # noqa: BLE001 — a malformed price is rejected, not guessed
            return ControlResult(ok=False, reason_code="model_price_invalid")
        if price_in is None or price_out is None:
            return ControlResult(ok=False, reason_code="model_price_invalid")

        facts_store.set_owner_price(
            acting_principal_id,
            profile.provider,
            model,
            input_per_mtok=price_in,
            output_per_mtok=price_out,
            currency=currency or "USD",
        )
        try:
            price_registry.record(
                acting_principal_id,
                profile.provider,
                model,
                PriceRates(
                    input_per_mtok=price_in,
                    output_per_mtok=price_out,
                    cache_write_per_mtok=cache_write,
                    cache_read_per_mtok=cache_read,
                    currency=currency or "USD",
                ),
                source="owner",
                effective_from=effective_from,
                as_of=effective_from,
                recorded_by=acting_principal_id,
                reason=reason or "Administrator price override",
            )
        except PriceRegistryError as exc:
            return ControlResult(ok=False, reason_code=str(exc))
        self._record_price_audit(acting_principal_id, profile.provider, model, "set", reason)
        return ControlResult(
            ok=True,
            data={
                "model": model,
                "input_per_mtok": str(price_in),
                "output_per_mtok": str(price_out),
                "cache_write_per_mtok": None if cache_write is None else str(cache_write),
                "cache_read_per_mtok": None if cache_read is None else str(cache_read),
                "currency": currency or "USD",
            },
        )

    def _record_price_audit(
        self: DashboardService,
        acting_principal_id: str,
        provider: str,
        model: str,
        action: str,
        reason: str | None,
    ) -> None:
        """Write the override to the governed event log. Never fails the write."""
        from raiker.contracts.models import AgentEvent

        with contextlib.suppress(Exception):
            EventLogWriter(self.store).append(
                AgentEvent(
                    event_id=new_id("evt_"),
                    timestamp=utc_now(),
                    session_id=TERMINAL_MODEL_SESSION_ID,
                    turn_id=None,
                    event_type=(
                        "model_price_override_cleared"
                        if action == "cleared"
                        else "model_price_override_recorded"
                    ),
                    actor=acting_principal_id,
                    payload={
                        "provider": provider,
                        "model": model,
                        "reason": redact_secret_like_text(reason or ""),
                    },
                )
            )

    async def list_provider_models(
        self: DashboardService, profile_id: str, acting_principal_id: str | None = None
    ) -> ProviderModelListView | None:
        """List the models a provider serves, on explicit user demand.

        Returns None for unknown/test-only profiles (the route 404s). This is the
        only web read that touches the network, and only because the user asked
        for this provider's catalogue; provider policy (gates, egress allowlist,
        API key) is enforced by the provider factory exactly as for a chat call,
        so a policy-denied provider is never contacted. On any failure the list
        is empty with an honest status — model names are never fabricated.
        """
        registry = ModelProfileRegistry.load()
        try:
            profile = registry.resolve_profile_id(profile_id)
        except Exception:  # noqa: BLE001 — unknown profile fails closed
            return None
        if bool(profile.raw.get("test_only", False)):
            return None
        from raiker.models.connections import get_model_connection

        router = ModelRouter(
            registry,
            runtime_policy=provider_runtime_policy_from_gates(self.store, acting_principal_id),
            connection_resolver=lambda current_profile_id: (
                get_model_connection(self.store, acting_principal_id or "", current_profile_id)
                if acting_principal_id
                else None
            ),
        )
        def _remembered(status: str, reason_code: str | None) -> ProviderModelListView:
            """The failure, plus whatever this provider last published.

            A provider that is briefly unreachable used to make
            its whole catalogue vanish from every picker, because the only copy
            was the one in flight. The failure is still reported exactly as it
            happened; the models beside it are the remembered ones, flagged as
            remembered so nothing presents them as current.

            A policy denial carries no models at all: the owner has not been
            granted this provider *now*, and offering a remembered catalogue for
            it would be projecting an authority the gate is refusing.
            """
            if status == "policy_denied" or not acting_principal_id:
                return ProviderModelListView(
                    profile_id=profile.profile_id,
                    provider=profile.provider,
                    status=status,
                    reason_code=reason_code,
                    models=(),
                )
            known: list[str] = []
            listed_at: str | None = None
            with contextlib.suppress(Exception):  # remembering never fails a listing
                known = self.store.list_provider_catalogue(
                    acting_principal_id, profile.profile_id
                )
                listed_at = self.store.provider_catalogue_listed_at(
                    acting_principal_id, profile.profile_id
                )
            return ProviderModelListView(
                profile_id=profile.profile_id,
                provider=profile.provider,
                status=status,
                reason_code=reason_code,
                models=tuple(known),
                remembered=bool(known),
                listed_at=listed_at,
            )

        try:
            models = await router.alist_models_for_profile(profile)
        except ProviderPolicyError as exc:
            return _remembered("policy_denied", safe_error(str(exc)))
        except ModelProviderError as exc:
            # BUG-257 — every provider failure used to come back as
            # `provider_unreachable`, which the Models page states as "could not
            # be reached. Check the credential and this device's network
            # access." A provider that answered 401 was reached perfectly well,
            # and sending the owner to check their network for a key the
            # provider rejected is the wrong instruction, not merely a vague
            # one. The error classes already distinguish these; only this branch
            # was flattening them.
            if "unsupported" in str(exc):
                return _remembered("unsupported", "model_listing_unsupported")
            return _remembered("unavailable", provider_error_code(exc))
        except Exception as exc:  # noqa: BLE001 — network/parse failures fail closed
            return _remembered("unavailable", safe_error(type(exc).__name__))
        # A successful listing is the one moment Raiker legitimately hears from
        # the provider, so whatever it published about its models (Anthropic's
        # context window, OpenRouter's prices) is cached here for the meter and
        # the cost rows to read without a second round trip.
        if acting_principal_id:
            # The catalogue itself, written down. This is the
            # only moment Raiker legitimately knows what a provider serves, and
            # until now that knowledge lived exactly as long as the response.
            with contextlib.suppress(Exception):  # remembering never fails a listing
                self.store.save_provider_catalogue(
                    acting_principal_id, profile.profile_id, [m.id for m in models]
                )
            with contextlib.suppress(Exception):  # caching never fails a listing
                ModelFactsStore(self.store).save_provider_facts(
                    acting_principal_id, profile.provider, list(models)
                )
            # BUG-21 — the same listing is the provider's own price feed, so it
            # also lands in the effective-dated registry. Recording is idempotent:
            # a catalogue whose rates have not moved writes no history row.
            with contextlib.suppress(Exception):
                from raiker.models.price_sync import PriceSynchroniser

                PriceSynchroniser(self.store).sync_from_catalogue(
                    acting_principal_id, profile.provider, list(models)
                )
        return ProviderModelListView(
            profile_id=profile.profile_id,
            provider=profile.provider,
            status="available",
            reason_code=None,
            models=tuple(m.id for m in models),
        )

    async def refresh_connected_provider_catalogues(
        self: DashboardService, acting_principal_id: str, profile_ids: list[str] | None = None
    ) -> tuple[ProviderCatalogueRefreshView, ...]:
        """Refresh local and vault-connected providers through normal policy gates.

        This is deliberately owner-triggered.  Local runtimes have no credential
        marker, so they are eligible alongside profiles whose connection values
        are stored in the vault; every actual listing still passes through
        :meth:`list_provider_models` and therefore cannot bypass policy.
        """
        from raiker.models.connections import list_model_connections

        registry = ModelProfileRegistry.load()
        eligible = {
            profile.profile_id
            for profile in registry.list_profiles()
            if profile.local_only and not bool(profile.raw.get("test_only", False))
        }
        eligible.update(list_model_connections(self.store, acting_principal_id))
        requested = list(dict.fromkeys(profile_ids or sorted(eligible)))
        if any(profile_id not in eligible for profile_id in requested):
            raise ValueError("model_catalogue_profile_not_connected")

        outcomes: list[ProviderCatalogueRefreshView] = []
        for profile_id in requested:
            listed = await self.list_provider_models(profile_id, acting_principal_id)
            if listed is None:  # defensive: registry and eligibility came from one snapshot
                continue
            outcomes.append(
                ProviderCatalogueRefreshView(
                    profile_id=listed.profile_id,
                    provider=listed.provider,
                    status=listed.status,
                    reason_code=listed.reason_code,
                    model_count=len(listed.models),
                )
            )
        return tuple(outcomes)

    #: How many models one provider may keep offered at once. High enough for
    #: any real catalogue an owner works across, low enough that a router with
    #: four hundred models cannot be poured into every picker in the app.
    MAX_AVAILABLE_MODELS_PER_PROFILE = 24

    def set_available_models(
        self: DashboardService, profile_id: str, models: list[str], acting_principal_id: str
    ) -> ControlResult:
        """Choose which of a provider's models stay offered in every picker.

        Selecting a default used to be the only way a model entered the pickers,
        so a provider serving six could offer one. This is the owner saying
        which of them they actually work with; the default is a separate,
        unchanged decision, and the model it names is always kept.
        """
        registry = ModelProfileRegistry.load()
        try:
            profile = registry.resolve_profile_id(profile_id)
        except Exception:  # noqa: BLE001 — unknown profile fails closed
            return ControlResult(ok=False, reason_code="unknown_model_profile")
        if len(models) > self.MAX_AVAILABLE_MODELS_PER_PROFILE:
            return ControlResult(ok=False, reason_code="too_many_available_models")
        if any(not isinstance(model, str) or len(model) > 200 for model in models):
            return ControlResult(ok=False, reason_code="invalid_model_id")
        state = self.store.load_principal_model_state(acting_principal_id)
        keep = (
            (state.model or profile.model)
            if state is not None and state.profile_id == profile_id
            else None
        )
        stored = self.store.set_configured_models(
            acting_principal_id,
            profile_id,
            list(models),
            keep=keep if keep and "<" not in keep else None,
        )
        self._append_model_event(
            "model_available_set_changed",
            {"profile_id": profile_id, "provider": profile.provider, "count": len(stored)},
        )
        return ControlResult(ok=True, data={"profile_id": profile_id, "models": stored})

    async def set_model_selection(
        self: DashboardService, profile_id: str, model: str | None, acting_principal_id: str | None
    ) -> ControlResult:
        """Persist the operator's model selection (human gate-manager only).

        Mirrors the CLI ``/model use``: the effective profile (concrete model +
        endpoint + provider policy) is validated by the provider factory without
        connecting, so a hosted provider whose gate/egress/key is missing fails
        closed here instead of at turn time. Placeholder profiles require an
        explicit concrete model.
        """
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if not self.control._is_gate_manager(principal):  # noqa: SLF001
            return ControlResult(ok=False, reason_code="not_authorized_gate_manager")
        registry = ModelProfileRegistry.load()
        try:
            profile = registry.resolve_profile_id(profile_id)
        except Exception:  # noqa: BLE001 — unknown profile fails closed
            return ControlResult(ok=False, reason_code=f"unknown_profile:{profile_id}")
        if bool(profile.raw.get("test_only", False)):
            return ControlResult(ok=False, reason_code=f"test_profile_not_allowed:{profile_id}")
        resolved_model = (model or "").strip() or profile.model
        if not resolved_model or "<" in resolved_model:
            return ControlResult(ok=False, reason_code=f"model_required_for_profile:{profile_id}")
        effective = (
            profile
            if resolved_model == profile.model
            else profile_with_model(profile, resolved_model)
        )
        try:
            from raiker.models.connections import get_model_connection

            # GCR-02 — the question is whether `effective` would run, so ask it
            # without building anything. The provider this used to construct was
            # closed by hand below, through a `getattr(..., "aclose")` that had to
            # exist because the call returned a live client nobody wanted.
            ModelProviderFactory(
                policy=provider_runtime_policy_from_gates(self.store, principal.principal_id),
                connection=get_model_connection(
                    self.store, principal.principal_id, profile.profile_id
                ),
            ).validate(effective)
        except Exception as exc:  # noqa: BLE001 — provider policy failures fail closed
            self._append_model_event(
                "model_provider_rejected_by_policy",
                {
                    "profile_id": profile.profile_id,
                    "provider": profile.provider,
                    "model": resolved_model,
                    "reason": safe_error(str(exc)),
                },
            )
            return ControlResult(ok=False, reason_code=safe_error(str(exc)))
        state = ModelSessionState(
            session_id=principal.principal_id
            if self.store.get_account(principal.principal_id) is not None
            else TERMINAL_MODEL_SESSION_ID,
            profile_id=profile.profile_id,
            model=(None if resolved_model == profile.model else resolved_model),
        )
        self.store.save_configured_model(principal.principal_id, profile.profile_id, resolved_model)
        if self.store.get_account(principal.principal_id) is not None:
            self.store.save_principal_model_state(principal.principal_id, state)
        else:
            self.store.save_model_session_state(state)
        self.store.invalidate_model_readiness(
            principal.principal_id,
            profile.profile_id,
            reason_code="model_selection_changed",
        )
        self._append_model_event(
            "model_profile_selected",
            {
                "profile_id": profile.profile_id,
                "provider": profile.provider,
                "model": profile.model,
                "endpoint_kind": profile.raw.get("endpoint_kind", "unknown"),
                "resolved_model": resolved_model,
            },
        )
        return ControlResult(
            ok=True, data={"profile_id": profile.profile_id, "model": resolved_model}
        )

    def _append_model_event(self: DashboardService, event_type: str, payload: dict[str, Any]) -> None:
        from raiker.contracts.models import ClientMetadata
        from raiker.events.types import make_event
        from raiker.events.writer import EventLogWriter

        EventLogWriter(self.store).append(
            make_event(
                session_id=TERMINAL_MODEL_SESSION_ID,
                turn_id=None,
                event_type=event_type,
                actor="web_ui",
                payload=payload,
                client=ClientMetadata(type="web_ui", name="raiker-web", version=raiker_version()),
            )
        )

    @staticmethod
    def _runtime_gate_for_profile(endpoint_kind: str) -> str | None:
        if endpoint_kind == "remote_hosted":
            return HOSTED_MODEL_GATE
        if endpoint_kind == "private_network":
            return PRIVATE_NETWORK_MODEL_GATE
        return None

    def get_diagnostics(self: DashboardService, acting_principal_id: str | None = None) -> DiagnosticsView:
        readiness = self.control.get_runtime_readiness(acting_principal_id)
        readiness_summary = dict(readiness.summary)
        checkpoint_health = self.store.get_checkpoint_capture_health()
        if checkpoint_health is not None:
            checkpoint_health["ok"] = bool(checkpoint_health["ok"])
            readiness_summary["checkpoint_capture"] = checkpoint_health
        disabled = tuple(g.capability for g in readiness.gates if g.state in _DISABLED_STATES)
        counts = {
            "sessions": len(self.store.list_sessions(limit=1000)),
            "events": self.store.count_events(),
            "checkpoints": self.store.count_checkpoints(),
            "tasks": self.store.count_tasks(),
        }
        models = self.get_models(acting_principal_id)
        provider_health = self._provider_health(models)
        missing_config = self._missing_config(readiness, models)
        return DiagnosticsView(
            runtime_mode=readiness.mode.mode_name,
            production_ready_local_single_user_runtime=bool(
                readiness.summary.get("production_ready_local_single_user_runtime", False)
            ),
            summary=readiness_summary,
            disabled_capabilities=disabled,
            counts=counts,
            readiness=readiness_summary,
            missing_config=missing_config,
            provider_health=provider_health,
            background_workers=tuple(self.store.list_background_worker_health()),
            model_profile_source=resolve_builtin_config(
                "config/model-profiles.json"
            ).as_dict(),
        )

    @staticmethod
    def _provider_health(models: ModelsView) -> tuple[ProviderHealthView, ...]:
        """Configuration-derived provider status. Never probes the network on a read, and never
        fabricates reachability — reachability is checked on demand via the CLI."""
        return tuple(
            ProviderHealthView(
                profile_id=p.profile_id,
                provider=p.provider,
                model=p.model,
                endpoint_kind=p.endpoint_kind,
                local_only=p.local_only,
                requires_network=p.requires_network,
                selected=p.selected,
                status="selected" if p.selected else "configured",
                detail=(
                    "local provider; reachability not probed here"
                    if p.local_only
                    else "remote/networked provider; reachability not probed here"
                ),
            )
            for p in models.profiles
        )

    @staticmethod
    def _missing_config(readiness: Any, models: ModelsView) -> tuple[str, ...]:
        """Human-readable configuration gaps derived from stored readiness — no shell, no probing."""
        s = readiness.summary
        gaps: list[str] = []
        if not s.get("owner_bootstrapped", False):
            gaps.append("No owner principal is bootstrapped (run `raiker` → `/bootstrap-owner`).")
        if not s.get("acting_principal_available", False):
            gaps.append("No acting principal is available.")
        if not s.get("runtime_gate_manager_available", False):
            gaps.append("No runtime_gate_manager principal is available to change gates.")
        if readiness.mode.status != "active":
            gaps.append("No runtime mode is active.")
        if models.current_profile_id is None:
            gaps.append("No model profile is selected.")
        return tuple(gaps)
