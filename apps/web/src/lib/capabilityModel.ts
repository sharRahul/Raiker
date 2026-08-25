import type { CapabilityGate } from "./apiTypes";
import type { BadgeVariant } from "./types";
import { humanize } from "./format";

// Capability gate states that mean the gate is enabled (anything else is off / not yet enabled).
const ENABLED_STATES = new Set(["enabled_read_only", "enabled_policy_gated", "enabled_runtime"]);

/** True when the gate is not enabled (off, planned, or only "readiness"-ready). */
export function isDisabled(gate: CapabilityGate): boolean {
  return !ENABLED_STATES.has(gate.state);
}

/** A capability with no real executor is deferred (future), not merely gated. */
export function isDeferred(gate: CapabilityGate): boolean {
  const reason = gate.blocked_reason_code ?? "";
  if (reason.includes("no_executor") || reason.includes("no_requirement_entry")) return true;
  // The backend strips every enabled target from allowed_transitions when the
  // capability has no executor in this runtime, so a disabled gate that offers
  // no enable path is a future, not a tool (fail-closed sensitive domains,
  // remote/cloud execution, and similar).
  return isDisabled(gate) && enableableTargets(gate).length === 0;
}

// The meaningful "enable" target states a capability control may offer.
const ENABLE_TARGETS = ["enabled_policy_gated", "enabled_runtime"] as const;

/**
 * The enable targets actually offered by the backend for this gate. The backend's
 * `allowed_transitions` already excludes enabled states for fail-closed/deferred caps
 * (no executor / wrong runtime mode), so an empty result means the cap is un-enableable here.
 */
export function enableableTargets(gate: CapabilityGate): string[] {
  return ENABLE_TARGETS.filter((t) => gate.allowed_transitions.includes(t));
}

/** True when this principal can enable the gate to a real enabled state (authority + a target).
 *
 * `isDisabled` is part of the question, not an optimisation. `allowed_transitions`
 * lists every state a capability *may* hold rather than every state it may move
 * to next, so an already-enabled gate still names its own enabled state as a
 * target — which rendered "Turn on" next to "Turn off" and would have set the
 * capability to the state it was already in.
 */
export function canEnable(gate: CapabilityGate): boolean {
  return (
    gate.can_current_principal_change
    && isDisabled(gate)
    && !isDeferred(gate)
    && enableableTargets(gate).length > 0
  );
}

/** True when an authorised principal can turn the (currently enabled) gate off. */
export function canDisable(gate: CapabilityGate): boolean {
  return gate.can_current_principal_change && !isDisabled(gate);
}

// Tier-2 capabilities the backend gates behind a human confirmation token + threat-model ack
// (raiker/runtime/authority/activation.py). This is a UI hint to pre-collect those inputs in the
// step-up window; the backend is the source of truth and enforces the requirement regardless.
const TIER2_STEPUP_CAPS = new Set([
  "shell_execution",
  "process_execution",
  "web_fetch",
  "mcp_builder_runtime",
  "mcp_connector_runtime",
]);

export function requiresStepUpToken(capability: string): boolean {
  return TIER2_STEPUP_CAPS.has(capability);
}

/** Map a backend gate to a status badge (text + shape; never colour-only). */
export function gateBadge(gate: CapabilityGate): BadgeVariant {
  if (gate.state === "enabled_read_only") return "read-only";
  if (ENABLED_STATES.has(gate.state)) return "implemented";
  if (isDeferred(gate)) return "deferred";
  return "disabled";
}

// ── What the switch actually decides (GEP-04) ────────────────────────────────
// Forty-five capabilities have a real executor and therefore a gate, and this
// page renders every gate as a switch. For fifteen of them, flipping it changed
// nothing: either nothing in the product reaches the executor, or the work
// happens under a different control the gate never consults. An owner holding a
// switch that governs nothing is the one failure mode a governance product
// cannot have, so the card says which kind of switch it is.

/** True when this gate's own state decides whether the capability runs. */
export function governsItsOwnCapability(gate: CapabilityGate): boolean {
  return (gate.gate_reality ?? "own_gate") === "own_gate";
}

