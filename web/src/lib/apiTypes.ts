import type { ApprovalMode } from "./approvalMode";
import type {
  AgentPlan,
  AgentPlanStep,
  ApprovalResolved,
  ApprovalView,
  AttachmentPreview,
  AuditExportResult,
  AuditExportView,
  BackgroundWorkerHealth,
  BrainSourceBrowse,
  BrainSourceResult,
  BrainSourceReview,
  BrainSourceRoot,
  BrainView,
  CapabilityContainmentView,
  CapabilityDecisionMode,
  CapabilityGateView,
  CheckpointCaptureHealth,
  CheckpointView,
  CodeReposView,
  CodeRepoView,
  CodexStatus,
  ConnectionsView,
  ConnectorView,
  ContainedSubject,
  ContentPartView,
  ContextUsageView,
  ConversationBranch,
  ConversationBranchOrigin,
  ConversationBranchPlan,
  ConversationCompaction,
  ConversionPreview,
  CredentialLifecycleView,
  CriticalApprovalResolved,
  DiagnosticsView,
  EmbeddingProviderView,
  EmbeddingSpaceView,
  EnvironmentContextView,
  EventView,
  ExtensionsOverviewView,
  ExtensionView,
  FileProvenanceEntryView,
  HfDownloadPreview,
  HfSearchResult,
  HfVariant,
  HuggingFaceDownloadResult,
  IdentityView,
  ImageGallery,
  ImageGeneration,
  ImportedFile,
  ImportRefused,
  InstallPlan,
  IssuedSessionView,
  KnowledgeSource,
  KnowledgeSources,
  LocalModelView,
  ManagedFile,
  ManagedFileImport,
  ManagedFileList,
  McpServerView,
  McpSessionView,
  McpToolDeclaration,
  MemoryControlView,
  MemoryHistoryEvent,
  MemoryImportPreview,
  MemoryImportResult,
  MemoryIntegrity,
  MemoryProposal,
  MemoryRelationshipProposal,
  MemorySettingsView,
  MemorySource,
  ModelCapacities,
  ModelCapacityEntry,
  ModelConversionRequestBody,
  ModelDecisionView,
  ModelLibraryView,
  ModelOperationView,
  ModelPricingEntryView,
  ModelPricingView,
  ModelProfileView,
  ModelReadinessView,
  ModelSetupState,
  ModelsView,
  NativeUsageMetricView,
  NotificationView,
  ObservationsView,
  OwnerQuestionAnswered,
  PasswordRecoveryBeginView,
  PathAttachment,
  PricingHistoryEntry,
  PricingSyncState,
  ProjectAttachmentView,
  ProjectBrowseEntry,
  ProjectBrowseView,
  ProjectContext,
  ProjectDeletionPreviewView,
  ProjectDetailView,
  ProjectFilesView,
  ProjectFileView,
  ProjectRootIndexResult,
  ProjectRootStatus,
  ProjectsListView,
  ProjectTreeNode,
  ProjectView,
  ProviderHealthView,
  ProviderModelListView,
  ProviderWeeklyUsage,
  ReadCapabilities,
  RecalledMemory,
  RestorePlan,
  RestorePlanFile,
  RestoreRequested,
  ResumableTurn,
  ResumableTurns,
  RuntimeModeView,
  RuntimeReadinessView,
  SecurityFindingView,
  SecurityHealthView,
  SessionAttachment,
  SessionAttachments,
  SessionDetail,
  SessionRecall,
  SessionView,
  SetupState,
  SourceAnchorView,
  SpeechProbe,
  SpeechRuntime,
  SpeechRuntimeView,
  StandingGrantView,
  TaskDetailView,
  TaskView,
  TelemetryDestinationView,
  ToolReadinessView,
  TranscriptFile,
  TranscriptManifest,
  TranscriptMessage,
  TurnDetailView,
  TurnSourceExcerpt,
  TurnSources,
  TurnSourceView,
  TurnView,
  UploadAttachment,
  WeeklyUsage,
  WorkInFlight,
  WorkThreadFacet,
  WorkThreadPage,
  WorkThreadView,
} from "./generated/apiContract";
import type { ApprovalDetailView as GeneratedApprovalDetailView } from "./generated/apiContract";

