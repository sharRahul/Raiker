import type {
  AgentPlan,
  AgentPlanStep,
  AgentResponse,
  ApprovalInfo,
  ApprovalResolved,
  ApprovalView,
  AttachmentPreview,
  AuditExportResult,
  AuditExportView,
  BackgroundWorkerHealth,
  BlocklistProbe,
  BrainEdgeView,
  BrainNodeView,
  BrainSourceBrowse,
  BrainSourceResult,
  BrainSourceReview,
  BrainSourceRoot,
  BrainView,
  CapabilityContainmentView,
  CapabilityDecisionMode,
  CapabilityGateView,
  CatalogueRefreshed,
  ChannelEnvRequirement,
  ChannelProfile,
  ChannelsView,
  ChannelUpdate,
  CheckpointCaptureHealth,
  CheckpointView,
  CodeMapStatus,
  CodeRepoBrowseView,
  CodeRepoChangeEntry,
  CodeRepoChangesView,
  CodeRepoDiagnosticsView,
  CodeRepoFileView,
  CodeReposView,
  CodeRepoView,
  CodexStatus,
  CommandChunkView,
  CommandReceiptView,
  CommandRunView,
  ComposerApprovalMode,
  ConformanceFindingView,
  ConnectionsView,
  ConnectorStoreView,
  ConnectorView,
  ContainedSubject,
  ContentPartView,
  ContextUsageView,
  ConversationBranch,
  ConversationBranchOrigin,
  ConversationBranchPlan,
  ConversationCompaction,
  ConversionPreview,
  CredentialDeltaView,
  CredentialLifecycleView,
  CriticalApprovalResolved,
  Diagnostic,
  DiagnosticsExport,
  DiagnosticsView,
  EmbeddingProviderView,
  EmbeddingSpaceView,
  EnvironmentContextView,
  EventView,
  ExecutionEnvironmentsView,
  ExecutionEnvironmentView,
  ExtensionsOverviewView,
  ExtensionView,
  FileProvenanceEntryView,
  GitCredentialGrant,
  GitCredentialStatus,
  GuideIndex,
  GuideSection,
  GuideSectionSummary,
  HfDownloadPreview,
  HfSearchResult,
  HfVariant,
  HookActivityView,
  HookEventView,
  HookHandlerView,
  HookRuleView,
  HookSourceView,
  HooksView,
  HostActionResult,
  HostPathEntry,
  HostPathListing,
  HostView,
  HostWaitingWork,
  HuggingFaceDownloadResult,
  IdentityView,
  ImageGallery,
  ImageGeneration,
  ImportedFile,
  ImportRefused,
  InstallationView,
  InstalledPlugin,
  InstalledSkill,
  InstallPlan,
  InstanceCreated,
  InterruptResult,
  IssuedSessionView,
  KnowledgeSource,
  KnowledgeSources,
  LimitWindow,
  LocalModelView,
  ManagedFile,
  ManagedFileImport,
  ManagedFileList,
  McpAgentAccess,
  McpOffer,
  McpServerView,
  McpSessionView,
  McpToolDeclaration,
  MemoryControlView,
  MemoryHistoryEvent,
  MemoryImportBatch,
  MemoryImportPreview,
  MemoryImportRecord,
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
  NextAction,
  ReadinessStep,
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
  ObservationView,
  OwnerQuestionAnswered,
  PartialFiles,
  PasswordRecoveryBeginView,
  PathAttachment,
  PluginContributionKind,
  PluginContributions,
  PluginSignatureView,
  PluginsView,
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
  RecoveryPointView,
  ReleaseTargetView,
  RestorePlan,
  RestorePlanFile,
  RestoreRequested,
  ResumableTurn,
  ResumableTurns,
  RuntimeModeView,
  RuntimeReadinessView,
  SecurityFindingView,
  SecurityHealthView,
  ServiceRegistration,
  SessionAttachment,
  SessionAttachments,
  SessionDetail,
  SessionRecall,
  SessionView,
  SetupState,
  SkillConformance,
  SkillInstalled,
  SkillVerification,
  SourceAnchorView,
  SpeechProbe,
  SpeechRuntime,
  SpeechRuntimeView,
  StandingGrantView,
  StopAllResult,
  StoreConnector,
  SubscriptionLimitsView,
  TaskAttemptView,
  TaskDetailView,
  TaskEventView,
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
  UpdateChannelView,
  UpdateCheckResult,
  UpdateStatusView,
  UploadAttachment,
  UploadedAttachment,
  WebBlocklist,
  WebBlocklistRule,
  WeeklyUsage,
  WorkInFlight,
  WorkThreadFacet,
  WorkThreadPage,
  WorkThreadView,
} from "./generated/apiContract";
import type { ApprovalDetailView as GeneratedApprovalDetailView } from "./generated/apiContract";
import type { CodeMapFailure, CodeMapPaths as GeneratedCodeMapPaths } from "./generated/apiContract";
import type {
  UpdateApplyResult as GeneratedUpdateApplyResult,
  UpdateDeferred,
} from "./generated/apiContract";

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

export type ComposerApprovalModeSettings = ComposerApprovalMode;

export type RuntimeMode = RuntimeModeView;

export type RuntimeReadiness = RuntimeReadinessView;

export type { McpAgentAccess };

export type { AgentPlanStep };

export type { AgentPlan };