/** True when the work runs and a *different* named control governs it. */
export function isGovernedElsewhere(gate: CapabilityGate): boolean {
  return gate.gate_reality === "governed_elsewhere";
}

/** True when nothing in the product reaches this capability's executor. */
export function hasNoRoute(gate: CapabilityGate): boolean {
  return gate.gate_reality === "no_path";
}

/** The short label for a switch that does not govern its own capability. */
export function realityLabel(gate: CapabilityGate): string {
  if (isGovernedElsewhere(gate)) return "Governed elsewhere";
  if (hasNoRoute(gate)) return "No route yet";
  return "";
}

/**
 * The sentence to show beside such a switch — what really governs the work, or
 * why nothing runs. Empty when the switch means what it says.
 */
export function realityNote(gate: CapabilityGate): string {
  return governsItsOwnCapability(gate) ? "" : (gate.governance_note ?? "").trim();
}

/** Group gates by backend phase (a real backend field) for the matrix. */
export function groupByPhase(gates: CapabilityGate[]): { phase: number; gates: CapabilityGate[] }[] {
  const byPhase = new Map<number, CapabilityGate[]>();
  for (const gate of gates) {
    const list = byPhase.get(gate.phase) ?? [];
    list.push(gate);
    byPhase.set(gate.phase, list);
  }
  return [...byPhase.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([phase, list]) => ({
      phase,
      gates: [...list].sort((a, b) => a.capability.localeCompare(b.capability)),
    }));
}

// ── Tool domains ─────────────────────────────────────────────────────────────
// The Capabilities page groups executable tools by what they touch, not by
// backend phase. Inherent contract surfaces (the UI reading itself) and
// deferred capabilities (no executor) are not tools and are omitted entirely.

const INHERENT_CAPABILITIES = new Set(["web_ui", "dashboard", "desktop_ui"]);

/** A contract/read-only surface the user never wields as a tool. */
export function isInherent(gate: CapabilityGate): boolean {
  if (INHERENT_CAPABILITIES.has(gate.capability)) return true;
  return capabilityLabel(gate.capability).toLowerCase().includes("legacy gate");
}

export const CAPABILITY_DOMAIN_ORDER = [
  "Workspace",
  "Local execution",
  "Network",
  "Models",
  "Connectors",
  "MCP",
  "Automation",
  "Other tools",
] as const;

const DOMAIN_OF: Record<string, (typeof CAPABILITY_DOMAIN_ORDER)[number]> = {
  file_write_execution: "Workspace",
  patch_apply_execution: "Workspace",
  git_write_execution: "Workspace",
  memory_write_execution: "Workspace",
  memory_forget_execution: "Workspace",
  task_management_runtime: "Workspace",
  project_assignment_runtime: "Workspace",
  semantic_memory_writes: "Workspace",
  semantic_memory_review_queue: "Workspace",
  graph_codemap_indexing: "Workspace",
  // B9 — the repository code map. Workspace, beside the file capabilities, because
  // it reads workspace files and writes a derived index and reaches nothing else.
  code_map_indexing: "Workspace",
  graph_codemap_planning: "Workspace",
  graph_indexing_runtime: "Workspace",
  semantic_memory_runtime: "Workspace",
  vector_embedding_runtime: "Workspace",
  audit_export: "Workspace",
  // BUG-230 — the rewind. It belongs beside the file capabilities it puts
  // back, not in "Other tools", which is where an unmapped capability lands.
  checkpoint_restore_execution: "Workspace",
  shell_execution: "Local execution",
  process_execution: "Local execution",
  container_execution_cap: "Local execution",
  subagents: "Local execution",
  multi_agent_teams: "Local execution",
  web_fetch: "Network",
  // BUG-67 — a push is repository work, but what makes it a separate decision is
  // that it leaves the machine. It sits with the other egress switches so the
  // owner reviewing "what can reach the network" sees it.
  git_push_execution: "Network",
  external_channel_runtime: "Network",
  channel_approval_relay: "Network",
  hosted_model_runtime: "Models",
  private_network_model_runtime: "Models",
  model_provider_runtime: "Models",
  advisor_model_runtime: "Models",
  plugin_sandbox_image_pull_cap: "Connectors",
  plugin_install: "Connectors",
  plugin_execution_cap: "Connectors",
  plugin_revocation_cap: "Connectors",
  plugin_runtime_cap: "Connectors",
  plugin_sandboxed_runtime_cap: "Connectors",
  email_runtime: "Connectors",
  calendar_runtime: "Connectors",
  reminder_runtime: "Connectors",
  mcp_builder_runtime: "MCP",
  mcp_connector_runtime: "MCP",
  scheduled_routines: "Automation",
  approval_execution_relay: "Automation",
  admin_mutation: "Automation",
  policy_mutation: "Automation",
  role_mutation: "Automation",
};