// Response shapes from the governed read API (see raiker/control/dashboard.py and
// raiker/control/dtos.py). These mirror the backend DTOs; the backend remains the source of truth.
//
// Two guards stand behind that, both in the Python CI job, so a backend-only change is checked
// even though the web job does not run for one:
//   - tests/test_api_contract_schemas.py asserts against live responses, so it covers the routes
//     as well as the shapes — but its key sets are transcribed here by hand.
//   - tests/test_api_contract_generated.py (GCR-42) derives the comparison instead: every
//     interface below is paired with the backend `<Name>View` dataclass and every field declared
//     required here must be one that DTO sends. It covers the shapes nobody transcribed.
// A required field added here without its backend field fails the second one.

export type ToolReadiness = ToolReadinessView;

export type { ReadCapabilities };

export type EnvironmentContext = EnvironmentContextView;

export type CapabilityGate = CapabilityGateView;

export interface ComposerApprovalModeSettings {
  approval_mode: ApprovalMode;
}

export type RuntimeMode = RuntimeModeView;

export type RuntimeReadiness = RuntimeReadinessView;

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

export type { AgentPlanStep };

export type { AgentPlan };

export type { McpToolDeclaration };

export type McpServer = McpServerView;

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

export type McpSession = McpSessionView;

export type McpFinding = SecurityFindingView;

export type Notification = NotificationView;

export type StandingGrant = StandingGrantView;

export type CredentialLifecycle = CredentialLifecycleView;

export type SecurityHealth = SecurityHealthView;

export type { CapabilityDecisionMode };

export type ProviderHealth = ProviderHealthView;

export type ModelReadinessState = ModelReadinessView["state"];

export type { ModelReadinessView };

export type { ModelSetupState };

export type { SetupState };

export type ModelOperation = ModelOperationView;

/**
 * What a confirmed "Delete partial files" would remove — named exactly.
 *
 * GCR-19 — `paths` is the deletion set: only the files the operation can prove
 * it created, never the library directory it wrote them into. `path` is the
 * single-target convenience (a download's own snapshot directory) and is null
 * whenever the set has more than one member.
 */
export interface PartialFiles {
  path: string | null;
  paths: string[];
  exists: boolean;
  bytes: number;
  file_count: number;
}

export type { BackgroundWorkerHealth };

export type { ContainedSubject };

export type { CapabilityContainmentView };

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
/** One environment variable a channel transport declares that it needs. */
export interface ChannelEnvRequirement {
  name: string;
  description: string;
  url: string | null;
  secret: boolean;
  required: boolean;
  /** Whether it is set. Never what it is set to. */
  present: boolean;
}

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
  env_requirements?: ChannelEnvRequirement[];
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
  /** BUG-308 — where this plugin's own code would run on this machine: not
   *  at all, in a container with no network, or with this machine's network.
   *  Optional so older payloads and fixtures stay valid. */
  code_runtime?: {
    where: "not_enabled" | "isolated" | "host_network";
    summary: string;
  };
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

export type RuntimeInstallPlan = InstallPlan;

export type LocalModel = LocalModelView;

export type { ModelLibraryView };

export type HuggingFaceSearchResult = HfSearchResult;

export type HuggingFaceVariant = HfVariant;

export type HuggingFaceDownloadPreview = HfDownloadPreview;

export type { HuggingFaceDownloadResult };

export type ModelConversionPreview = ConversionPreview;
export type ConversionQuantization = ModelConversionRequestBody["quantization"];

export type Diagnostics = DiagnosticsView;

export type { MemoryIntegrity };

export type { CheckpointCaptureHealth };

export type ModelProfile = ModelProfileView;

export type ContextUsage = ContextUsageView;

export type ModelPricingHistoryEntry = PricingHistoryEntry;

export type ModelPricingEntry = ModelPricingEntryView;

export type ModelPricingSyncState = PricingSyncState;

export type { ModelPricingView };

export type TranscriptExportMessage = TranscriptMessage;

export type TranscriptExportFile = TranscriptFile;

export type TranscriptExportManifest = TranscriptManifest;

export type { ResumableTurn };

export type ResumableTurnsView = ResumableTurns;

export type { ModelsView };

export type NativeUsageMetric = NativeUsageMetricView;

/**
 * One limit window a subscription volunteered as part of a turn (BUG-254).
 *
 * Never polled and never inferred: this is what the provider itself said, and a
 * provider that says nothing produces no window at all rather than a zero.
 */
