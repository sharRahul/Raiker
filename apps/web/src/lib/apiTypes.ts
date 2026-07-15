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
  prompt_cache_ttl: string | null;
}

export interface ModelsView {
  profiles: ModelProfile[];
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
  executes_action: boolean; // true only for an approved, single-use connector write intent
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
