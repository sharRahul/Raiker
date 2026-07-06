from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from raiker.phase_gates import CapabilityState
from raiker.runtime.authority.models import Principal, PrincipalType

ACTIVATION_BLOCKED_NO_EXECUTOR = "activation_blocked:no_executor"
ACTIVATION_BLOCKED_NO_THREAT_MODEL_ACK = "activation_blocked:no_threat_model_ack"
ACTIVATION_BLOCKED_RUNTIME_MODE_NOT_ACTIVE = "activation_blocked:runtime_mode_not_active"
ACTIVATION_BLOCKED_NEEDS_HUMAN_CONFIRMATION = "activation_blocked:needs_human_confirmation"
ACTIVATION_BLOCKED_NO_REQUIREMENT_ENTRY = "activation_blocked:no_requirement_entry"


@dataclass(frozen=True)
class ActivationRequirement:
    capability: str
    risk_tier: str
    requires_runtime_mode: tuple[str, ...] = ("local_single_user_runtime",)
    requires_executor: bool = True
    requires_policy_rules: bool = False
    requires_storage: bool = False
    requires_events: bool = False
    requires_threat_model_ack: bool = False
    requires_human_confirmation_to_enable: bool = False
    notes: str = ""


def _req(
    cap: str,
    tier: str,
    *,
    mode: tuple[str, ...] | None = None,
    executor: bool = True,
    threat_ack: bool = False,
    human_confirm: bool = False,
    notes: str = "",
) -> ActivationRequirement:
    return ActivationRequirement(
        capability=cap,
        risk_tier=tier,
        requires_runtime_mode=mode or ("local_single_user_runtime",),
        requires_executor=executor,
        requires_threat_model_ack=threat_ack,
        requires_human_confirmation_to_enable=human_confirm,
        notes=notes,
    )


# ── Build one entry per capability ──────────────────────────────────────────


def _build_registry() -> dict[str, ActivationRequirement]:
    r: dict[str, ActivationRequirement] = {}

    # Phase 3 — UI contracts (no executor)
    for cap in ("desktop_ui", "web_ui", "dashboard"):
        r[cap] = _req(cap, "ui", executor=False, notes="Client contract; surfaced via UI, no executor.")

    # Phase 3 — disabled / planning
    for cap in ("plugin_execution",):
        r[cap] = _req(cap, "4", threat_ack=True, human_confirm=True, notes="Phase-7 alias for plugin_execution_cap.")
    for cap in ("graph_codemap_indexing", "graph_codemap_planning",
                "semantic_memory_writes", "semantic_memory_review_queue"):
        r[cap] = _req(cap, "3", notes="Phase-3 read/write; executors pending.")

    # Phase 4
    for cap in ("external_channels",):
        r[cap] = _req(cap, "5", mode=("multi_user_local_runtime",), threat_ack=True, human_confirm=True,
                      notes="Alias for external_channel_runtime.")
    for cap in ("subagents", "multi_agent_teams"):
        r[cap] = _req(cap, "5", threat_ack=True, human_confirm=True,
                      notes="Spawning/team runtime; isolation + budgets.")
    for cap in ("remote_execution", "container_execution"):
        r[cap] = _req(cap, "5", mode=("hosted_or_networked_runtime",), threat_ack=True, human_confirm=True,
                      notes="Alias for remote_execution_cap / container_execution_cap.")

    # Runtime domain — Tier 1
    for cap in ("approval_execution_relay", "file_write_execution", "patch_apply_execution"):
        r[cap] = _req(cap, "1", notes="First-slice caps; executor registered.")
    for cap in ("memory_write_execution", "memory_forget_execution"):
        r[cap] = _req(cap, "1", notes="Memory mutation caps; executor pending.")

    # Tier 2
    for cap in ("shell_execution", "process_execution", "network_execution", "web_fetch"):
        r[cap] = _req(cap, "2", threat_ack=True, human_confirm=True,
                      notes="Sandbox, allowlist, budget required.")

    # Tier 3
    for cap in ("graph_indexing_runtime", "semantic_memory_runtime", "vector_embedding_runtime"):
        r[cap] = _req(cap, "3", notes="Local indexing / embedding runtime; executor registered.")
    r["model_provider_runtime"] = _req(
        "model_provider_runtime", "3", threat_ack=True, human_confirm=True,
        notes="Provider-backed embedding; egress + hosted/private gate + API-key gated; executor registered.")

    # Tier 4
    for cap in ("plugin_execution_cap", "plugin_install", "plugin_revocation_cap"):
        r[cap] = _req(cap, "4", threat_ack=True, human_confirm=True,
                      notes="Plugin sandbox; signature verify.")
    r["plugin_runtime_cap"] = _req(
        "plugin_runtime_cap", "4", threat_ack=True, human_confirm=True,
        notes="Bounded subprocess plugin code runtime; owner plugin allowlist, interpreter allowlist.")
    r["plugin_sandboxed_runtime_cap"] = _req(
        "plugin_sandboxed_runtime_cap", "4", threat_ack=True, human_confirm=True,
        notes="Network-isolated container plugin runtime; owner plugin + image allowlist.")

    # Tier 5
    for cap in ("external_channel_runtime", "channel_approval_relay"):
        # Raiker is single-user: the reference channel is a single-owner bridge,
        # so it activates under local_single_user_runtime (not multi-user).
        r[cap] = _req(cap, "5", threat_ack=True, human_confirm=True,
                      notes="Single-user reference channel: connector auth + owner egress allowlist.")
    # Local sandboxed container execution activates under the single-user runtime
    # (it is local Docker with no network / no host mounts). Remote/cloud egress
    # stays gated to hosted_or_networked_runtime.
    r["container_execution_cap"] = _req(
        "container_execution_cap", "5", threat_ack=True, human_confirm=True,
        notes="Local sandboxed container: no network, no mounts, owner image allowlist.")
    for cap in ("remote_execution_cap", "cloud_execution_cap"):
        r[cap] = _req(cap, "5", mode=("hosted_or_networked_runtime",), threat_ack=True, human_confirm=True,
                      notes="Isolation, secrets, egress, budget required.")
    # Hosted / private-network model APIs are called *from* the local
    # single-user machine (like the reference channel): owner egress
    # allowlist + env-only credentials, so they activate under
    # local_single_user_runtime. See docs/threat-models/hosted-models.md.
    for cap in ("hosted_model_runtime", "private_network_model_runtime"):
        r[cap] = _req(cap, "5", threat_ack=True, human_confirm=True,
                      notes="Owner egress allowlist, env-only credentials, metadata-only events.")
    for cap in ("scheduled_routines",):
        r[cap] = _req(cap, "5", threat_ack=True, human_confirm=True,
                      notes="Scheduler storage, owner consent, budget.")

    # Tier 6
    for cap in ("email_runtime", "calendar_runtime", "reminder_runtime",
                "finance_runtime", "investment_runtime", "medical_runtime",
                "pregnancy_baby_runtime", "cctv_runtime", "home_security_runtime",
                "hardware_operator_runtime"):
        r[cap] = _req(cap, "6", threat_ack=True, human_confirm=True,
                      notes="High-sensitivity domain; per-domain threat model required.")

    # Governance
    for cap in ("admin_mutation", "policy_mutation", "role_mutation"):
        r[cap] = _req(cap, "gov", executor=False, threat_ack=True,
                      notes="Governed mutation; AI never allowed; no executor needed.")
    r["audit_export"] = _req("audit_export", "gov", executor=False,
                             notes="Export with redaction + integrity; no executor needed.")

    return r