export interface SubscriptionLimitWindow {
  label: string;
  used_percent: number;
  window_minutes: number | null;
  resets_at: string | null;
}

export interface SubscriptionLimits {
  windows: SubscriptionLimitWindow[];
  observed_at: string;
  /** The reading is old enough that it should not be read as current. */
  stale: boolean;
  source: "provider_turn";
}

export type { ProviderWeeklyUsage };

export type ProviderWeeklyUsageView = WeeklyUsage;

/** Read-only status of one governed service connector (web-app task 4). Every
 * field derives from stored/config state — the view never reaches the network
 * and never exposes a credential value (only whether one is set). */
export type { ConnectorView };

export type { ConnectionsView };

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

export type ProviderModelList = ProviderModelListView;

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

export type CodexSubscriptionStatus = CodexStatus;

/** A project is an organizing scope (workspace-contained subpath + its
 * sessions/checkpoints), never an authority — selecting one grants nothing. */
export type { ProjectView };

export type ProjectAttachment = ProjectAttachmentView;

export type ProjectDeletionPreview = ProjectDeletionPreviewView;

export type ProjectsList = ProjectsListView;

/**
 * One repository the Build workspace can point a coding chat at. A reference
 * only: it carries no credential and grants no capability. A `local` repository
 * is a workspace-contained subpath; a `github` repository is an `owner/repo`
 * coordinate read through the brokered `github_read` tool.
 */
export type CodeRepo = CodeRepoView;

export type { CodeReposView };

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

export type ProjectDetail = ProjectDetailView;

export type { ProjectContext };

export type { ProjectTreeNode };

export type EventEntry = EventView;

export type Checkpoint = CheckpointView;

export type { ConversationBranchPlan };

export type { ConversationBranch };

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

export type { OwnerQuestionAnswered };

export type { ConversationCompaction };

export type { ConversationBranchOrigin };

export type { RestorePlanFile };

export type { RestorePlan };

export type RestoreRequestResult = RestoreRequested;

export type { AuditExportView };

export type { AuditExportResult };

/**
 * One extension's lifecycle, as four independent server-derived facts. `usable`
 * is a conclusion, never a claim the browser makes on its own; `blocked_reason`
 * names the first unmet condition.
 */
export type { ExtensionView };

export type ExtensionsOverview = ExtensionsOverviewView;

export type ProjectFile = ProjectFileView;

export type FileProvenanceEntry = FileProvenanceEntryView;

export type { ProjectFilesView };

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

/**
 * C18 — one thread of the owner's work, whatever started it.
 *
 * Chat search covers titles and message text, which answers "where did I say
 * that" and not "what am I working on". The second question spans conversations
 * the owner typed *and* the threads a routine is advancing on its own (C11),
 * wants the project each sits in, and wants to know which are blocked.
 */
/**
 * NEW-THREAD-01 — one filtered, faceted, bounded page of the work index.
 *
 * The facets are computed on the server over everything that matched, with
 * each facet's own filter lifted, so every choice stays reachable from every
 * page rather than only those in the rows a browser happened to receive.
 */
export type { WorkThreadFacet };

export type { WorkThreadPage };

export type WorkThread = WorkThreadView;

export type SessionSummary = SessionView;

export type TurnSummary = TurnView;

export type { SessionDetail };

export type TurnDetail = TurnDetailView;

export type AuthSession = IssuedSessionView;

// Raiker/control/dashboard.py ApprovalView.to_dict()
export type { IdentityView };

export type { ApprovalView };

/**
 * What the approval relay recorded when an approved action ran: who resolved it,
 * plus whatever the executor reported. The backend carries the executor's own
 * result record, which is open by nature, so this names the keys the card reads.
 */
export interface ExecutionEvidence {
  principal_id?: string;
  returncode?: number;
  stdout_bytes?: number;
  stderr_bytes?: number;
  stdout?: string;
  stderr?: string;
  truncated?: boolean;
  output_redacted?: boolean;
}

export type ApprovalDetailView = Omit<GeneratedApprovalDetailView, "execution_evidence"> & {
  execution_evidence: ExecutionEvidence;
};

export type ResolveApprovalResult = ApprovalResolved;

export type ResolveCriticalApprovalResult = CriticalApprovalResolved;

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

export type ContentPart = ContentPartView;

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
  // BUG-288 — the answer as declared parts. Empty for every turn that declared
  // nothing, which is most of them, so a client that ignores it sees what it
  // always saw. Optional so older payloads and fixtures stay valid.
  content_parts?: ContentPart[];
}

