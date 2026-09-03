import type { ApprovalMode } from "./approvalMode";

// Response shapes from the governed read API (see raiker/control/dashboard.py and
// raiker/control/dtos.py). These mirror the backend DTOs; the backend remains the source of truth.
// tests/test_api_contract_schemas.py guards the backend against dropping keys the UI reads.

export interface CapabilityGate {
  capability: string;
  phase: number;
  state: string;
  default_state: string;
  source: string;
  runtime_enabled: boolean;
  allowed_transitions: string[];
  can_current_principal_change: boolean;
  blocked_reason_code: string | null;
  readiness: Record<string, boolean>;
  // Per-capability decision mode for AI-proposed actions (ask|allow|auto|deny).
  decision_mode: string;
  // Activation preconditions the enable step-up dialog must collect, driven by
  // the backend's real requirements (not a hardcoded client list). Optional so
  // older payloads / test fixtures without them remain valid.
  requires_threat_model_ack?: boolean;
  requires_human_confirmation?: boolean;
  threat_model_ack_recorded?: boolean;
  // GEP-04 — what this gate actually decides. "own_gate" means the switch
  // governs the capability; "governed_elsewhere" means the work happens under a
  // different named control; "no_path" means nothing in the product reaches the
  // executor. Optional so older payloads and fixtures stay valid, and absent is
  // read as "own_gate".
  gate_reality?: "own_gate" | "governed_elsewhere" | "no_path";
  // The sentence naming what really governs the work, for anything that is not
  // "own_gate". Empty otherwise.
  governance_note?: string;
  // BUG-239 — how the *enforcing* path reads a gate table with nothing
  // persisted in it, and what it would therefore answer right now. On a fresh
  // account these disagree with `state` for `web_fetch`: nothing is stored, the
  // per-principal reading is fail-closed, and the tool would nevertheless
  // fetch. Optional so older payloads and fixtures stay valid.
  unset_resolution?: "off" | "shipped_default" | "shipped_default_unscoped";
  enforced_enabled?: boolean;
}

export interface ComposerApprovalModeSettings {
  approval_mode: ApprovalMode;
}

export interface RuntimeMode {
  mode_name: string;
  status: string;
  activated_by: string;
  activated_at: string;
  reason: string;
  allowed_modes: string[];
}

export interface RuntimeReadiness {
  mode: RuntimeMode;
  gates: CapabilityGate[];
  summary: Record<string, unknown>;
}

// GET /api/mcp/servers — one owner-scoped local stdio or remote HTTP MCP profile
// (see raiker/control/dashboard.py::McpServerView). `command` is argv for a
// local server; remote credentials are represented only by `auth_ref`.
// `tools` are the names discovered by the last successful handshake.
/**
 * Whether this owner's connected MCP tools can actually be called in a turn.
 *
 * Two owner controls stand between a connected server and the model — the
 * capability gate and the per-capability decision mode — so `connected` on a
 * server card is not the same claim as "the agent can use this".
 */
export interface McpAgentAccess {
  gate_enabled: boolean;
  decision_mode: string;
  /** True only when a projected MCP tool would really run this turn. */
  callable: boolean;
  /** Empty when callable; otherwise the exact runtime reason it is not. */
  reason_code: string;
  projected_tools: number;
  connected_servers: number;
}

/**
 * One step of the agent's plan for a conversation (B6). Written by the model
 * through the governed `update_plan` tool; at most one step is `in_progress`.
 */
export interface AgentPlanStep {
  title: string;
  status: "pending" | "in_progress" | "completed" | "blocked";
  note?: string;
}

export interface AgentPlan {
  session_id: string;
  steps: AgentPlanStep[];
  turn_id?: string;
  created_at?: string;
  updated_at?: string;
  total?: number;
  completed?: number;
  in_progress?: number;
  pending?: number;
  blocked?: number;
  current_step?: string;
}

export interface McpServer {
  server_id: string;
  name: string;
  command: string[];
  template: string | null;
  transport: string;
  status: string;
  created_at: string;
  last_connected_at: string | null;
  tools: string[];
  tool_count: number;
  endpoint_url: string | null;
  auth_ref: string | null;
  monitor_state: "active" | "paused" | "killed";
  paused_reason: string | null;
  paused_at: string | null;
  // BUG-234 — the MCP revision this server negotiated on its last successful
  // handshake, or null when it has never connected.
  protocol_version: string | null;
}

/**
 * One installed skill. `active` is the owner's own switch: an inactive skill
 * stays stored and is withheld from every turn. The stored document is never
 * carried in a list — it is read on an explicit download or by the runtime.
 */
/** One way an installed skill differs from the Agent Skills standard. */
export interface SkillConformanceFinding {
  field: string;
  code: string;
  // "error" — would not validate elsewhere; "warning" — portable but untidy;
  // "refused" — Raiker read the field and deliberately does not honour it.
  severity: "error" | "warning" | "refused";
  message: string;
}

/** How an installed skill measures against https://agentskills.io/specification. */
export interface SkillConformance {
  conformant: boolean;
  spec_url: string;
  findings: SkillConformanceFinding[];
  license: string;
  compatibility: string;
  metadata: Record<string, string>;
  refused_allowed_tools: string[];
}

export interface SkillView {
  skill_id: string;
  name: string;
  description: string;
  version: string | null;
  source: "upload" | "url" | "builtin" | "built" | "plugin";
  source_ref: string | null;
  checksum: string;
  active: boolean;
  files: string[];
  file_count: number;
  byte_size: number;
  created_at: string;
  updated_at: string;
  /** Optional owner-authored slash handle. It loads this skill and grants nothing. */
  command_trigger?: string | null;
  // Optional so older payloads and existing test fixtures stay valid; absent is
  // read as "not measured", which renders nothing rather than a false pass.
  conformance?: SkillConformance;
}

/** What a linked skill turned out to be, reported before anything is stored. */
export interface SkillVerification {
  ok: boolean;
  verified: boolean;
  name: string;
  description: string;
  version: string | null;
  checksum: string;
  byte_size: number;
  source_url: string;
  already_installed: boolean;
}

export interface SkillMutationResult {
  ok: boolean;
  skill_id: string;
  skill?: SkillView;
}

export interface McpSession {
  session_row_id: string;
  server_id: string;
  transport: string;
  operation: string;
  hosts: string[];
  tool_calls: number;
  bytes_in: number;
  bytes_out: number;
  error_count: number;
  outcome: string;
  started_at: string;
  ended_at: string | null;
}

export interface McpFinding {
  finding_id: string;
  source: string;
  severity: string;
  code: string;
  summary: string;
  redacted_detail: Record<string, unknown>;
  subject_id: string | null;
  state: string;
  created_at: string;
}

export interface Notification {
  notification_id: string;
  kind: string;
  title: string;
  body: string;
  finding_id: string | null;
  subject_id: string | null;
  read: boolean;
  created_at: string;
}

export interface StandingGrant {
  grant_id: string;
  principal_id: string;
  granted_by: string;
  action_type: string;
  tool_name: string;
  scope_pattern: string;
  risk_ceiling: string;
  reason: string;
  created_at: string;
  expires_at: string;
  revoked: number;
  use_count: number;
  last_used_at: string | null;
}

export interface CredentialLifecycle {
  credential_id?: string;
  provider: string;
  verified_at?: string | null;
  due_at: string;
  status: "current" | "warning" | "overdue";
}

export interface SecurityHealth {
  source: string;
  subject_id: string;
  code: string;
  state: string;
  updated_at: string;
}

// GET /api/capability-modes/{capability} — the per-capability decision mode
// (ask | allow | auto | deny) governing AI-proposed actions for that capability.
export interface CapabilityDecisionMode {
  ok: boolean;
  capability: string;
  decision_mode: string;
}

export interface ProviderHealth {
  profile_id: string;
  provider: string;
  model: string;
  endpoint_kind: string;
  local_only: boolean;
  requires_network: boolean;
  selected: boolean;
  status: string; // "selected" | "configured" — config-derived, never probed here
  detail: string;
}

export type ModelReadinessState =
  | "not_configured"
  | "checking"
  | "ready"
  | "runtime_missing"
  | "runtime_stopped"
  | "model_missing"
  | "policy_blocked"
  | "authentication_failed"
  | "quota_exhausted"
  | "unreachable"
  | "unsupported"
  | "stale";

/** Reachability of one exact owner/profile/model/endpoint tuple. */
export interface ModelReadinessView {
  owner_principal_id: string;
  profile_id: string;
  model: string;
  endpoint_fingerprint: string;
  state: ModelReadinessState;
  checked_at: string | null;
  expires_at: string | null;
  summary: string;
  reason_code: string;
  remediation: string;
  evidence: Record<string, unknown>;
  ready: boolean;
}

