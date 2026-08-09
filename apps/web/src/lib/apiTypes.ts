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
}

/**
 * One installed skill. `active` is the owner's own switch: an inactive skill
 * stays stored and is withheld from every turn. The stored document is never
 * carried in a list — it is read on an explicit download or by the runtime.
 */
export interface SkillView {
  skill_id: string;
  name: string;
  description: string;
  version: string | null;
  source: "upload" | "url" | "builtin" | "built";
  source_ref: string | null;
  checksum: string;
  active: boolean;
  files: string[];
  file_count: number;
  byte_size: number;
  created_at: string;
  updated_at: string;
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
  readiness: Record<string, boolean>;
  missing_config: string[];
  provider_health: ProviderHealth[];
  scope_note: string;
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
  hosted_model_gate_state: string;
  private_network_model_gate_state: string;
  model_egress_allowlist_configured: boolean;
  remote_profile_count: number;
  fallback_sequence: string[];
  no_silent_hosted_fallback: boolean;
  ready_provider_count?: number;
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
  preview_kind:
    "file_diff" | "patch" | "git_change" | "connector_request" | "arguments";
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
  "lifecycle" | "text_delta" | "tool" | "final" | "error";

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
  session_id?: string;
  planning_mode?: string;
  approval_mode?: string;
  model_profile?: string;
  model?: string;
  reasoning_effort?: string;
  max_tool_calls?: number;
  attachments?: PromptAttachment[];
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

export interface MemoryHistoryEvent {
  audit_id: string;
  action: string;
  actor_id: string;
  created_at: string;
  details: Record<string, unknown>;
}

export interface MemorySettingsView {
  incognito: boolean;
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

export interface BrainSourceBrowse {
  path: string;
  parent: string | null;
  children: Array<{
    name: string;
    path: string;
    kind: "folder" | "file";
    size_bytes: number | null;
  }>;
  truncated: boolean;
  resolution_method: "stored_coordinates" | "matching_text" | "";
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
  kind: "local" | "container" | "ssh" | "daytona";
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
  availability_reason?: string | null;
}

export interface ExecutionEnvironmentsView {
  selected_profile_id: string;
  environments: ExecutionEnvironment[];
  container_options?: {
    runtimes: Array<"docker" | "podman">;
    images: string[];
    supported_tools: string[];
  };
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