// Raiker.contracts.streaming.StreamEvent serialized over SSE (see routes_prompts._sse).
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

export type { TaskView };

// Raiker/tasks/history.py TaskEventView.to_dict() — one recorded transition.
export interface TaskEventView {
  event_id: string;
  event_type: string;
  timestamp: string;
  actor: string;
  /** What the runtime stated, never a bare code and never an empty row. */
  detail: string;
  /** The governed turn this belongs to, when it had one. */
  turn_id: string | null;
  session_id: string | null;
}

// Raiker/tasks/history.py TaskAttemptView.to_dict() — one run of a task.
export interface TaskAttemptView {
  /** 1-based across runs and continuations; 0 for a segment that is not a run. */
  index: number;
  /** "run", "continuation" or "record". */
  kind: string;
  started_at: string;
  ended_at: string | null;
  /**
   * "completed" | "failed" | "waiting_for_approval" | "cancelled" |
   * "waiting_for_children" | "in_progress" | "recorded".
   */
  outcome: string;
  summary: string;
  /** The decision this attempt waited on, when the runtime recorded which. */
  approval_id: string | null;
  events: TaskEventView[];
}

export type { TaskDetailView };

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
export type PromptAttachment = PathAttachment | UploadAttachment;

export interface PromptRequestBody {
  text: string;
  // Client-reported provenance; no audio or transcript metadata crosses this boundary.
  input_mode?: "typed" | "dictated" | "mixed";
  // Which composer sent this prompt. It selects the operating protocol the turn
  // runs under — Build adds the engineering protocol, Design adds the research
  // one, Chat adds neither — and grants nothing: gates, capabilities and
  // approvals are identical whichever it is.
  surface?: "chat" | "build" | "design";
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
  /** False for a builtin this build does not ship, and for an `http` destination
   *  the owner's egress grant does not cover: the rule matches, the handler
   *  refuses, and nothing is enforced. */
  available: boolean;
  /** Why an unavailable handler is unavailable — "egress_not_granted" or
   *  "builtin_not_in_this_build". Empty when the handler is available. */
  unavailable_reason: string;
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

export type { AttachmentPreview };

/** The passage a source resolved to — the part every excerpt route shares. */
export type SourceExcerptView = Omit<MemorySource, "ok" | "memory_id">;

export type { SourceAnchorView };

export type { TurnSourceView };

export type { RecalledMemory };

export type SessionRecallView = SessionRecall;

export type TurnSourcesView = TurnSources;

export type TurnSourceExcerptView = TurnSourceExcerpt;

export type { SessionAttachment };

export type SessionAttachmentsView = SessionAttachments;

export type { WorkInFlight };

export interface StopAllResult {
  tasks: { task_id: string; result: string }[];
  turns: { session_id: string; turn_id: string }[];
  commands: { run_id: string; state: string }[];
  failed: { kind: string; reason_code: string; run_id?: string }[];
  safe_boundary: boolean;
}

export interface InterruptRequestBody {
  session_id: string;
  task_id?: string;
  all?: boolean;
  action_type?: string;
  reason?: string;
  steer_text?: string;
}

export type { MemoryImportPreview };

export type { MemoryImportResult };

export type { MemoryControlView };

export type { MemoryProposal };

export type { MemoryRelationshipProposal };

export type { MemoryHistoryEvent };

export type { EmbeddingSpaceView };

export type { MemorySettingsView };

export type { EmbeddingProviderView };

// Raiker/control/dashboard.py ObservationView.to_dict(). MEM-04 — metadata
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

export type { ObservationsView };

// Raiker/control/dashboard.py BrainView.to_dict(). Nodes and edges are stored
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

export type { BrainView };

export type { BrainSourceResult };

export type { BrainSourceRoot };

export type { BrainSourceBrowse };

export type { BrainSourceReview };

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

export type { ModelCapacityEntry };

export type ModelCapacitiesView = ModelCapacities;

export interface InstanceLaunchResult {
  name: string;
  url: string;
}

export type PasswordRecoveryBeginResult = PasswordRecoveryBeginView;

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
    /** REM-SET-UPDATES — nothing has asked the channel; not an assurance. */
    | "not_checked"
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
  // The boundary the runtime issues the credential inside — the hosts its
  // credential helper will answer, and everything a loan is used for. The page
  // states the scope before it asks for the secret, and states the runtime's
  // answer rather than its own.
  hosts: string[];
  operations: string[];
  checked_at: string;
}