export interface ModelSetupState {
  owner_principal_id: string;
  status: "required" | "in_progress" | "skipped" | "complete";
  step: "choose_path" | "provider" | "model" | "review" | "ready";
  path:
    "provider" | "ollama" | "lm_studio" | "local_gguf" | "hugging_face" | null;
  selected_profile_id: string | null;
  selected_model: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface SetupState {
  owner_principal_id: string;
  status: "required" | "in_progress" | "skipped" | "complete";
  stage: "account" | "model" | "privacy" | "backup" | "finish";
  selected_profile_id: string | null;
  selected_model: string | null;
  model_deferred: boolean;
  privacy_mode: "local_first" | "balanced" | null;
  privacy_acknowledged_at: string | null;
  backup_mode: "later" | "local";
  backup_target: string | null;
  backup_verified_at: string | null;
  background_service_enabled: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface ModelOperation {
  operation_id: string;
  owner_principal_id: string;
  kind: "install" | "download" | "convert" | "deploy" | "pull";
  target: string;
  state:
    | "queued"
    | "running"
    | "cancel_requested"
    | "cancelled"
    | "failed"
    | "complete";
  phase: string;
  progress_bytes: number;
  total_bytes: number | null;
  progress_percent: number | null;
  source_url: string | null;
  destination: string | null;
  error_code: string | null;
  error_detail: string | null;
  created_at: string;
  updated_at: string;
  /** True when a retry can really reconstruct and dispatch this job (BUG-75). */
  retryable: boolean;
  /** True when a terminal operation may have left an incomplete destination. */
  partial_files_present: boolean;
}

/** What a confirmed "Delete partial files" would remove — named exactly. */
export interface PartialFiles {
  path: string | null;
  exists: boolean;
  bytes: number;
  file_count: number;
}

/** One monitored subject's containment state (BUG-76, BUG-77). */
export interface ContainedSubject {
  capability: string;
  capability_label: string;
  subject_id: string;
  label: string;
  state: "active" | "paused" | "killed";
  reason: string;
  source: string;
  finding_id: string | null;
  failure_streak: number;
  last_failure_code: string;
  contained_at: string | null;
  probe_after: string | null;
  updated_at: string;
}

export interface CapabilityContainmentView {
  subjects: ContainedSubject[];
  contained: number;
  capabilities: { id: string; label: string }[];
}

/** What a plugin manifest's signature actually proved (BUG-79). */
export interface PluginSignature {
  level: "verified" | "present_only" | "unsigned";
  label: string;
  reason: string;
  method: string;
  verified: boolean;
  explanation: string;
  remediation: string;
}

/** What a plugin actually provides, read from the files the runtime loads
 *  rather than from the manifest that described them (BUG-221). */
/** One connector profile, and what is actually true of it right now (BUG-225). */
export interface ChannelProfile {
  connector_id: string;
  channel_type: string;
  display_name: string;
  transport: string;
  auth_method: string;
  default_state: string;
  requires_pairing: boolean;
  requires_sender_allowlist: boolean;
  requires_network: boolean;
  /** Is there a pairing at all. */
  linked: boolean;
  /** Is that pairing switched on. Linked is not enabled. */
  enabled: boolean;
  pairing_id: string | null;
  display_label: string | null;
  sender_count: number;
  senders: string[];
  routing_mode: "record_only" | "new_turn" | "side_question" | "interrupt";
  target_session_id: string | null;
  owner_sender_id: string | null;
  approval_relay_enabled: boolean;
  supports_side_questions: boolean;
  supports_interrupts: boolean;
  supports_approvals: boolean;
}

export interface ChannelsView {
  profiles: ChannelProfile[];
  error: string | null;
  outbound: {
    capability?: string;
    gate_state?: string;
    runtime_enabled?: boolean;
    /** RAIKER_CHANNEL_EGRESS_ALLOWLIST names at least one host. Fail-closed. */
    egress_configured?: boolean;
    egress_host_count?: number;
    /** RAIKER_CHANNEL_OUTBOUND_SECRET is set, so deliveries carry an HMAC. */
    signing_configured?: boolean;
  };
  inbound: {
    /** RAIKER_CHANNEL_INBOUND_SECRET is set. Without it the receiver refuses. */
    secret_configured?: boolean;
    /** Messages per sender per minute. Allowlisting says who; this says how often. */
    rate_limit_per_minute?: number;
    quarantined?: boolean;
    instructions_inert?: boolean;
  };
}

/** An MCP server an installed plugin offers. Inert until the owner adds it. */
export interface McpOffer {
  plugin_id: string;
  name: string;
  transport: "http" | "stdio";
  description: string;
  endpoint_url?: string;
  auth_ref?: string | null;
  template?: string;
  already_added: boolean;
}

export interface PluginContributions {
  hooks: number;
  events: string[];
  /** Skills the plugin ships. They install switched off and are credited to it. */
  skills: number;
  skill_names: string[];
  /** MCP servers it offers. Offers are inert until the owner adds them. */
  mcp_servers: number;
  mcp_server_names: string[];
  /** "unreadable" when the contributed file exists and could not be parsed. */
  error: string | null;
}

export interface InstalledPlugin {
  record_id: string;
  plugin_id: string;
  version: string;
  trust_level: string;
  status: string;
  source_url: string | null;
  installed_at: string;
  installed_by: string;
  checksum_present: boolean;
  signature: PluginSignature;
  contributions: PluginContributions;
}

/** A kind of contribution, and whether this build accepts it yet — so
 *  "provides nothing" and "may not provide anything" stay distinguishable. */
export interface PluginContributionKind {
  kind: string;
  available: boolean;
  summary: string;
}

export interface PluginsView {
  plugins: InstalledPlugin[];
  signing: {
    configured: boolean;
    hmac_key_set: boolean;
    publisher_key_set: boolean;
    summary: string;
    remediation: string;
  };
  contribution_kinds: PluginContributionKind[];
}

export interface RuntimeInstallPlan {
  runtime: string;
  action: string;
  source_url: string;
  argv: string[];
  requires_elevation: boolean;
  terms_url: string;
  redistribution: boolean;
}

export interface LocalModel {
  owner_principal_id: string;
  root_path: string;
  model_id: string;
  name: string;
  architecture: string;
  quantization: string | null;
  primary_path: string;
  shard_count: number;
  expected_shards: number;
  complete: boolean;
  size_bytes: number;
  indexed_at: string;
  /** Runtime format detected from the approved local model folder. */
  format?: "gguf" | "mlx";
}

export interface ModelLibraryView {
  roots: Array<{ path: string }>;
  models: LocalModel[];
}

export interface HuggingFaceSearchResult {
  repo_id: string;
  downloads: number;
  likes: number;
  gated: boolean;
}

export interface HuggingFaceVariant {
  repo_id: string;
  revision: string;
  files: string[];
  format: "gguf" | "safetensors";
  quantization: string | null;
  total_bytes: number;
  cached_bytes: number;
  gated: boolean;
  license_id: string | null;
  complete: boolean;
}

export interface HuggingFaceDownloadPreview {
  repo_id: string;
  revision: string;
  files: string[];
  total_bytes: number;
  cached_bytes: number;
  download_bytes: number;
}

export type HuggingFaceDownloadResult = ModelOperation & {
  snapshot_path: string;
  conversion_output_path: string;
};

export interface ModelConversionPreview {
  source: string;
  output: string;
  revision: string;
  architecture: string;
  quantization: string;
  source_bytes: number;
  required_free_bytes: number;
  toolchain_image: string;
  isolation: {
    network: false;
    source_read_only: true;
    credential_environment: string[];
    workspace_mounted: false;
    max_memory_bytes: number;
    max_cpu_count: number;
    max_processes: number;
    timeout_seconds: number;
  };
}

export interface Diagnostics {
  runtime_mode: string;
  production_ready_local_single_user_runtime: boolean;
  summary: Record<string, unknown>;
  disabled_capabilities: string[];
  counts: Record<string, number>;
  readiness: Record<string, boolean | CheckpointCaptureHealth>;
  missing_config: string[];
  provider_health: ProviderHealth[];
  scope_note: string;
}

/**
 * MEM-09 — GET /api/memory/integrity. The owner-started scan of every index and
 * projection the memory store depends on, including the conversation index
 * behind Search chats. Counts are drift, not errors: each one names rows that
 * disagree with the table that owns them.
 */
export interface MemoryIntegrity {
  ok: boolean;
  clean: boolean;
  active_memory_count: number;
  fts_count: number;
  stale_fts_count: number;
  missing_markdown_count: number;
  stale_projection_count: number;
  stale_graph_edge_count: number;
  checksum_mismatch_count: number;
  orphaned_markdown_count: number;
  failed_purge_location_count: number;
  project_path_inconsistency_count: number;
  text_search_engine: string;
  index_engine_mismatch_count: number;
  conversation_index_count: number;
  stale_conversation_index_count: number;
}

export interface CheckpointCaptureHealth {
  ok: boolean;
  stage: "ineligible" | "snapshot_ready" | "snapshot" | "commit";
  reason_code: string;
  display_path: string | null;
  checked_at: string;
  remediation: string;
}

export interface ModelProfile {
  profile_id: string;
  provider: string;
  model: string;
  default_state: string;
  local_only: boolean;
  requires_network: boolean;
  endpoint_kind: string;
  requires_egress_policy: boolean;
  requires_budget_policy: boolean;
  runtime_gate: string | null;
  off_machine: boolean;
  selected: boolean;
  connection_configured?: boolean;
  /** A separate organization-usage credential is stored; never its value. */
  usage_admin_configured?: boolean;
  prompt_cache_ttl: string | null;
  context_window_tokens?: number | null;
  /** "provider" | "config" — which source supplied the capacity above. */
  context_window_source?: string | null;
  configured?: boolean;
  /** Only API-key providers can accrue an API bill; local runtimes cannot. */
  billable?: boolean;
  /** Whether this exact provider/model profile supports a reasoning mode. */
  supports_reasoning?: boolean;
  /** Whether this exact profile accepts one of `reasoning_effort_values`. */
  supports_reasoning_effort?: boolean;
  /** Backend-advertised effort values; never inferred by the client. */
  reasoning_effort_values?: string[];
  /**
   * Backend-advertised reasoning *modes* (BUG-207 slice B). A provider declares
   * reasoning as an effort (OpenAI: low/medium/high) or as a mode (Anthropic:
   * adaptive). Offering only the first is why the composer had no reasoning
   * control at all for the provider that ships in the box.
   */
  reasoning_modes?: string[];
  /** Whether the provider can return a *summary* of its reasoning rather than raw text. */
  supports_reasoning_summary?: boolean;
  models_used?: number;
  turns_used?: number;
  total_tokens?: number;
  /** Decimal string, or null when no price is resolvable. Never "0" for unknown. */
  total_cost?: string | null;
  cost_currency?: string | null;
  price_source?: string | null;
  price_as_of?: string | null;
  readiness_state?: ModelReadinessState;
  readiness_summary?: string;
  readiness_reason_code?: string;
  readiness_remediation?: string;
  readiness_checked_at?: string | null;
  readiness_expires_at?: string | null;
  ready?: boolean;
}

/** Token usage and API cost for one conversation. Every figure names its source. */
export interface ContextUsage {
  session_id: string;
  profile_id: string | null;
  provider: string | null;
  model: string | null;
  used_tokens: number | null;
  context_window_tokens: number | null;
  context_window_source: string | null;
  /** "provider" once a turn has run, else "unavailable". */
  usage_source: string;
  billable: boolean;
  session_cost: string | null;
  provider_total_cost: string | null;
  currency: string | null;
  price_source: string | null;
  price_as_of: string | null;
  session_turns: number;
  session_input_tokens: number;
  session_output_tokens: number;
  /** BUG-21 — the individual rate components behind `session_cost`, read from
   *  the normalised registry. Each is independently sourced; a provider that
   *  publishes no cache rate leaves those null rather than having one inferred. */
  price_input_per_mtok?: string | null;
  price_output_per_mtok?: string | null;
  price_cache_write_per_mtok?: string | null;
  price_cache_read_per_mtok?: string | null;
  price_effective_from?: string | null;
  /** True on a billable provider with no exact rate for this model. The popover
   *  states **Unknown** and offers Configure → rather than implying it was free. */
  price_unknown?: boolean;
  /** Most recent automatic context-compaction outcome. Transcript turns stay
   *  unchanged; this describes only provider-context replay. */
  latest_compaction?: {
    status: "completed" | "failed";
    created_at: string;
    source_turn_count: number;
    estimated_input_tokens_before: number;
    estimated_summary_tokens: number;
    reason_code: string | null;
  } | null;
}

/** BUG-21 — one exact model's row in the Models → Pricing surface. */
export interface ModelPricingHistoryEntry {
  provider: string;
  model: string;
  source: string;
  effective_from: string;
  recorded_at: string;
  as_of: string | null;
  recorded_by: string | null;
  reason: string | null;
  currency: string;
  input_per_mtok: string;
  output_per_mtok: string;
  cache_write_per_mtok: string | null;
  cache_read_per_mtok: string | null;
}

export interface ModelPricingEntry {
  provider: string;
  model: string;
  profile_id: string | null;
  source: string | null;
  currency: string | null;
  input_per_mtok: string | null;
  output_per_mtok: string | null;
  cache_write_per_mtok: string | null;
  cache_read_per_mtok: string | null;
  effective_from: string | null;
  as_of: string | null;
  reviewed_at: string | null;
  review_due_at: string | null;
  review_status: "current" | "overdue" | "invalid" | null;
  recorded_at: string | null;
  recorded_by: string | null;
  reason: string | null;
  has_owner_override: boolean;
  history: ModelPricingHistoryEntry[];
}

export interface ModelPricingSyncState {
  provider: string;
  interval_hours: number;
  last_attempt_at: string | null;
  last_success_at: string | null;
  next_refresh_at: string | null;
  last_error: string | null;
  models_recorded: number;
  has_last_good: boolean;
  due: boolean;
  stale: boolean;
}

export interface ModelPricingView {
  entries: ModelPricingEntry[];
  sync: ModelPricingSyncState[];
  /** Overrides are administrator work; a non-gate-manager sees the registry
   *  read-only rather than an action that would be refused on submit. */
  can_override: boolean;
}

/** BUG-22 — what an export of one conversation would contain, reviewed first. */
export interface TranscriptExportMessage {
  role: string;
  text: string;
  timestamp: string | null;
  status: string | null;
}

export interface TranscriptExportFile {
  filename: string;
  media_type: string;
  byte_size: number;
  source: string;
}

export interface TranscriptExportManifest {
  session_id: string;
  title: string;
  created_at: string | null;
  message_count: number;
  file_count: number;
  files: TranscriptExportFile[];
  redaction_policy: string;
  formats: string[];
  messages: TranscriptExportMessage[];
}

/** BUG-24 — parked turns this account may continue, ids only. */
export interface ResumableTurn {
  approval_id: string;
  session_id: string;
  turn_id: string;
  tool_name: string;
  outcome_status: string;
  created_at: string;
}

export interface ResumableTurnsView {
  session_id: string | null;
  turns: ResumableTurn[];
}

export interface ModelsView {
  profiles: ModelProfile[];
  chat_profiles?: ModelProfile[];
  current_profile_id: string | null;
  current_model: string | null;
  advisor_profile_id: string | null;
  advisor_model_gate_state: string;
  // BUG-82 — readiness for the exact model a consult would call. The advisor is
  // a second model this runtime runs, and it used to have no probe, no state and
  // no chip: an owner could pin one with no credential, no credit or no running
  // runtime and learn about it only when a consult failed mid-turn.
  advisor_model?: string | null;
  advisor_readiness_state?: ModelReadinessState;
  advisor_readiness_summary?: string | null;
  advisor_readiness_remediation?: string | null;
  advisor_readiness_checked_at?: string | null;
  hosted_model_gate_state: string;
  private_network_model_gate_state: string;
  model_egress_allowlist_configured: boolean;
  remote_profile_count: number;
  fallback_sequence: string[];
  no_silent_hosted_fallback: boolean;
  ready_provider_count?: number;
}

export interface NativeUsageMetric {
  unit: string;
  used: string;
  limit: string | null;
  remaining: string | null;
  reset_interval: string | null;
  resets_at: string | null;
  scope: string;
  source: "provider";
}

export interface ProviderWeeklyUsage {
  profile_id: string;
  provider: string;
  display_name: string;
  observed: {
    input_tokens: number;
    output_tokens: number;
    cache_read_tokens: number;
    cache_write_tokens: number;
    total_tokens: number;
    requests: number;
    turns: number;
    compactions: number;
    known_cost: string | null;
    cost_currency: string | null;
    unpriced_models: string[];
    source: "raiker_ledger";
    window: "rolling_7_days";
  };
  owner_budget: number | null;
  native: {
    status: "available" | "unavailable" | "not_configured" | "not_supported" | "not_checked";
    reason_code: string | null;
    checked_at: string | null;
    expires_at: string | null;
    metrics: NativeUsageMetric[];
  };
}

export interface ProviderWeeklyUsageView {
  window: "rolling_7_days";
  providers: ProviderWeeklyUsage[];
}

/** Read-only status of one governed service connector (web-app task 4). Every
 * field derives from stored/config state — the view never reaches the network
 * and never exposes a credential value (only whether one is set). */
export interface ConnectorView {
  connector_id: string;
  display_name: string;
  capability: string;
  gate_state: string;
  capability_enabled: boolean;
  decision_mode: string;
  credential_env: string;
  credential_configured: boolean;
  egress_host: string;
  egress_allowed: boolean;
  actions: string[];
  kind: string;
}

export interface ConnectionsView {
  connectors: ConnectorView[];
  connector_egress_allowlist_configured: boolean;
}

export interface StoreConnector {
  connector_id: string;
  display_name: string;
  category: string;
  description: string;
  auth_type: "oauth2" | "api_key";
  host: string;
  installed: boolean;
  enabled: boolean;
  auth_status: "connected" | "reauth_required" | "not_connected";
  vault_configured: boolean;
  activity_status: "idle" | "processing" | "completed" | "failed";
  active_operation: string | null;
  last_invoked_at: string | null;
  operations: Array<{
    operation_id: string;
    method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
    path: string;
    description: string;
    requires_confirmation: boolean;
  }>;
}

export interface ConnectorStoreView {
  connectors: StoreConnector[];
  count: number;
  vault_configured: boolean;
}

/** On-demand listing of the models one provider serves. Failures come back as an
 * honest status with an empty list — the backend never fabricates model names. */
export interface ProviderModelList {
  profile_id: string;
  provider: string;
  status: "available" | "policy_denied" | "unsupported" | "unavailable";
  reason_code: string | null;
  models: string[];
}

/** Outcome for one provider in an explicit connected-catalogue refresh. */
export interface ProviderCatalogueRefresh {
  providers: Array<{
    profile_id: string;
    provider: string;
    status: "available" | "policy_denied" | "unsupported" | "unavailable";
    reason_code: string | null;
    model_count: number;
  }>;
}

/** Status of the locally installed Codex client session. No account identifier,
 * token, or login URL is exposed to the browser UI. */
export interface CodexSubscriptionStatus {
  connection_status: "connected" | "signed_out" | "login_pending" | "codex_missing";
  plan_type: string | null;
}

/** A project is an organizing scope (workspace-contained subpath + its
 * sessions/checkpoints), never an authority — selecting one grants nothing. */
export interface ProjectView {
  project_id: string;
  name: string;
  root_subpath: string;
  created_at: string;
  session_count: number;
  selected: boolean;
  parent_id: string | null;
  path: string;
  is_archived: boolean;
  archived_at: string | null;
  /** Which kind of root, and what to call it. On the list rather than fetched
   *  per card, because the delete confirmation must say whether a folder
   *  survives before the owner opens anything. */
  root_kind: "managed" | "attached";
  root_label: string;
}

export interface ProjectsList {
  projects: ProjectView[];
  active_project_id: string | null;
}

/**
 * One repository the Build workspace can point a coding chat at. A reference
 * only: it carries no credential and grants no capability. A `local` repository
 * is a workspace-contained subpath; a `github` repository is an `owner/repo`
 * coordinate read through the brokered `github_read` tool.
 */
export interface CodeRepo {
  repo_id: string;
  kind: "local" | "github";
  label: string;
  selected: boolean;
  created_at: string;
  local_subpath: string | null;
  local_exists: boolean;
  github_owner: string | null;
  github_repo: string | null;
  branch: string | null;
}

export interface CodeReposView {
  repos: CodeRepo[];
  selected_repo_id: string | null;
  // What the connector_github_runtime gate currently permits, so the page can
  // say whether a connected GitHub repository is actually readable.
  github_gate_state: string;
  github_decision_mode: string;
  github_token_configured: boolean;
  note: string;
}

// B9 — the repository code map's own state. Counts and governance only: this
// shape deliberately carries no path and no symbol, so the status call cannot
// become a listing of the owner's tree.
export interface CodeMapStatus {
  capability: string;
  gate_state: string;
  decision_mode: string;
  enabled: boolean;
  repository: string;
  repo_id: string;
  status: "indexed" | "partial" | "not_indexed" | "failed";
  reason_code: string;
  file_count: number;
  symbol_count: number;
  edge_count: number;
  languages: Record<string, number>;
  skipped: Record<string, number>;
  limits_hit: string[];
  built_at: string | null;
  updated_at: string | null;
}

/**
 * GET /api/code/map/paths — completion for an `@`-mention (B19).
 *
 * `status` is `"success"` with the matching paths, or a named refusal:
 * `code_map_not_built` when the owner has never indexed the repository, or a
 * governance reason when the `code_map_indexing` capability is off. The menu
 * shows the reason rather than an empty list, because "nothing matched" and
 * "nothing could match" send the owner to different places.
 */
export interface CodeMapPaths {
  status: string;
  repository?: string;
  fragment?: string;
  count?: number;
  paths?: Array<{ path: string; language: string }>;
  error?: { type?: string; message?: string } | null;
}

export interface ProjectDetail {
  project: ProjectView;
  sessions: SessionSummary[];
  checkpoints: Checkpoint[];
  context: ProjectContext;
}

export interface ProjectContext {
  instructions: string;
  attachment_ids: string[];
  memory_enabled: boolean;
  memory_mode: "inherit" | "enabled" | "disabled";
}

/** A node in the project tree hierarchy. Recursive — each node may have
 * children. Represents an active (non-archived) project/folder. */
export interface ProjectTreeNode {
  project_id: string;
  name: string;
  root_subpath: string;
  created_at: string;
  session_count: number;
  children: ProjectTreeNode[];
}

export interface EventEntry {
  event_id: string;
  session_id: string;
  turn_id: string | null;
  event_type: string;
  actor: string;
  timestamp: string;
  risk_level: string | null;
  summary: string | null;
  machine_identity?: IdentityView | null;
  priority: string | null;
  scheduled_at: string | null;
  recurrence: string | null;
  reminder_at: string | null;
}

export interface Checkpoint {
  checkpoint_id: string;
  session_id: string;
  turn_id: string | null;
  task_id: string | null;
  checkpoint_type: string;
  created_at: string;
  summary: string | null;
  last_event_id: string | null;
  can_restore_state: boolean;
  can_restore_files: boolean;
}

/**
 * What branching a conversation from one checkpoint would seed (GAP-CHAT C14).
 * `requires_approval` is always false: a branch writes no workspace file, which
 * is the property that separates it from a restore.
 */
export interface ConversationBranchPlan {
  status: string;
  checkpoint_id: string;
  source_session_id: string;
  summary: string;
  memory_candidate_count: number;
  can_execute: boolean;
  requires_approval: boolean;
}

/** The branch that was created. The source conversation is unchanged. */
export interface ConversationBranch {
  status: string;
  checkpoint_id: string;
  source_session_id: string;
  session_id: string;
  title: string;
  summary: string;
  memory_candidate_count: number;
  seed_manifest_path: string;
}

/** Where a conversation came from. `source_session_id` is null for a root. */
/**
 * The result of an owner-guided compaction (backlog #9).
 *
 * `compacted: false` is a state rather than a failure: a mark already covered by
 * an earlier boundary has nothing behind it to summarise, and the reason code
 * says which case it was.
 */
/** One question the model asked the owner mid-turn (ADD-22). */
export interface OwnerQuestion {
  question: string;
  header: string;
  options: { label: string; description: string }[];
  multiSelect?: boolean;
}

/** The result of answering one. Nothing was granted, so nothing was executed. */
export interface OwnerQuestionAnswered {
  approval_id: string;
  status: string;
  answered: number;
  resume?: { resumable?: boolean; session_id?: string | null; turn_id?: string | null };
}

export interface ConversationCompaction {
  session_id: string;
  compacted: boolean;
  reason_code?: string;
  through_turn_id?: string | null;
  source_turn_count?: number;
  estimated_summary_tokens?: number;
  provider?: string;
  model?: string;
  created_at?: string;
}

export interface ConversationBranchOrigin {
  session_id: string;
  source_session_id: string | null;
  source_title: string | null;
  forked_from_checkpoint_id: string | null;
  summary: string;
  created_at: string;
}

/**
 * Metadata-only preflight for a checkpoint restore. `files` carries content
 * addresses and sizes; the server never sends file content to the browser, and
 * computing a plan performs no restore.
 */
export interface RestorePlanFile {
  workspace_path: string;
  op: string;
  pre_image_sha256: string | null;
  pre_image_size: number;
  current_sha256: string | null;
  current_size: number;
  changed: boolean;
  changed_by_other_principal: boolean;
}

export interface RestorePlan {
  status: string;
  checkpoint_id: string;
  session_id: string;
  checkpoint_created_at: string;
  can_execute: boolean;
  requires_approval: boolean;
  files: RestorePlanFile[];
  restore_content_count: number;
  delete_count: number;
  skip_count: number;
  changed_count: number;
  touches_other_principal: boolean;
}

/**
 * POST /api/checkpoints/{id}/restore — the governed request, not the restore.
 * The server raises an approval and performs nothing; `executes_action` is
 * always false, and `critical` is true when the rewind would overwrite work
 * last changed by a different principal (human-only, step-up lifecycle).
 */
export interface RestoreRequestResult {
  status: string;
  approval_id: string;
  action_id: string;
  checkpoint_id: string;
  critical: boolean;
  executes_action: boolean;
  restore_content_count: number;
  delete_count: number;
  skip_count: number;
}

/**
 * BUG-231 — one redacted audit export. Metadata only: the manifest hash is
 * taken over the exact event ids and scope, which is what lets someone outside
 * Raiker say whether the file they were handed is the one it produced.
 */
export interface AuditExportView {
  export_id: string;
  manifest_hash: string;
  event_count: number;
  redacted: boolean;
  first_timestamp: string | null;
  last_timestamp: string | null;
  exported_by: string | null;
  created_at: string;
}

export interface AuditExportResult {
  ok: boolean;
  export_id: string;
  manifest_hash: string;
  event_count: number;
  redacted: boolean;
  first_event_id: string | null;
  last_event_id: string | null;
  export_path: string | null;
}

/**
 * One extension's lifecycle, as four independent server-derived facts. `usable`
 * is a conclusion, never a claim the browser makes on its own; `blocked_reason`
 * names the first unmet condition.
 */
export interface ExtensionView {
  extension_id: string;
  kind: string;
  display_name: string;
  category: string;
  installed: boolean;
  connected: boolean;
  enabled: boolean;
  usable: boolean;
  blocked_reason: string | null;
  detail: string;
  capability: string | null;
  gate_state: string | null;
  decision_mode: string | null;
  egress_host: string | null;
  egress_allowed: boolean | null;
  transport: string | null;
  monitor_state: string | null;
  tool_count: number;
  last_activity_at: string | null;
}

export interface ExtensionsOverview {
  extensions: ExtensionView[];
  counts: {
    total: number;
    installed: number;
    connected: number;
    enabled: number;
    usable: number;
  };
  vault_configured: boolean;
  connector_egress_allowlist_configured: boolean;
  deferred: Array<{ kind: string; status: string; detail: string }>;
}

export interface ProjectFile {
  workspace_path: string;
  name: string;
  is_directory: boolean;
  size_bytes: number;
  modified_at: string;
  depth: number;
}

export interface FileProvenanceEntry {
  turn_id: string | null;
  action_id: string | null;
  session_id: string;
  capability: string;
  principal_id: string;
  capture_status: string;
  existed_before: boolean;
  pre_image_size: number;
  created_at: string;
}

export interface ProjectFilesView {
  project_id: string;
  root_subpath: string;
  root_exists: boolean;
  files: ProjectFile[];
  truncated: boolean;
  provenance: Record<string, FileProvenanceEntry[]>;
  note: string;
}

/** Redacted, copyable support bundle. Shape is intentionally loose: the server
 *  owns which readiness facts it includes, and the UI renders it verbatim. */
export interface DiagnosticsExport {
  generated_at: string;
  scope: string;
  runtime_mode: string;
  counts: Record<string, number>;
  missing_config: string[];
  disabled_capabilities: string[];
  gates: Array<{
    capability: string;
    state: string;
    decision_mode: string;
    runtime_enabled: boolean;
  }>;
  note: string;
  [key: string]: unknown;
}

export interface SessionSummary {
  session_id: string;
  title: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  turn_count: number;
  // Conversation organisation: a per-session pin/bookmark flag. Pinned
  // sessions surface first in the Sessions list. Organizing label only.
  pinned: boolean;
  // Conversation organisation remainder: per-session tags. Organizing labels
  // only — like `pinned`, they grant nothing. Storage returns them sorted.
  tags: string[];
  // The organizing project this chat sits in, or null. A chat can be moved in
  // or out; the project only bounds the context the chat receives.
  project_id: string | null;
  // Soft-archive state. Archiving is reversible and never deletes transcripts,
  // events, checkpoints, or permissions.
  archived: boolean;
  archived_at: string | null;
  // Where the session came from: "chat" for a conversation the owner typed,
  // "task" for the server-owned session a task run executes in. Provenance
  // only — a task session stays readable in Sessions and from Tasks.
  origin?: string;
  // RAIKER-2020 — set only on a search result: the exchange that matched and
  // the turn it belongs to, so a result can say *why* it matched rather than
  // only that it did. Empty on a plain listing.
  match_snippet?: string;
  match_turn_id?: string;
}

export interface TurnSummary {
  turn_id: string;
  session_id: string;
  turn_type: string;
  status: string;
  prompt_text: string | null;
  created_at: string;
  completed_at: string | null;
  summary: string | null;
  /**
   * BUG-215 — how much of its own working this turn produced, and the working
   * itself when the owner has asked for it to be kept.
   *
   * The pair is what makes a re-opened turn honest. `reasoning_chars === 0`
   * means the turn produced none; `reasoning_chars > 0` with `reasoning === null`
   * means it did and the working was not retained — which the transcript says
   * plainly instead of showing nothing and implying nothing happened.
   */
  reasoning_chars?: number;
  reasoning?: string | null;
  /**
   * Backlog #25 — the turn's tool calls, rebuilt from the durable record.
   *
   * Live, these arrive on the stream; a reload had no stream and lost them, so
   * a reopened transcript showed the answer and nothing about how it was
   * reached. Each entry is the same payload shape a `kind: "tool"` stream event
   * carries, rendered server-side by the same presentation function, so the two
   * sources merge into one row rather than two.
   */
  tool_rows?: Array<Record<string, unknown>>;
}

// GET /api/sessions/{id} — raiker/control/dashboard.py SessionDetailView.to_dict()
export interface SessionDetail {
  session: SessionSummary;
  turns: TurnSummary[];
  parked_approvals?: Array<{
    approval_id: string;
    turn_id: string;
    tool_name: string;
    created_at: string;
  }>;
}

// GET /api/turns/{id} — raiker/control/dashboard.py TurnDetailView.to_dict()
export interface TurnDetail {
  turn: TurnSummary;
  events: EventEntry[];
}

export interface AuthSession {
  token: string;
  session_id: string;
  principal_id: string;
  expires_at: string | null;
}

// raiker/control/dashboard.py ApprovalView.to_dict()
export interface IdentityView {
  principal_id: string;
  principal_type: string;
  display_name: string;
  subject: string | null;
  turn_id: string | null;
  key_id: string | null;
  issued_at: string | null;
  expires_at: string | null;
  state: string;
}

export interface ApprovalView {
  approval_id: string;
  action_id: string;
  status: string;
  tool_name: string;
  capability: string;
  risk_level: string;
  session_id: string;
  turn_id: string | null;
  created_at: string;
  age_seconds: number | null;
  requires_approval: boolean;
  expires_at: string | null;
  is_expired: boolean; // server-calculated snapshot; resolution re-checks the TTL
  executes_action: boolean; // true only for an approved, single-use connector write intent
  critical: boolean; // server-supplied: needs elevated, human-only lifecycle
  resolved_by: string | null;
  proposed_by?: IdentityView;
  approved_by?: IdentityView | null;
  machine_identity?: IdentityView | null;
  // ADD-02 — where this decision sits in the batch of tool calls its turn
  // proposed. 1 / 1 for an ordinary approval; 2 / 3 means two more decisions are
  // queued behind this one on the same turn.
  queue_position: number;
  queue_total: number;
}

// raiker/control/dashboard.py ApprovalDetailView.to_dict()
export interface ApprovalDetailView {
  approval: ApprovalView;
  arguments: Record<string, unknown>;
  diff: string | null;
  diff_path: string | null;
  // `connector_request` has always been produced by the server for a
  // `connector_write`; it was missing here, so the union claimed a shape the
  // backend does not only produce. `git_change` is B11's: a commit's file list
  // and diff, or the two refs a branch moves between.
  // `checkpoint_restore` is BUG-230's: the per-file rewind plan, recomputed by
  // the server at read time so the decision is made on what will actually run.
  preview_kind:
    | "file_diff"
    | "patch"
    | "git_change"
    | "connector_request"
    | "checkpoint_restore"
    | "arguments";
  metadata_only_notice: string;
  // Server-computed: does pressing Approve actually perform this action?
  executes_on_approval: boolean;
  execution_evidence: {
    principal_id?: string;
    returncode?: number;
    stdout_bytes?: number;
    stderr_bytes?: number;
    stdout?: string;
    stderr?: string;
    truncated?: boolean;
    output_redacted?: boolean;
  };
}

// POST /api/approvals/{id}/resolve response.
export interface ResolveApprovalResult {
  approval_id: string;
  action_id: string;
  status: string;
  executes_action: boolean;
  reason: string;
  proposed_by?: IdentityView | null;
  approved_by?: IdentityView | null;
  machine_identity?: IdentityView | null;
  connector_result?: Record<string, unknown>;
  // Present when an approved mutation was carried out by the execution relay.
  execution?: {
    capability: string;
    path: string | null;
    returncode?: number;
    stdout_bytes?: number;
    stderr_bytes?: number;
    stdout?: string;
    stderr?: string;
    truncated?: boolean;
    output_redacted?: boolean;
    // BUG-62 — where the executed action landed, for capabilities whose result
    // is a row rather than a file: the task that now exists, the project a
    // conversation was moved into.
    receipt?: { kind: string; title: string; href: string; label: string };
    // B11 — one sentence naming what the execution did, for a capability whose
    // result is neither a file nor a row (the branch created, the commit made).
    summary?: string;
    checkpoint_capture?: CheckpointCaptureHealth;
  };
  // B2 — whether a turn was parked on this approval and can now pick up again.
  // ADD-02 adds the batch counters and how many calls the resume still owes.
  resume?: {
    resumable: boolean;
    session_id?: string;
    turn_id?: string;
    queue_position?: number;
    queue_total?: number;
    queued_calls?: number;
  };
}

export interface ResolveCriticalApprovalResult {
  approval_id: string;
  status: string;
  decision: string;
  message: string;
  executes_action: boolean;
}

// Approval proposal carried on an AgentResponse when status === "needs_approval".
// Mirrors the `approval` dict built in raiker/runtime/orchestrator.py. Nothing has
// been executed at this point; `expected_effect` states what approving will do.
export interface ApprovalInfo {
  action_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  risk_level: string;
  reasons: string[];
  message: string;
  expected_effect?: string;
  approval_id?: string;
  // True when the turn's working state was parked, so resolving this approval
  // continues the same turn rather than costing a re-prompt.
  resumable?: boolean;
  // ADD-02 — the batch this decision belongs to, and how many of its calls are
  // still queued behind it.
  queue_position?: number;
  queue_total?: number;
  queued_calls?: number;
}

// raiker.contracts.models.AgentResponse.to_dict()
export interface AgentResponse {
  request_id: string;
  session_id: string;
  turn_id: string;
  status: string; // queued|running|completed|failed|denied|needs_approval (see RESPONSE_STATUSES)
  message: string;
  events_path?: string | null;
  checkpoint_path?: string | null;
  approval?: ApprovalInfo | null;
  last_event_id?: string | null;
}

// raiker.contracts.streaming.StreamEvent serialized over SSE (see routes_prompts._sse).
export type StreamKind =
  "lifecycle" | "text_delta" | "reasoning_delta" | "tool" | "final" | "error";

/** One page of the user guide, as the product lists it (BUG-208 slice A). */
export interface GuideSectionSummary {
  slug: string;
  title: string;
  summary: string;
}

/** The sections this install carries. `available` is false when a build shipped none. */
export interface GuideIndex {
  available: boolean;
  sections: GuideSectionSummary[];
  reason_code: string;
}

/** One section's Markdown, rendered by the client with the shared component. */
export interface GuideSection extends GuideSectionSummary {
  markdown: string;
}

export interface StreamEvent {
  kind: StreamKind;
  text: string;
  event_type: string;
  payload: Record<string, unknown>;
  response: AgentResponse | null;
  // B17/C13 — the conversation and turn this chunk belongs to, present on every
  // chunk of a prompt stream. A brand-new chat learns its own session id from
  // the first event, which is what lets Stop and steer reach the very first
  // turn instead of only later ones.
  session_id?: string | null;
  turn_id?: string | null;
}

// raiker/control/dashboard.py TaskView.to_dict()
export interface TaskView {
  task_id: string;
  session_id: string;
  status: string;
  title: string;
  objective: string;
  current_step: string | null;
  progress_percent: number | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  summary: string | null;
  priority?: string | null;
  scheduled_at?: string | null;
  recurrence?: string | null;
  reminder_at?: string | null;
  // Project-scoped schedules: the project this task/schedule was created
  // under, or null when it was created outside every project.
  project_id: string | null;
  parent_task_id?: string | null;
  model_profile?: string | null;
  model?: string | null;
  attachments?: PromptAttachment[];
}

// POST /api/interrupts response (raiker/api/routes_prompts.py).
export interface InterruptResult {
  applied: { task_id: string; result: string }[];
  safe_boundary: boolean;
  // B17/C13 — what the same request did to the *turn* streaming in this
  // conversation, which is not one of the tasks in `applied`. Null when the
  // request named a specific task, or when the action reaches tasks only.
  turn_control?: { action: "stop" | "steer"; queued: number } | null;
}

// One prompt attachment: a workspace path, or an image/document previously
// uploaded through POST /api/attachments (referenced by id; the bytes stay
// server-side).
export type PromptAttachment =
  | { type: "path"; path: string }
  | { type: "image"; attachment_id: string }
  | { type: "document"; attachment_id: string };

export interface PromptRequestBody {
  text: string;
  // Client-reported provenance; no audio or transcript metadata crosses this boundary.
  input_mode?: "typed" | "dictated" | "mixed";
  // Which composer sent this prompt. It selects the operating protocol the turn
  // runs under — Build adds the engineering protocol, Chat does not — and grants
  // nothing: gates, capabilities and approvals are identical either way.
  surface?: "chat" | "build";
  // The project this turn may retrieve inside. Required by Build and rejected
  // for Chat: the two surfaces have genuinely different boundaries, and the
  // server refuses a turn that leaves the boundary for it to guess.
  project_id?: string;
  session_id?: string;
  planning_mode?: string;
  approval_mode?: string;
  model_profile?: string;
  model?: string;
  reasoning_effort?: string;
  max_tool_calls?: number;
  // BUG-70 — a turn-scoped capability posture (Build's Plan / Edit chips). The
  // server accepts only the tightening modes `ask` and `deny`, and applies them
  // to this turn alone; the owner's standing decision modes are untouched.
  capability_modes?: Record<string, string>;
  attachments?: PromptAttachment[];
}

// GET /api/hooks (raiker/control/dashboard.py → list_hooks).
//
// Hooks are the one extension surface whose backend really enforces something —
// a `PreToolUse` deny short-circuits to a denied policy decision — so the view
// has to be exact about the three ways a configured hook can still do nothing:
// its file did not parse, its event is never dispatched by this build, or its
// event carries no decision the runtime honours.
export interface HookHandlerView {
  id: string;
  type: string;
  /** The argv or builtin name, already joined for display. */
  target: string;
  timeout_ms: number;
  decision_authority: boolean;
  /** False only for a builtin this build does not ship: the rule matches, the
   *  handler raises, and nothing is enforced. */
  available: boolean;
}

export interface HookRuleView {
  rule_id: string;
  event: string;
  event_summary: string;
  matcher: string;
  if_guard: string | null;
  scope: string;
  source: string | null;
  /** False when this build never emits the event, so the rule cannot fire. */
  dispatched: boolean;
  /** True only when the event is one whose decision the runtime honours *and* a
   *  handler on it holds decision authority. */
  can_decide: boolean;
  handlers: HookHandlerView[];
}

export interface HookSourceView {
  path: string;
  scope: string;
  exists: boolean;
  loaded: boolean;
  rule_count: number;
  /** Why the file contributed nothing. Null when it loaded or is absent. */
  error: string | null;
}

export interface HookEventView {
  event: string;
  summary: string;
  dispatched: boolean;
  can_decide: boolean;
}

export interface HookActivityView {
  event_id: string;
  event_type: string;
  session_id: string;
  timestamp: string;
  summary: string | null;
}

export interface HooksView {
  /** False when nothing is configured **or** the owner turned hooks off. */
  active: boolean;
  /** The owner's off switch. Rules stay listed while it is on. */
  disabled: boolean;
  rule_count: number;
  rules: HookRuleView[];
  sources: HookSourceView[];
  failed_sources: HookSourceView[];
  events: HookEventView[];
  /** The builtin handler names this build actually has. */
  builtins: string[];
  activity: HookActivityView[];
  activity_counts: Record<string, number>;
}

// POST /api/attachments response (raiker/api/routes_attachments.py) —
// metadata only; the stored bytes are never echoed back.
export interface UploadedAttachment {
  ok: boolean;
  attachment_id: string;
  kind: string;
  filename: string;
  media_type: string;
  byte_size: number;
  sha256: string;
}

// GET /api/sessions/{id}/attachments/{id}/preview — raiker/runtime/attachment_preview.py
// AttachmentPreview.to_dict(). View-only and inert: `text` is source text (the
// client's escape-first renderer turns Markdown into markup, never the server),
// `rows` are spreadsheet cell values, and `pdf_url` / `image_url` are
// same-origin authorized paths fetched with the session bearer token — never an
// external URL, and never the bytes themselves.
export interface AttachmentPreview {
  attachment_id: string;
  session_id: string;
  filename: string;
  media_type: string;
  kind: "text" | "markdown" | "table" | "pdf" | "image" | "unavailable";
  byte_size: number;
  text: string;
  rows: string[][];
  truncated: boolean;
  pdf_url: string | null;
  image_url: string | null;
  unavailable_reason: string | null;
}

/**
 * BUG-27 — one resolved source passage, or the stated reason there is not one.
 *
 * `status` is the whole contract. Only `resolved` carries a located passage;
 * every other value is a fact the owner is entitled to see instead of an empty
 * pane, and the inspector states each one in words:
 *
 * - `no_provenance` — the record never stored where it came from.
 * - `source_deleted` — the conversation or turn is gone.
 * - `source_changed` — the source is readable, but no longer contains the
 *   passage, so the excerpt is shown without a highlight rather than with a
 *   guessed one.
 * - `unsupported_source` — a real, readable source with no text offset to open
 *   it at (an image, a PDF, a spreadsheet).
 * - `not_authorized` — this account may not read the source.
 *
 * `highlight_start` is `-1` whenever there is no located passage.
 */
export interface SourceExcerptView {
  ok?: boolean;
  status:
    | "resolved"
    | "no_provenance"
    | "source_deleted"
    | "source_changed"
    | "unsupported_source"
    | "not_authorized";
  kind: string;
  title: string;
  excerpt: string;
  highlight_start: number;
  highlight_length: number;
  session_id: string;
  turn_id: string;
  attachment_id: string;
  truncated: boolean;
  // How the passage was located. C6/C4 adds three: `answer_quote` (the sentence
  // carrying the citation found verbatim in the source — the narrowest honest
  // claim available), `recorded_passage` (material Raiker holds no second copy
  // of, shown as the exact text that reached the model), and `whole_source`
  // (the turn read all of it, so marking every character would say nothing).
  resolution_method:
    | "stored_coordinates"
    | "matching_text"
    | "answer_quote"
    | "recorded_passage"
    | "whole_source"
    | "";
  // BUG-245 — the exchanges this one call returned, as openable coordinates.
  // Built by the runtime from the tool result it read, never from anything the
  // model wrote, and served with the passage rather than with the chip: only an
  // opened source needs them. Absent for every source that is not a set of
  // conversation hits, and optional so older payloads stay valid.
  anchors?: SourceAnchorView[];
}

// One exchange a cited search returned. Four coordinates and no text: the
// passage already carries what was read, and this carries only where from.
export interface SourceAnchorView {
  session_id: string;
  turn_id: string;
  title: string;
  created_at: string;
  /** Which surface it happened on, so the link opens where the work is. */
  origin: string;
}

// C6/C4 — raiker/runtime/turn_sources.py TurnSource.to_view(). One thing a turn
// actually read: a governed tool result, or a file the owner attached. Labels
// and locators only — the passage behind a source is fetched on open, so a
// history load never carries a transcript's worth of read material.
export interface TurnSourceView {
  source_id: string; // "s1", "s2", … — the marker the model was handed
  ordinal: number;
  kind: string; // file | attachment | email | calendar | web | memory | …
  title: string;
  locator: string;
  tool_name: string;
  detail: string;
  attachment_id: string;
  turn_id: string;
  openable: boolean;
}

/**
 * C17 — GET /api/sessions/{id}/recall. Which approved memories the turns of
 * this conversation were actually given. Ambient recall leaves no citation to
 * click, so this is the only way the transcript can say what was remembered —
 * and the only place the owner can correct or forget it at the moment it
 * mattered.
 */
export interface RecalledMemory {
  memory_id: string;
  turn_id: string;
  text: string;
  scope: string;
  pinned: boolean;
}

export interface SessionRecallView {
  ok: boolean;
  session_id: string;
  memories: RecalledMemory[];
}

// GET /api/sessions/{id}/sources
export interface TurnSourcesView {
  session_id: string;
  sources: TurnSourceView[];
}

// GET /api/sessions/{id}/turns/{turn}/sources/{source}/excerpt — the source view
// above plus the resolved passage, in the same shape (and with the same honest
// statuses) as SourceExcerptView.
export type TurnSourceExcerptView = TurnSourceView &
  SourceExcerptView & { ok: boolean };

// GET /api/sessions/{id}/attachments — metadata only, so a reloaded chat can
// redraw the attachment chips its transcript does not persist.
export interface SessionAttachment {
  attachment_id: string;
  turn_id: string;
  kind: string;
  filename: string;
  media_type: string;
  byte_size: number;
  previewable: boolean;
  source: "uploaded" | "generated";
  created_at: string;
}

export interface SessionAttachmentsView {
  session_id: string;
  files: SessionAttachment[];
}

export interface InterruptRequestBody {
  session_id: string;
  task_id?: string;
  all?: boolean;
  action_type?: string;
  reason?: string;
  steer_text?: string;
}

// Reliable memory controls (backlog item 3): user-facing view of one approved
// memory entry — provenance, scope, sensitivity, confidence, retention, pin.
/**
 * BUG-244 — what an import would change, read before anything is written.
 *
 * A record is a duplicate when the workspace already holds the same sentence
 * *at the same scope*: the same sentence at `project` and at `global` is two
 * records an owner may genuinely want. `memory_id` names the record a duplicate
 * would be a copy of, and is empty when the repeat is inside the file itself.
 */
export interface MemoryImportPreview {
  ok: boolean;
  total: number;
  new_count: number;
  duplicate_count: number;
  duplicates: Array<{ index: number; text: string; scope: string; memory_id: string }>;
}

/** What the import actually did. `count` is what changed, not what was offered. */
export interface MemoryImportResult {
  ok: boolean;
  count: number;
  reviewed: number;
  imported: number;
  skipped_duplicates: number;
  relationship_proposals: number;
}

export interface MemoryControlView {
  memory_id: string;
  text: string;
  scope: string;
  sensitivity: string;
  memory_type: string;
  created_at: string;
  tags: string[];
  source: string;
  provenance: Record<string, unknown>;
  confidence: number;
  trust_score: number;
  retention: string;
  approval_state: string;
  pinned: boolean;
  search_enabled: boolean;
  expires_at: string | null;
  updated_at: string | null;
  last_used_at: string | null;
}

export interface MemoryProposal {
  candidate_id: string;
  source_event_id: string;
  memory_type: string;
  scope: string;
  text: string;
  sensitivity: string;
  confidence: number;
  decision: string;
  created_at: string;
}

export interface MemoryRelationshipProposal {
  candidate_id: string;
  subject_name: string;
  subject_type: string;
  predicate: string;
  object_name: string;
  object_type: string;
  evidence_memory_id: string;
  evidence_text: string;
  confidence: number;
  extractor_version: string;
  decision: "needs_user_review";
  created_at: string;
}

export interface MemoryHistoryEvent {
  audit_id: string;
  action: string;
  actor_id: string;
  created_at: string;
  details: Record<string, unknown>;
}

export interface EmbeddingSpaceView {
  backend_id: string;
  kind: "lexical_fallback" | "local_model" | "provider";
  model: string;
  dimensions: number;
  semantic: boolean;
  reason_code: string;
  /**
   * MEM-10 — whether a *question* can be embedded into this space at read time.
   *
   * `semantic` and this are two different claims and only the first is true
   * today: a workspace can build a semantic space and recall selects it, but
   * embedding the query means calling the provider on every search, which needs
   * its own gated path rather than a shortcut. Until it has one the vector leg
   * is dropped and matching is still lexical — so a card that reads `semantic`
   * as "matches meaning" would say something the retrieval does not do.
   *
   * Present only on `retrieval`; a listed space carries no read-path claim.
   */
  query_embeddable?: boolean;
}

export interface MemorySettingsView {
  incognito: boolean;
  // MEM-03 — the owner's selection ("auto" or an exact model label), what that
  // resolved to, and the spaces this workspace really holds vectors in.
  embedding_backend: string;
  retrieval: EmbeddingSpaceView;
  spaces: EmbeddingSpaceView[];
  // MEM-10 — `spaces` is read from the vectors that exist, so a default install
  // has nothing semantic to offer. These two say what it would take: which
  // embedding models this install could call, and how many approved memories
  // are waiting to be embedded into one.
  embedding_providers: EmbeddingProviderView[];
  unindexed_memories: number;
  unindexed_file_chunks: number;
  /** Exact cosine ranking stays in force for small corpora; larger spaces use
   * approximate candidate lookup followed by exact re-ranking. */
  vector_search_strategy?: "exact_then_approximate";
  vector_search_exact_limit?: number;
}

// raiker/vector/backends.py embedding_capable_profiles(). A description of what
// the model profiles declare — nothing here has performed egress or checked a
// credential; the run still goes through model_provider_runtime.
export interface EmbeddingProviderView {
  profile_id: string;
  provider: string;
  model: string;
  // The label the vectors will carry, and so the space that becomes selectable.
  space: string;
  local_only: boolean;
  // The next governed run is capped at 500 total items. Counts are per vector
  // space so the confirmation always describes the model the owner selected.
  unindexed_memories?: number;
  unindexed_file_chunks?: number;
  pending_count?: number;
  requires_network: boolean;
}

// raiker/control/dashboard.py ObservationView.to_dict(). MEM-04 — metadata
// about material the runtime saw while it worked. There is no field carrying
// the material itself, and there is not meant to be one: an observation exists
// so recall is possible without a second ungoverned copy of everything read.
export interface ObservationView {
  observation_id: string;
  session_id: string;
  turn_id: string;
  tool_name: string;
  source_type: string;
  summary: string;
  sensitivity: string;
  retention: string;
  capture_status: "captured" | "skipped";
  skip_reason: string;
  promotable_to_memory: boolean;
  content_sha256: string;
  content_bytes: number;
  artifact_ref: string | null;
  source_event_id: string;
  created_at: string;
  expires_at: string;
  gist_status: string;
  gist_summary: string;
  gist_id: string;
}

export interface ObservationsView {
  ok: boolean;
  observations: ObservationView[];
  captured: number;
  skipped: number;
  gists_pending: number;
  // MEM-07 — the observation ids whose retention class already says they are
  // due. Raiker runs no cleanup daemon on purpose; being shown what is due and
  // confirming it is the deliberate alternative, and it was never built.
  due_for_expiry: string[];
}

// raiker/control/dashboard.py BrainView.to_dict(). Nodes and edges are stored
// runtime relationships; the UI may add clearly labelled illustrative motion.
export interface BrainNode {
  node_id: string;
  node_type: string;
  label: string;
  status: string;
  detail: string | null;
  progress_percent: number | null;
  is_real: boolean;
}

export interface BrainEdge {
  source: string;
  target: string;
  relationship: string;
  is_active: boolean;
  relationship_id?: string | null;
  evidence_memory_id?: string | null;
  owner_can_reject?: boolean;
}

export interface BrainView {
  generated_at: string;
  nodes: BrainNode[];
  edges: BrainEdge[];
  illustrative_motion_notice: string;
}

export interface BrainSourceResult {
  ok: boolean;
  path: string;
}

/**
 * One place the Knowledge Map may look. There is deliberately no root for "the
 * workspace": Raiker's own document areas and the folders the owner granted are
 * the whole boundary, and the database appears as a root that names what it
 * already holds rather than as a folder to walk.
 */
export interface BrainSourceRoot {
  root_id: string;
  label: string;
  detail: string;
  kind: "raiker" | "granted" | "database";
  browsable: boolean;
  /** Absolute path — only ever set for a folder the owner granted themselves. */
  path: string | null;
}

export interface BrainSourceBrowse {
  path: string;
  parent: string | null;
  roots: BrainSourceRoot[];
  children: Array<{
    name: string;
    path: string;
    kind: "folder" | "file";
    size_bytes: number | null;
  }>;
  truncated: boolean;
  resolution_method?: "stored_coordinates" | "matching_text" | "";
}

export interface BrainSourceReview {
  path: string;
  kind: "folder" | "file";
  supported_files: number;
  unsupported_files: number;
  total_bytes: number;
  examples: string[];
  warnings: string[];
  review_cap: number;
}

export interface ExecutionEnvironment {
  profile_id: string;
  kind: "local" | "native" | "container" | "ssh" | "daytona";
  name: string;
  enabled: boolean;
  configured: boolean;
  available: boolean;
  status: string;
  selected: boolean;
  credential_configured: boolean;
  budget: number | null;
  cost: {
    actual_cost: number;
    provider_cost: number;
    reserved_cost: number;
    committed_cost: number;
    remaining_cost: number | null;
    reconciliation_status:
      "not_started" | "reserved" | "reconciled" | "provider_unavailable";
    history: Array<{
      event_id: string;
      action_id: string;
      event_type:
        | "reserved"
        | "reconciled"
        | "released"
        | "provider_snapshot"
        | "provider_unavailable";
      amount: number;
      provider_reference: string | null;
      reason: string | null;
      recorded_at: string;
    }>;
  } | null;
  config?: Record<string, unknown>;
  runtime?: "docker" | "podman";
  image?: string | null;
  repository_access?: "none" | "read_only";
  writable_output?: boolean;
  assigned_tool_count?: number;
  /**
   * What this boundary was measured or built to do — `raiker.execution.commands
   * .models.CommandFeatures`, as a flat map. BUG-194: `persistent_environment`
   * and `restart_recovery` are what decide whether the reset control and the
   * "survives a restart" line appear, and both come from the backend rather
   * than from configuration.
   */
  features?: Record<string, boolean>;
  availability_reason?: string | null;
  /** The boundary this host was measured to build, not the one it was configured with. */
  boundary?: string;
  /**
   * Per-observation verdicts from the readiness probe. `indeterminate` means the
   * control arm failed, so the observation proves nothing and must never be
   * rendered as enforcement.
   */
  probe_observations?: Record<string, ProbeVerdict>;
  probe_checked_at?: string;
  /** Publisher trust for the exact command runner; never inferred from a sibling digest. */
  runner_trust?: "publisher_verified" | "package_relative_integrity" | "development_unverified";
}

export type ProbeVerdict = "enforced" | "unenforced" | "indeterminate";

export interface ExecutionEnvironmentsView {
  selected_profile_id: string;
  environments: ExecutionEnvironment[];
  container_options?: {
    runtimes: Array<"docker" | "podman">;
    images: string[];
    supported_tools: string[];
  };
}

export type CommandRunState =
  | "queued"
  | "starting"
  | "running"
  | "finalizing"
  | "succeeded"
  | "failed"
  | "timed_out"
  | "cancelled"
  | "contained"
  | "lost";

export interface CommandRunView {
  run_id: string;
  session_id: string;
  turn_id: string;
  action_id: string;
  authority_kind: string;
  authority_id: string;
  state: CommandRunState;
  profile_id: string;
  backend: string;
  safe_display: string;
  started_at: string | null;
  completed_at: string | null;
  exit_code: number | null;
  termination_reason: string | null;
  stdout_bytes: number;
  stderr_bytes: number;
  truncated: boolean;
  redaction_count: number;
  receipt_digest: string | null;
  created_at: string;
  updated_at: string;
}

export interface CommandChunkView {
  run_id: string;
  sequence: number;
  stream: "stdout" | "stderr" | "system";
  text: string;
  byte_count: number;
  emitted_at: string;
  start_byte_offset: number;
  end_byte_offset: number;
}

export interface CommandReceiptView {
  run_id: string;
  state: CommandRunState;
  exit_code: number | null;
  termination_reason: string;
  completed_at: string;
  evidence: Record<string, unknown>;
  digest: string;
}

export interface CredentialDeltaView {
  run_id: string;
  environment_profile_id: string;
  state: "scanning" | "clean" | "quarantined" | "resolving" | "cleanup_failed";
  manifest: { files: Array<{ path: string; kind: string; size?: number }> };
  delta_digest: string;
  scan_digest: string;
  scan_rule_version: string;
  cleanup_status: string;
  created_at: string;
  recipient_boundary: "disposable_container_tcb";
}

export interface ModelCapacityEntry {
  profile_id: string;
  provider: string;
  model: string;
  endpoint_identity: string;
  context_window_tokens: number | null;
  source: string | null;
  history: Array<{
    capacity_id: string;
    context_window_tokens: number | null;
    action: string;
    reason: string | null;
    recorded_by: string;
    recorded_at: string;
  }>;
}

export interface ModelCapacitiesView {
  ok: boolean;
  entries: ModelCapacityEntry[];
  sync: Array<{
    profile_id: string;
    last_refresh_at: string | null;
    next_refresh_at: string;
    status: string;
    reason_code: string | null;
  }>;
  refresh_due: boolean;
  cadence_hours: number;
  can_override: boolean;
}

export interface InstanceLaunchResult {
  name: string;
  url: string;
}

/** Local-only password recovery acknowledgement. The opaque ticket is issued
 * for known and unknown usernames alike; only a valid short-lived ticket plus
 * TOTP/backup code can complete a reset. */
export interface PasswordRecoveryBeginResult {
  ok: boolean;
  ticket: string;
}

/** BUG-40 — the tray/menu-bar control's view of the host it is controlling.
 * `state` is one of running / paused / needs attention / stopped, and `waiting`
 * is what a quit would interrupt, stated before it happens. */
export interface HostWaitingWork {
  kind: string;
  label: string;
  detail: string;
}

export interface HostServiceRegistration {
  supported: boolean;
  registered: boolean;
  mechanism: string;
  label: string;
  path: string | null;
  note: string;
}

export interface HostStatusView {
  state: string;
  detail: string;
  pid: number | null;
  port: number | null;
  started_at: string | null;
  paused: boolean;
  paused_since: string | null;
  paused_reason: string | null;
  waiting: HostWaitingWork[];
  service: HostServiceRegistration;
  restartable: boolean;
}

export interface HostActionResult extends HostStatusView {
  ok: boolean;
  reason_code?: string;
  stopping?: boolean;
  restarting?: boolean;
}

// BUG-44 — what this installation is, and whether it can update itself. Every
// field here is read from the build that produced the installation rather than
// configured afterwards, and all of them can honestly be "nothing": a source
// checkout is `packaged: false, signed: false` and says so.
export interface InstallationView {
  version: string;
  target: string | null;
  packaged: boolean;
  signed: boolean;
  channel: string | null;
  commit: string | null;
  built_at: string | null;
  installer_formats: string[];
  install_root: string;
  note: string;
}

export interface UpdateChannelView {
  url: string;
  channel: string;
  public_key_fingerprint: string;
}

export interface AvailableUpdateView {
  channel: string;
  version: string;
  target: string;
  artifact: string;
  sha256: string;
  signed: boolean;
  released_at: string;
}

export interface RecoveryPointView {
  version: string;
  path: string;
  files: number;
  bytes: number;
}

export interface ReleaseTargetView {
  target_id: string;
  os: string;
  arch: string;
  runner: string;
  installer_formats: string[];
  signing: { tool: string; secrets: string[]; note: string };
}

export interface UpdateStatusView {
  state:
    | "source_checkout"
    | "no_channel"
    | "unsigned_build"
    | "up_to_date"
    | "available"
    | "unreachable";
  message: string;
  installation: InstallationView;
  channel: UpdateChannelView | null;
  available: AvailableUpdateView | null;
  recovery_points: RecoveryPointView[];
  checked_at: string | null;
  targets: ReleaseTargetView[];
  last_check: {
    state: string;
    message: string;
    available_version: string | null;
    checked_at: string | null;
  } | null;
}

export interface UpdateCheckResult extends UpdateStatusView {
  ok: boolean;
}

export interface UpdateApplyResult extends UpdateStatusView {
  ok: boolean;
  updating: boolean;
  version?: string;
  reason_code?: string;
}


// ── Web access blocklist (RAIKER-2021) ──────────────────────────────────────
// Three sources with different affordances: `stored` the owner can delete here,
// `environment` and `builtin` they cannot. `address_guard` is reported rather
// than listed because it is not a rule and cannot be switched off.
export interface WebBlocklistRule {
  rule_id: string;
  rule: string;
  kind: string;
  note: string;
  created_at: string;
}

export interface WebBlocklist {
  stored: WebBlocklistRule[];
  environment: string[];
  environment_variable: string;
  builtin: string[];
  effective_count: number;
  address_guard: { enforced: boolean; editable: boolean; description: string };
}

export interface WebBlocklistProbe {
  host: string;
  allowed: boolean;
  reason: string;
  addresses: string[];
}

// ── Git credential (RAIKER-2022) ────────────────────────────────────────────
// Never carries the token. `token_configured` says one exists, `token_source`
// says where it came from, and `grant` is the owner's current decision.
export interface GitCredentialGrant {
  grant_id: string;
  scope: string;
  status: string;
  granted_at: string;
  expires_at: string;
  session_id: string | null;
  uses: number;
}

export interface GitCredentialStatus {
  credential_configured: boolean;
  credential_source: string;
  grant: GitCredentialGrant | null;
  scopes: string[];
  grant_seconds: Record<string, number>;
  checked_at: string;
}

// ── Managed knowledge files ─────────────────────────────────────────────────
// One catalogue entry per stored original. `index_state` is the honest answer
// to "can Raiker read this?": `ready` means its text is searchable,
// `metadata_only` means the file is kept but has no safe local reader, and
// `failed` means extraction broke — the stored bytes are unaffected either way.
export type ManagedFileScope = "memory" | "project";

export type ManagedFileIndexState =
  | "queued"
  | "indexing"
  | "ready"
  | "metadata_only"
  | "failed"
  | "retired";

export interface ManagedFile {
  file_id: string;
  scope_kind: ManagedFileScope;
  project_id: string | null;
  relative_path: string;
  media_type: string;
  size_bytes: number;
  content_hash: string;
  index_state: ManagedFileIndexState;
  index_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface ManagedFileList {
  ok: boolean;
  scope_kind: ManagedFileScope;
  project_id: string | null;
  files: ManagedFile[];
}

/** One file's outcome inside a batch. A failure names the file, not the batch. */
export type ManagedFileImportResult =
  | ({ ok: true } & ManagedFile)
  | { ok: false; relative_path: string; reason_code: string };

export interface ManagedFileImportResponse {
  ok: boolean;
  scope_kind: ManagedFileScope;
  project_id: string | null;
  results: ManagedFileImportResult[];
}

export interface ManagedFileUpload {
  relative_path: string;
  media_type: string;
  data_base64: string;
}

// ── Project roots ─────────────────────────────────────────────────────────
// A project's root is one of two things: the managed subpath under the
// workspace it has always had, or a folder the owner already has and granted.
// One explorer browses both, so both answer this same shape — what differs is
// only what the answer says.
export type ProjectRootKind = "managed" | "attached";

export interface ProjectBrowseEntry {
  name: string;
  relative_path: string;
  is_directory: boolean;
  size_bytes: number;
  media_type: string;
  /** Absent when the file has no catalogue row: a file Raiker cannot read has
   *  no index state, and inventing one would suggest a failure. */
  index_state: ManagedFileIndexState | null;
}

export interface ProjectBrowseView {
  path: string;
  parent: string | null;
  entries: ProjectBrowseEntry[];
  truncated: boolean;
  root_kind: ProjectRootKind;
  root_label: string;
  /** The grant was revoked, the project detached, or the folder moved. The
   *  explorer must say so; an empty tree would read as "no files". */
  root_missing: boolean;
}

// B13 — the repository Build is pointed at, browsed one directory at a time.
// Deliberately the same entry shape as a project's tree so one explorer serves
// both roots; `index_state` is always null here because a repository is files on
// disk rather than a catalogue of managed documents.
export interface CodeRepoBrowseView {
  path: string;
  parent: string | null;
  entries: ProjectBrowseEntry[];
  truncated: boolean;
  root_kind: "local" | "github";
  root_label: string;
  /** A GitHub coordinate with no checkout, or a local folder that has moved. */
  root_missing: boolean;
  /** Which of those two, so the interface can say which; "" when present. */
  reason_code?: string;
}

// B13 — one bounded text file for the read-only viewer. A file that cannot be
// shown says why rather than rendering as empty: `readable` false with the
// reason the server gave (`binary_file`, `file_too_large`, `not_found`).
export interface CodeRepoFileView {
  path: string;
  text: string;
  truncated: boolean;
  size_bytes: number;
  readable: boolean;
  reason_code: string;
}

export interface ProjectRootStatus {
  ok: boolean;
  project_id: string;
  root_kind: ProjectRootKind;
  root_label: string;
  root_path: string | null;
  root_missing: boolean;
  writable: boolean;
  watching: boolean;
  watch_reason: string;
  last_scanned_at: string;
  indexed_files: number;
}

export interface ProjectRootIndexResult {
  ok: boolean;
  project_id: string;
  indexed: number;
  updated: number;
  retired: number;
  skipped: number;
  truncated: boolean;
  scanned_at: string;
}