/** Domain for one capability; unknown (future) capabilities are never hidden. */
export function capabilityDomain(capability: string): string {
  const mapped = DOMAIN_OF[capability];
  if (mapped) return mapped;
  if (/^connector_.+_runtime$/.test(capability)) return "Connectors";
  return "Other tools";
}

/** Group executable tools by domain, in the fixed display order. */
export function groupByDomain(gates: CapabilityGate[]): { domain: string; gates: CapabilityGate[] }[] {
  const byDomain = new Map<string, CapabilityGate[]>();
  for (const gate of gates) {
    const domain = capabilityDomain(gate.capability);
    const list = byDomain.get(domain) ?? [];
    list.push(gate);
    byDomain.set(domain, list);
  }
  return CAPABILITY_DOMAIN_ORDER.filter((domain) => byDomain.has(domain)).map((domain) => ({
    domain,
    gates: [...byDomain.get(domain)!].sort((a, b) =>
      capabilityLabel(a.capability).localeCompare(capabilityLabel(b.capability)),
    ),
  }));
}

export interface CapabilityExplanation {
  status: string;
  why: string;
  requirement: string;
  kind: "deferred" | "gated" | "enabled";
}

const REASON_TEXT: Record<string, string> = {
  "activation_blocked:no_executor": "No runtime exists for this capability yet.",
  "activation_blocked:no_requirement_entry": "This capability is not flippable in this runtime.",
  "activation_blocked:runtime_mode_not_active": "The required runtime mode is not active.",
  "activation_blocked:no_threat_model_ack": "A threat-model acknowledgement is required.",
  "activation_blocked:needs_human_confirmation": "A human confirmation token is required.",
  disabled_by_capability_gate: "The capability gate is turned off.",
};

/** Plain-English explanation for a disabled/deferred capability row. */
export function explainCapability(gate: CapabilityGate): CapabilityExplanation {
  if (ENABLED_STATES.has(gate.state)) {
    return { status: gate.state, why: "Enabled.", requirement: "—", kind: "enabled" };
  }
  const reason = gate.blocked_reason_code ?? "";
  const why = REASON_TEXT[reason] ?? (reason ? reason : "This capability is currently off.");
  const notReady = Object.entries(gate.readiness)
    .filter(([, ready]) => !ready)
    .map(([key]) => key.replace(/_ready$/, ""));
  const deferred = isDeferred(gate);
  const requirement = deferred
    ? "Not available in the local single-user runtime (no executor)."
    : notReady.length > 0
      ? `Pending readiness: ${notReady.join(", ")}.`
      : "Enable it from this page (if your principal is authorised).";
  return {
    status: gate.state,
    why,
    requirement,
    kind: deferred ? "deferred" : "gated",
  };
}

// ── Why a runtime-gated surface is blocked (BUG-11) ─────────────────────────
//
// A surface that needs `runtime_enabled` has three distinct ways of being shut,
// and they need three different actions from the owner. Saying "disabled —
// enable it in Capabilities" for all of them sends the owner to a page where
// the capability already reads as enabled, and following that advice changes
// nothing. Raising a capability to `enabled_runtime` is now entirely a
// Permissions action: Raiker runs one runtime and there is no mode to activate
// first, so every one of these cases resolves on the same page.

export type RuntimeBlockKind = "none" | "not_available" | "gate_off" | "below_runtime";

export interface RuntimeBlock {
  kind: RuntimeBlockKind;
  /** What is true right now, in plain English. */
  reason: string;
  /** The one action that actually unblocks it (empty when nothing will). */
  action: string;
  /** Where that action lives, or null when there is nowhere to go. */
  href: string | null;
  linkLabel: string | null;
}

