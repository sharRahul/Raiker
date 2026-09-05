from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from raiker.phase_gates import CapabilityState
from raiker.runtime.authority.models import (
    RUNTIME_STATUS_ACTIVE,
    Principal,
    PrincipalType,
)

ACTIVATION_BLOCKED_NO_EXECUTOR = "activation_blocked:no_executor"
ACTIVATION_BLOCKED_NO_THREAT_MODEL_ACK = "activation_blocked:no_threat_model_ack"
# Raiker has one runtime, so a capability is never blocked for being in the
# wrong mode. It is still blocked while the owner has switched the agent runtime
# off in Settings' danger zone, and this is that refusal. The reason code keeps
# its historical spelling so stored audit rows and older clients still resolve.
ACTIVATION_BLOCKED_RUNTIME_DISABLED = "activation_blocked:runtime_mode_not_active"
ACTIVATION_BLOCKED_RUNTIME_MODE_NOT_ACTIVE = ACTIVATION_BLOCKED_RUNTIME_DISABLED
ACTIVATION_BLOCKED_NEEDS_HUMAN_CONFIRMATION = "activation_blocked:needs_human_confirmation"
ACTIVATION_BLOCKED_NO_REQUIREMENT_ENTRY = "activation_blocked:no_requirement_entry"


@dataclass(frozen=True)
class ActivationRequirement:
    capability: str
    risk_tier: str
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
    executor: bool = True,
    threat_ack: bool = False,
    human_confirm: bool = False,
    notes: str = "",
) -> ActivationRequirement:
    return ActivationRequirement(
        capability=cap,
        risk_tier=tier,
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
        r[cap] = _req(cap, "5", threat_ack=True, human_confirm=True,
                      notes="Alias for external_channel_runtime.")
    for cap in ("subagents", "multi_agent_teams"):
        r[cap] = _req(cap, "5", threat_ack=True, human_confirm=True,
                      notes="Spawning/team runtime; isolation + budgets.")
    for cap in ("remote_execution", "container_execution"):
        r[cap] = _req(cap, "5", threat_ack=True, human_confirm=True,
                      notes="Alias for remote_execution_cap / container_execution_cap.")

    # B9 — the repository code map. A real executor exists, so this is a switch
    # the owner can throw rather than a name on the matrix: Tier 1 because the
    # scan reads workspace files and writes a derived index, and reaches nothing
    # outside the machine.
    r["code_map_indexing"] = _req(
        "code_map_indexing", "1",
        notes="Local read-derived symbol index; no egress, no mutation outside the index.",
    )

    # B10 — language intelligence. Tier 1 for the same reason and with less
    # reach: it reads workspace files and writes nothing at all.
    r["language_intelligence"] = _req(
        "language_intelligence", "1",
        notes="Local parse of workspace files; no egress, no index, no mutation.",
    )

    # Runtime domain — Tier 1
    for cap in ("approval_execution_relay", "file_write_execution", "patch_apply_execution"):
        r[cap] = _req(cap, "1", notes="First-slice caps; executor registered.")
    for cap in ("memory_write_execution", "memory_forget_execution"):
        r[cap] = _req(cap, "1", notes="Memory mutation caps; executor pending.")
    # BUG-62 — the two local planning mutations an approval carries out, plus the
    # rewind that was in the same position: a real executor, a gate the owner can
    # see, and no entry here, so *"Activation is blocked. Satisfy the activation
    # requirement first."* was the whole answer. A capability with a registered
    # executor and no requirement entry cannot be turned on at all; the invariant
    # is now asserted by a test rather than left to care.
    for cap in ("checkpoint_restore_execution", "task_management_runtime",
                "project_assignment_runtime"):
        r[cap] = _req(cap, "1", notes="Local, reversible, owner-scoped; executor registered.")
    # BUG-231 — the audit export. A local, redacted, account-scoped read of the
    # owner's own record written to a file beside it: no egress, no mutation of
    # anything the log describes, and the export is itself an audited event.
    r["audit_export"] = _req(
        "audit_export", "1",
        notes="Redacted, account-scoped export of the owner's own audit log; local file only.")
    # B11 — the git write path. Local and repository-scoped like the file caps
    # above; hooks are disabled for the invocation so an approved commit cannot
    # become an un-governed code-execution path.
    r["git_write_execution"] = _req(
        "git_write_execution", "1",
        notes="Local branch/commit in the workspace repository; repository hooks disabled.")

    # Tier 2
    for cap in ("shell_execution", "process_execution", "web_fetch"):
        r[cap] = _req(cap, "2", threat_ack=True, human_confirm=True,
                      notes="Sandbox, allowlist, budget required.")
    # BUG-67 — the governed push. Egress, so Tier 2 and acknowledged like the
    # rest of it; bound to the owner's own credential and the connector egress
    # allowlist, neither of which the gate can substitute for.
    r["git_push_execution"] = _req(
        "git_push_execution", "2", threat_ack=True, human_confirm=True,
        notes="Owner credential + connector egress allowlist; never forces, never deletes.")
    # Backlog #18 — the governed record over OTLP. Tier 2 because it leaves the
    # machine; metadata-only unless the owner opts into redacted content, and the
    # credential is an environment-variable *name*, never a stored value.
    r["telemetry_export"] = _req(
        "telemetry_export", "2", threat_ack=True, human_confirm=True,
        notes="OTLP export to an owner-named collector; metadata by default, "
              "redacted content on explicit opt-in.")
    # The Design surface. Tier 2 because it leaves the machine, and gated
    # separately from `hosted_model_runtime` because an owner who wanted a chat
    # model has not thereby asked to spend credit generating images.
    r["image_generation"] = _req(
        "image_generation", "2", threat_ack=True, human_confirm=True,
        notes="Hosted image model; model egress allowlist + owner credential; "
              "endpoint built from the configured profile, never from the request.")

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
    r["plugin_sandbox_image_pull_cap"] = _req(
        "plugin_sandbox_image_pull_cap", "4", threat_ack=True, human_confirm=True,
        notes="Owner-allowlisted Docker image pull for the sandboxed plugin runtime.")

    # Tier 5
    for cap in ("external_channel_runtime", "channel_approval_relay"):
        # The reference channel is a single-owner bridge: its containment is the
        # connector's own auth plus the owner egress allowlist, not a mode.
        r[cap] = _req(cap, "5", threat_ack=True, human_confirm=True,
                      notes="Single-user reference channel: connector auth + owner egress allowlist.")
    # Local sandboxed container execution: local Docker, no network, no host
    # mounts. Remote/cloud execution is a separate capability with its own gate
    # and threat model — see BUG-31 for the containment work still owed there.
    r["container_execution_cap"] = _req(
        "container_execution_cap", "5", threat_ack=True, human_confirm=True,
        notes="Local sandboxed container: no network, no mounts, owner image allowlist.")
    for cap in ("remote_execution_cap", "cloud_execution_cap"):
        r[cap] = _req(cap, "5", threat_ack=True, human_confirm=True,
                      notes="Isolation, secrets, egress, budget required.")
    # Hosted / private-network model APIs are called *from* the owner's machine
    # (like the reference channel): owner egress allowlist + env-only
    # credentials. See docs/threat-models/hosted-models.md.
    for cap in ("hosted_model_runtime", "private_network_model_runtime"):
        r[cap] = _req(cap, "5", threat_ack=True, human_confirm=True,
                      notes="Owner egress allowlist, env-only credentials, metadata-only events.")
    # Advisor model for local-model turns: the consult re-checks the hosted/
    # private egress path per call. See docs/threat-models/advisor-model.md.
    r["advisor_model_runtime"] = _req(
        "advisor_model_runtime", "5", threat_ack=True, human_confirm=True,
        notes="Default-ask consult of the owner-picked advisor profile; provider policy re-checked per call.")
    # GitHub read-only service connector (Task 4 reference slice): the read
    # reaches api.github.com with the owner's env-only token per call. See
    # docs/threat-models/connectors-github.md.
    r["connector_github_runtime"] = _req(
        "connector_github_runtime", "5", threat_ack=True, human_confirm=True,
        notes="Default-ask GitHub issue/PR read; env-only owner token, owner egress allowlist.")
    # Gmail read-only service connector (Task 4, second read connector): the read
    # reaches gmail.googleapis.com with the owner's env-only OAuth token per call.
    # See docs/threat-models/connectors-gmail.md.
    r["connector_gmail_runtime"] = _req(
        "connector_gmail_runtime", "5", threat_ack=True, human_confirm=True,
        notes="Default-ask Gmail message/thread read; env-only owner token, owner egress allowlist.")
    # Google Calendar read-only connector (Task 4). See
    # docs/threat-models/connectors-gcal.md.
    r["connector_gcal_runtime"] = _req(
        "connector_gcal_runtime", "5", threat_ack=True, human_confirm=True,
        notes="Default-ask Calendar event/calendar read; env-only owner token, owner egress allowlist.")
    # Slack read-only connector (Task 4). See
    # docs/threat-models/connectors-slack.md.
    r["connector_slack_runtime"] = _req(
        "connector_slack_runtime", "5", threat_ack=True, human_confirm=True,
        notes="Default-ask Slack channel info/history read; env-only owner token, owner egress allowlist.")
    for cap in ("scheduled_routines",):
        r[cap] = _req(cap, "5", threat_ack=True, human_confirm=True,
                      notes="Scheduler storage, owner consent, budget.")
    # Governed local stdio MCP builder + connector (Control Deck task 4): both
    # run on the local single-user machine. The builder writes a reviewed
    # workspace-relative server template; the connector runs a bounded JSON-RPC
    # stdio session against an owner-allowlisted local interpreter. No remote
    # transport / OAuth. See docs/threat-models/mcp-builder.md and
    # docs/threat-models/mcp-connector.md.
    r["mcp_builder_runtime"] = _req(
        "mcp_builder_runtime", "5", threat_ack=True, human_confirm=True,
        notes="Local stdio MCP server template write; workspace-relative path, reviewed template only.")
    r["mcp_connector_runtime"] = _req(
        "mcp_connector_runtime", "5", threat_ack=True, human_confirm=True,
        notes="Bounded local stdio MCP session; interpreter allowlist, workspace-relative args, redacted output.")

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

    # One runtime, one question: is it accepting executions? A stored row is
    # only ever consulted for its status now, never for which of five modes it
    # named, and no stored row at all means the runtime is on — a fresh install
    # has nothing to activate before its gates mean what they say.
    if target_state == CapabilityState.ENABLED_RUNTIME.value:
        active = (
            store.get_principal_runtime_mode(principal.principal_id)
            if store.get_account(principal.principal_id) is not None
            else store.get_latest_runtime_mode()
        )
        if active is not None and str(active.get("status", RUNTIME_STATUS_ACTIVE)) != RUNTIME_STATUS_ACTIVE:
            return f"{ACTIVATION_BLOCKED_RUNTIME_DISABLED}:{capability} (the agent runtime is disabled)"

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


def has_threat_model_ack(capability: str, store: Any) -> bool:
    """True when a threat-model acknowledgement is on record for *capability*."""
    with store.connect() as connection:
        row = connection.execute(
            "SELECT 1 FROM threat_model_acks WHERE capability = ?", (capability,)
        ).fetchone()
    return row is not None


# Backwards-compatible private alias (kept for existing internal callers).
_has_threat_model_ack = has_threat_model_ack