ACTIVATION_REQUIREMENTS: dict[str, ActivationRequirement] = _build_registry()


def get_activation_requirement(capability: str) -> ActivationRequirement | None:
    return ACTIVATION_REQUIREMENTS.get(capability)


def evaluate_activation_requirement(
    capability: str,
    target_state: str,
    principal: Principal,
    store: Any,
    registry: Any = None,
    confirmation_token: str | None = None,
) -> str | None:
    """Evaluate whether *capability* can transition to *target_state*.

    Returns None if allowed, or a specific reason-code string if blocked.

    ``registry`` is the live :class:`ExecutorRegistry`. Executor availability is
    determined from the registry's actual contents (no static allowlist), so a
    capability without a genuinely-registered executor can never be activated.
    """
    enabled_states = {
        CapabilityState.ENABLED_READ_ONLY,
        CapabilityState.ENABLED_POLICY_GATED,
        CapabilityState.ENABLED_RUNTIME,
    }
    if target_state not in enabled_states:
        return None

    req = get_activation_requirement(capability)
    if req is None:
        return f"{ACTIVATION_BLOCKED_NO_REQUIREMENT_ENTRY}:{capability}"

    if principal.principal_type != PrincipalType.HUMAN:
        return f"{ACTIVATION_BLOCKED_NEEDS_HUMAN_CONFIRMATION}:{capability}"

    if target_state == CapabilityState.ENABLED_RUNTIME.value:
        active_mode = store.get_active_runtime_mode()
        mode_name = active_mode["mode_name"] if active_mode else "development_preview"
        if mode_name not in req.requires_runtime_mode:
            return f"{ACTIVATION_BLOCKED_RUNTIME_MODE_NOT_ACTIVE}:{capability} (needs {req.requires_runtime_mode})"

    if req.requires_executor and not has_executor(capability, registry):
        return f"{ACTIVATION_BLOCKED_NO_EXECUTOR}:{capability}"

    if req.requires_threat_model_ack and not _has_threat_model_ack(capability, store):
        return f"{ACTIVATION_BLOCKED_NO_THREAT_MODEL_ACK}:{capability}"

    if req.requires_human_confirmation_to_enable and not confirmation_token:
        return f"{ACTIVATION_BLOCKED_NEEDS_HUMAN_CONFIRMATION}:{capability} (confirmation_token required)"

    return None


def has_executor(capability: str, registry: Any = None) -> bool:
    """True only if a real executor is registered for *capability*.

    Backed by the live registry — there is no static "satisfied" allowlist, so
    activation cannot be granted for a capability whose executor is missing or
    fail-closed-only (those are simply never registered).
    """
    return registry is not None and registry.has(capability)


def _has_threat_model_ack(capability: str, store: Any) -> bool:
    with store.connect() as connection:
        row = connection.execute(
            "SELECT 1 FROM threat_model_acks WHERE capability = ?", (capability,)
        ).fetchone()
    return row is not None