/**
 * Why a `runtime_enabled` consumer is blocked, and what would unblock it.
 *
 * A missing gate is treated as off rather than open: a surface must never claim
 * to be usable because its gate could not be read.
 */
export function runtimeBlock(gate: CapabilityGate | undefined, label: string): RuntimeBlock {
  if (gate?.runtime_enabled) {
    return { kind: "none", reason: "", action: "", href: null, linkLabel: null };
  }
  if (gate === undefined) {
    return {
      kind: "gate_off",
      reason: `${label} is not enabled in this runtime.`,
      action: "Open Permissions to review the capability.",
      href: "#/capabilities",
      linkLabel: "Open Permissions",
    };
  }
  if (isDeferred(gate)) {
    return {
      kind: "not_available",
      reason: `${label} has no executor in this runtime, so it cannot be enabled here.`,
      action: "",
      href: null,
      linkLabel: null,
    };
  }
  if (ENABLED_STATES.has(gate.state)) {
    return {
      kind: "below_runtime",
      reason: `${label} is enabled, but only at “${humanize(gate.state)}” — this surface needs runtime level.`,
      action: "Set the capability to “enabled runtime” in Permissions.",
      href: "#/capabilities",
      linkLabel: "Open Permissions",
    };
  }
  return {
    kind: "gate_off",
    reason: `${label} is turned off.`,
    action: "Turn it on in Permissions.",
    href: "#/capabilities",
    linkLabel: "Open Permissions",
  };
}

// ── Decision modes (per-capability policy for AI-proposed actions) ──────────

export type DecisionMode = "ask" | "allow" | "auto" | "deny";

export const DECISION_MODES: readonly DecisionMode[] = ["ask", "allow", "auto", "deny"];

export const DECISION_MODE_COPY: Record<DecisionMode, { label: string; hint: string }> = {
  ask: { label: "Ask", hint: "Every AI-proposed action pauses for your approval (default)." },
  allow: { label: "Allow", hint: "AI-proposed actions run without prompting, within policy." },
  auto: { label: "Auto", hint: "Fully automatic within policy — the most permissive mode." },
  deny: { label: "Deny", hint: "Every AI-proposed action for this capability is refused." },
};

export function isDecisionMode(value: unknown): value is DecisionMode {
  return typeof value === "string" && (DECISION_MODES as readonly string[]).includes(value);
}

// ── Friendly copy for every registered capability ────────────────────────────
// Descriptions are transcribed from docs/architecture/RUNTIME_EXECUTORS_SPEC.md and
// docs/architecture/IMPLEMENTATION_STATUS.md. Unknown capabilities fall back to a humanised
// name so a new backend capability is never hidden.

interface CapabilityCopy {
  label: string;
  description: string;
}

