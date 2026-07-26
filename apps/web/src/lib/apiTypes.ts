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
  models_used?: number;
  turns_used?: number;
  total_tokens?: number;
  /** Decimal string, or null when no price is resolvable. Never "0" for unknown. */
  total_cost?: string | null;
  cost_currency?: string | null;
  price_source?: string | null;
  price_as_of?: string | null;
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
  counts: { total: number; installed: number; connected: number; enabled: number; usable: number };
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
}

// raiker/control/dashboard.py ApprovalDetailView.to_dict()
export interface ApprovalDetailView {
  approval: ApprovalView;
  arguments: Record<string, unknown>;
  diff: string | null;
  diff_path: string | null;
  preview_kind: "file_diff" | "patch" | "arguments";
  metadata_only_notice: string;
}

// POST /api/approvals/{id}/resolve response.
export interface ResolveApprovalResult {
  approval_id: string;
  action_id: string;
  status: string;
  executes_action: boolean;
  reason: string;
  connector_result?: Record<string, unknown>;
}

export interface ResolveCriticalApprovalResult {
  approval_id: string;
  status: string;
  decision: string;
  message: string;
  executes_action: boolean;
}

// Approval proposal carried on an AgentResponse when status === "needs_approval".
// Mirrors the `approval` dict built in raiker/runtime/orchestrator.py. No action is executed.
export interface ApprovalInfo {
  action_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  risk_level: string;
  reasons: string[];
  message: string;
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
export type StreamKind = "lifecycle" | "text_delta" | "tool" | "final" | "error";

export interface StreamEvent {
  kind: StreamKind;
  text: string;
  event_type: string;
  payload: Record<string, unknown>;
  response: AgentResponse | null;
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
}

// POST /api/interrupts response (raiker/api/routes_prompts.py).
export interface InterruptResult {
  applied: { task_id: string; result: string }[];
  safe_boundary: boolean;
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