// ── BUG-305 — one answer to "what can Raiker read" ─────────────────────────
// Two controllers, one inventory. `held` is the whole distinction and decides
// what revoking does: a managed file is a copy Raiker made and takes with it, a
// granted folder is the owner's own and is only stopped being read.
export type KnowledgeSourceKind = "managed_file" | "granted_folder";

export type { KnowledgeSource };

export type KnowledgeSourcesView = KnowledgeSources;

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

export type { ManagedFile };

export type { ManagedFileList };

/** One file's outcome inside a batch. A failure names the file, not the batch. */
export type ManagedFileImportResult = ImportedFile | ImportRefused;

export type ManagedFileImportResponse = ManagedFileImport;

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

export type { ProjectBrowseEntry };

export type { ProjectBrowseView };

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

// B10 — parse-level problems for one open file, from the same service and the
// same `language_intelligence` gate the agent's own `diagnostics` tool uses.
//
// `checked` is the field that carries the honesty contract: false means this
// runtime has no parser for the file's language and it was NOT looked at. A
// surface must say "not checked" for it, never "no problems".
export interface CodeRepoDiagnostic {
  path: string;
  line: number;
  column: number;
  severity: string;
  message: string;
  source: string;
}

export interface CodeRepoDiagnosticsView {
  path: string;
  checked: boolean;
  available: boolean;
  reason_code: string;
  reason: string;
  diagnostics: CodeRepoDiagnostic[];
}

// B13 — one bounded text file for the read-only viewer. A file that cannot be
// shown says why rather than rendering as empty: `readable` false with the
// reason the server gave (`binary_file`, `file_too_large`, `not_found`).
/** one uncommitted change in the repository's working tree. */
export interface CodeRepoChangeEntry {
  path: string;
  /** The old name of a rename; "" otherwise. Both ends of a rename matter. */
  previous_path: string;
  /** Git's own word for it: modified, added, deleted, renamed, untracked. */
  state: string;
  /** Whether the working tree still differs from the index for this path. */
  unstaged: boolean;
}

/**
 * The working tree's uncommitted state, as Build's `Changes` tab reads it.
 *
 * Built from the same two helpers the commit proposal is assembled from, so
 * what the pane shows and what a commit would record are one change set. The
 * two absences are kept apart on purpose: a repository with no checkout and a
 * folder under no version control are different answers, and "no changes" must
 * not stand in for either.
 */
export interface CodeRepoChangesView {
  entries: CodeRepoChangeEntry[];
  diff: string;
  /** More changed files than the read carries. */
  truncated: boolean;
  /** The diff was longer than the pane will render. */
  diff_truncated: boolean;
  root_missing: boolean;
  reason_code: string | null;
}

export interface CodeRepoFileView {
  path: string;
  text: string;
  truncated: boolean;
  size_bytes: number;
  readable: boolean;
  reason_code: string;
}

export type { ProjectRootStatus };

export type { ProjectRootIndexResult };

/** One entry the host path browser offers (BUG-251). */
export interface HostPathEntry {
  name: string;
  /** The absolute path, which is the whole point: the browser cannot make one. */
  path: string;
  is_directory: boolean;
}

/** One directory listing from the host, for the Browse… dialog (BUG-251). */
export interface HostPathListing {
  /** Empty means the top of the machine: drives, home, and the usual folders. */
  path: string;
  /** Null at the top, "" when the listing is already a root. */
  parent: string | null;
  /** "\\" or "/", so the dialog can show a path the way the host writes it. */
  separator: string;
  /** Where the workspace lives, so a field wanting a relative path can make one. */
  workspace_root: string;
  entries: HostPathEntry[];
  truncated: boolean;
  /** The location is gone or cannot be read — not the same as empty. */
  missing: boolean;
}

export type { SpeechRuntimeView };

export type { SpeechRuntime };

export interface SpeechRuntimeChange {
  endpoint?: string;
  model?: string;
}

export type SpeechRuntimeProbe = SpeechProbe;


export type { ImageGeneration };

export type ImageGenerationsView = ImageGallery;

export type TelemetryDestination = TelemetryDestinationView;

export type ModelDecision = ModelDecisionView;