const CAPABILITY_COPY: Record<string, CapabilityCopy> = {
  // Phase 3 — UI contracts and memory/graph foundations.
  desktop_ui: { label: "Desktop app", description: "Native desktop client contract (deferred surface)." },
  web_ui: { label: "Web dashboard", description: "This local web app's read/contract capability." },
  dashboard: { label: "Dashboard views", description: "Read-only governed dashboard view contract." },
  plugin_execution: {
    label: "Plugin execution (legacy gate)",
    description: "Phase-3 plugin execution contract gate.",
  },
  code_map_indexing: {
    label: "Code map",
    description:
      "Index this repository's files and what they declare, so the agent can find a definition instead of guessing a search pattern. Local and read-derived: it reads files the agent may already open, returns coordinates rather than code, and never leaves this machine.",
  },
  graph_codemap_indexing: {
    label: "Graph memory indexing (not implemented)",
    description:
      "The Phase-3 durable code-graph store — nodes and edges with provenance, approval previews and rollback plans. Still a dry-run planner; the working repository index is Code map, above.",
  },
  graph_codemap_planning: {
    label: "Graph memory planning (not implemented)",
    description:
      "The Phase-3 dry-run planner over the durable code-graph store. Named for that subsystem rather than for Code map, so the two are not mistaken for each other in this list.",
  },
  semantic_memory_writes: {
    label: "Semantic memory writes",
    description: "Write durable semantic memories (approval-governed).",
  },
  semantic_memory_review_queue: {
    label: "Memory review queue",
    description: "Human review queue for proposed memories.",
  },
  // Phase 4 — orchestration and execution surfaces.
  external_channels: {
    label: "External channels (legacy gate)",
    description: "Phase-4 external channel contract gate.",
  },
  subagents: { label: "Subagents", description: "Delegate bounded work to governed in-process subagents." },
  multi_agent_teams: {
    label: "Multi-agent teams",
    description: "Coordinate several governed agents on one objective.",
  },
  remote_execution: {
    label: "Remote execution (legacy gate)",
    description: "Phase-4 remote execution contract gate.",
  },
  container_execution: {
    label: "Container execution (legacy gate)",
    description: "Phase-4 container execution contract gate.",
  },
  // Runtime domains — Tier 1/2 execution.
  shell_execution: {
    label: "Shell commands",
    description: "Run sandboxed shell commands with output caps and timeouts.",
  },
  process_execution: {
    label: "Processes",
    description: "Start bounded local processes through the sandbox.",
  },
  web_fetch: {
    label: "Web fetch",
    description:
      "Read web pages and run web searches. HTTPS only, every resolved address must be public, and each redirect is re-checked against your blocklist.",
  },
  file_write_execution: {
    label: "File writes",
    description: "Write files in the workspace (approval-gated proposals).",
  },
  patch_apply_execution: {
    label: "Patch apply",
    description: "Apply unified-diff patches to workspace files (approval-gated).",
  },
  git_write_execution: {
    label: "Git writes",
    description:
      "Create a branch or record a commit in the workspace repository when you approve one the agent proposed.",
  },
  git_push_execution: {
    label: "Git push",
    description:
      "Send an approved branch to its remote with your own credential. Separate from Git writes because a push leaves this machine: it still needs the remote's host on your connector egress allowlist, and it never forces or deletes a branch.",
  },
  memory_write_execution: {
    label: "Memory store",
    description:
      "Let a turn propose a durable fact or preference to remember. You see the exact text before it is stored, and text that looks like a credential is refused outright.",
  },
  memory_forget_execution: {
    label: "Memory forget",
    description:
      "Let a turn propose deleting one stored memory. You see which record would go before you decide.",
  },
  task_management_runtime: {
    label: "Task creation",
    description: "Create a task in Tasks when you approve one the agent proposed.",
  },
  project_assignment_runtime: {
    label: "Project assignment",
    description: "Move a conversation into a project when you approve the move.",
  },
  approval_execution_relay: {
    label: "Approval execution relay",
    description: "Execute an action after approval (disabled: approvals stay metadata-only).",
  },
  admin_mutation: { label: "Admin mutations", description: "Administrative changes to runtime records." },
  policy_mutation: { label: "Policy mutations", description: "Change policy rules (owner-only, off by default)." },
  role_mutation: { label: "Role mutations", description: "Grant or revoke principal roles (human-only)." },
  // Models.
  model_provider_runtime: {
    label: "Provider embeddings",
    description: "Call a provider's embedding endpoint and store semantic vectors (egress-gated).",
  },
  hosted_model_runtime: {
    label: "Hosted models",
    description: "Talk to hosted LLM APIs (Anthropic, OpenAI, Gemini, OpenRouter) behind the egress allowlist.",
  },
  private_network_model_runtime: {
    label: "Home-lab models",
    description: "Talk to private-network inference servers such as vLLM.",
  },
  // Personal-domain local stores.
  email_runtime: {
    label: "Email drafts (local)",
    description: "Local email drafts only — queued for a human to send; Raiker never transmits.",
  },
  calendar_runtime: {
    label: "Calendar (local)",
    description: "Local calendar events only — no external calendar sync or invites.",
  },
  reminder_runtime: { label: "Reminders (local)", description: "Local reminder store — create and list." },
  // Sensitive domains — fail closed, no executor.
  finance_runtime: { label: "Finance", description: "No executor; fails closed pending a per-domain threat model." },
  investment_runtime: {
    label: "Investments",
    description: "No executor; fails closed pending a per-domain threat model.",
  },
  medical_runtime: { label: "Medical", description: "No executor; fails closed pending a per-domain threat model." },
  pregnancy_baby_runtime: {
    label: "Pregnancy & baby",
    description: "No executor; fails closed pending a per-domain threat model.",
  },
  cctv_runtime: { label: "CCTV", description: "No executor; fails closed pending a per-domain threat model." },
  home_security_runtime: {
    label: "Home security",
    description: "No executor; fails closed pending a per-domain threat model.",
  },
  hardware_operator_runtime: {
    label: "Hardware operator",
    description: "No executor; fails closed pending a per-domain threat model.",
  },
  // Plugins.
  plugin_install: {
    label: "Plugin install",
    description: "Validate a plugin manifest (checksum + signatures) and record the install.",
  },
  plugin_execution_cap: {
    label: "Plugin reads",
    description: "Installed plugins may call read-only tools through the broker.",
  },
  plugin_revocation_cap: {
    label: "Plugin revocation",
    description: "The off-switch: revoke an installed plugin so it fails closed.",
  },
  plugin_runtime_cap: {
    label: "Plugin runtime",
    description: "Run an allowlisted plugin's entrypoint as a bounded subprocess.",
  },
  plugin_sandboxed_runtime_cap: {
    label: "Plugin sandbox runtime",
    description: "Run a plugin inside a network-isolated container.",
  },
  // Channels / execution environments.
  external_channel_runtime: {
    label: "External channels",
    description: "One governed webhook channel for inbound messages.",
  },
  channel_approval_relay: {
    label: "Channel approval relay",
    description: "Relay approval requests over a governed channel.",
  },
  remote_execution_cap: {
    label: "Remote execution",
    description:
      "Run an approved command over SSH — only through a profile you configured, with a pinned host key.",
  },
  container_execution_cap: {
    label: "Container execution",
    description: "Run commands in an owner-allowlisted local container.",
  },
  cloud_execution_cap: {
    label: "Cloud execution",
    description:
      "Run an approved command in a Daytona sandbox — only through a profile you configured, under a cost ceiling.",
  },
  // Memory / retrieval runtimes.
  graph_indexing_runtime: {
    label: "Graph indexing runtime",
    description: "Maintain the workspace graph index as a governed runtime.",
  },
  semantic_memory_runtime: {
    label: "Semantic memory runtime",
    description: "Governed semantic memory store operations.",
  },
  vector_embedding_runtime: {
    label: "Vector embeddings",
    description: "Local embeddings + vector search; also gates retrieval-augmented turns (default-ask).",
  },
  // MCP.
  mcp_builder_runtime: {
    label: "MCP builder",
    description: "Create reviewed local MCP server templates inside the workspace.",
  },
  mcp_connector_runtime: {
    label: "MCP connector",
    description: "Connect to owner-added MCP servers over monitored, bounded sessions.",
  },
  // Models.
  advisor_model_runtime: {
    label: "Advisor model",
    description: "Run the second-opinion advisor model alongside the selected model.",
  },
  plugin_sandbox_image_pull_cap: {
    label: "Plugin sandbox image pull",
    description: "Pull the container image used by the plugin sandbox.",
  },
  // Automation / audit.
  scheduled_routines: {
    label: "Scheduled routines",
    description: "Time-based routine metadata (no unattended execution).",
  },
  audit_export: {
    label: "Audit export",
    description:
      "Export your own audit record as a redacted file plus a manifest hash over the events it covers.",
  },
  checkpoint_restore_execution: {
    label: "Checkpoint restore",
    description:
      "Rewind workspace files to a checkpoint. Approval-gated, and the restore is captured too, so it can be rewound.",
  },
};

export function capabilityLabel(capability: string): string {
  const copy = CAPABILITY_COPY[capability];
  if (copy) return copy.label;
  // Per-connector runtime capabilities are registered dynamically
  // (connector_github_runtime, …); label them by their service.
  const connector = capability.match(/^connector_(.+)_runtime$/);
  if (connector) return `${humanize(connector[1])} connector`;
  return humanize(capability);
}

export function capabilityDescription(capability: string): string {
  return CAPABILITY_COPY[capability]?.description ?? "Governed capability.";
}