export type { McpToolDeclaration };

export type McpServer = McpServerView;

export type SkillConformanceFinding = ConformanceFindingView;

export type { SkillConformance };

export type SkillView = InstalledSkill;

export type { SkillVerification };

export type SkillMutationResult = SkillInstalled;

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

export type { PartialFiles };

export type { BackgroundWorkerHealth };

export type { ContainedSubject };

export type { CapabilityContainmentView };

export type PluginSignature = PluginSignatureView;

export type { ChannelEnvRequirement };

export type { ChannelProfile };

export type { ChannelsView };

export type { McpOffer };

export type { PluginContributions };

export type { InstalledPlugin };

export type { PluginContributionKind };

export type { PluginsView };

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
export type SubscriptionLimitWindow = LimitWindow;

export type SubscriptionLimits = SubscriptionLimitsView;

export type { ProviderWeeklyUsage };

export type ProviderWeeklyUsageView = WeeklyUsage;

/** Read-only status of one governed service connector (web-app task 4). Every
 * field derives from stored/config state — the view never reaches the network
 * and never exposes a credential value (only whether one is set). */
export type { ConnectorView };

export type { ConnectionsView };

export type { StoreConnector };

export type { ConnectorStoreView };

export type ProviderModelList = ProviderModelListView;

export type ProviderCatalogueRefresh = CatalogueRefreshed;

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

export type { CodeMapStatus };

/**
 * GET /api/code/map/paths — completion for an `@`-mention (B19).
 *
 * `status` is `"success"` with the matching paths, or a named refusal:
 * `code_map_not_built` when the owner has never indexed the repository, or a
 * governance reason when the `code_map_indexing` capability is off. The menu
 * shows the reason rather than an empty list, because "nothing matched" and
 * "nothing could match" send the owner to different places.
 */
export type CodeMapPaths = GeneratedCodeMapPaths | CodeMapFailure;

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

export type { DiagnosticsExport };

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

export type { ApprovalInfo };

export type ContentPart = ContentPartView;

export type { AgentResponse };

// Raiker.contracts.streaming.StreamEvent serialized over SSE (see routes_prompts._sse).
export type StreamKind =
  "lifecycle" | "text_delta" | "reasoning_delta" | "tool" | "final" | "error";

export type { GuideSectionSummary };

export type { GuideIndex };

export type { GuideSection };

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

export type { TaskEventView };

export type { TaskAttemptView };

export type { TaskDetailView };

export type { InterruptResult };

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

export type { HookHandlerView };

export type { HookRuleView };

export type { HookSourceView };

export type { HookEventView };

export type { HookActivityView };

export type { HooksView };

export type { UploadedAttachment };

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

export type { StopAllResult };

export interface InterruptRequestBody {
  session_id: string;
  task_id?: string;
  all?: boolean;
  action_type?: string;
  reason?: string;
  steer_text?: string;
}

export type { MemoryImportPreview };

export type { MemoryImportRecord };

export type { MemoryImportBatch };

export type { MemoryImportResult };

export type { MemoryControlView };

export type { MemoryProposal };

export type { MemoryRelationshipProposal };

export type { MemoryHistoryEvent };

export type { EmbeddingSpaceView };

export type { MemorySettingsView };

export type { EmbeddingProviderView };

export type { ObservationView };

export type { ObservationsView };

export type BrainNode = BrainNodeView;

export type BrainEdge = BrainEdgeView;

export type { BrainView };

export type { BrainSourceResult };

export type { BrainSourceRoot };

export type { BrainSourceBrowse };

export type { BrainSourceReview };

export type ExecutionEnvironment = ExecutionEnvironmentView;

export type ProbeVerdict = "enforced" | "unenforced" | "indeterminate";

export type { ExecutionEnvironmentsView };

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

export type { CommandRunView };

export type { CommandChunkView };

export type { CommandReceiptView };

export type { CredentialDeltaView };

export type { ModelCapacityEntry };

export type ModelCapacitiesView = ModelCapacities;

export type InstanceLaunchResult = InstanceCreated;

export type PasswordRecoveryBeginResult = PasswordRecoveryBeginView;

export type { HostWaitingWork };

export type HostServiceRegistration = ServiceRegistration;

export type HostStatusView = HostView;

export type { HostActionResult };

export type { InstallationView };

export type { UpdateChannelView };

export type AvailableUpdateView = ChannelUpdate;

export type { RecoveryPointView };

export type { ReleaseTargetView };

export type { UpdateStatusView };

export type { UpdateCheckResult };

/** The verified update handed to the helper, or the work it would interrupt. */
export type UpdateApplyResult = GeneratedUpdateApplyResult | UpdateDeferred;


export type { WebBlocklistRule };

export type { WebBlocklist };

export type WebBlocklistProbe = BlocklistProbe;

export type { GitCredentialGrant };

export type { GitCredentialStatus };

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

export type { CodeRepoBrowseView };

export type CodeRepoDiagnostic = Diagnostic;

export type { CodeRepoDiagnosticsView };

export type { CodeRepoChangeEntry };

export type { CodeRepoChangesView };

export type { CodeRepoFileView };

export type { ProjectRootStatus };

export type { ProjectRootIndexResult };

export type { HostPathEntry };

export type { HostPathListing };

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

export type { NextAction as ModelNextAction, ReadinessStep as ModelReadinessStep };
