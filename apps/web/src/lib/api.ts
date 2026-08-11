import type {
  AgentPlan,
  AgentResponse,
  ApprovalDetailView,
  ApprovalView,
  AttachmentPreview,
  SourceExcerptView,
  AuthSession,
  BrainView,
  BrainSourceResult,
  BrainSourceBrowse,
  BrainSourceRoot,
  BrainSourceReview,
  CapabilityContainmentView,
  CapabilityDecisionMode,
  CapabilityGate,
  ContainedSubject,
  ContextUsage,
  Checkpoint,
  ComposerApprovalModeSettings,
  CodeMapStatus,
  CodeReposView,
  CredentialLifecycle,
  ConnectionsView,
  ConnectorStoreView,
  HostActionResult,
  HostStatusView,
  UpdateCheckResult,
  UpdateStatusView,
  Diagnostics,
  DiagnosticsExport,
  EventEntry,
  ExecutionEnvironmentsView,
  ExtensionsOverview,
  InterruptRequestBody,
  InstanceLaunchResult,
  InterruptResult,
  McpAgentAccess,
  McpServer,
  McpSession,
  McpFinding,
  Notification,
  MemoryControlView,
  MemoryProposal,
  MemoryHistoryEvent,
  MemorySettingsView,
  ModelPricingView,
  ModelReadinessView,
  ModelSetupState,
  SetupState,
  ModelOperation,
  PartialFiles,
  PluginsView,
  RuntimeInstallPlan,
  ModelLibraryView,
  HuggingFaceSearchResult,
  HuggingFaceVariant,
  HuggingFaceDownloadPreview,
  HuggingFaceDownloadResult,
  ModelConversionPreview,
  ModelCapacitiesView,
  ModelsView,
  PasswordRecoveryBeginResult,
  ProjectDetail,
  ProjectFilesView,
  ProjectTreeNode,
  ProjectsList,
  PromptAttachment,
  PromptRequestBody,
  ProviderModelList,
  ProviderWeeklyUsageView,
  ResolveApprovalResult,
  ResumableTurnsView,
  ResolveCriticalApprovalResult,
  RestorePlan,
  RuntimeMode,
  RuntimeReadiness,
  SecurityHealth,
  SessionAttachmentsView,
  SessionDetail,
  SessionSummary,
  SkillMutationResult,
  SkillVerification,
  SkillView,
  StandingGrant,
  StreamEvent,
  TaskView,
  TranscriptExportManifest,
  TurnDetail,
  TurnSourceExcerptView,
  TurnSourcesView,
  UploadedAttachment,
  WebBlocklist,
  WebBlocklistProbe,
  GitCredentialStatus,
} from "./apiTypes";
import type { ApprovalMode } from "./approvalMode";

// Bearer token held in memory only — never localStorage/sessionStorage (security requirement).
let token: string | null = null;

export function setToken(value: string | null): void {
  token = value;
}

export function hasToken(): boolean {
  return token !== null;
}

export function getToken(): string | null {
  return token;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly reasonCode: string | null,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (token !== null) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const resp = await fetch(instancePath(path), { ...init, headers });
  if (!resp.ok) {
    let reasonCode: string | null = null;
    try {
      const body = await resp.json();
      const detail = body?.detail ?? body;
      reasonCode = detail?.reason_code ?? null;
    } catch {
      /* non-JSON error response */
    }
    throw new ApiError(
      resp.status,
      reasonCode,
      `Request failed: ${resp.status} ${path}`,
    );
  }
  return (await resp.json()) as T;
}

async function requestBlob(
  path: string,
  init: RequestInit = {},
): Promise<Blob> {
  const headers = new Headers(init.headers);
  if (token !== null) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const resp = await fetch(instancePath(path), { ...init, headers });
  if (!resp.ok) {
    let reasonCode: string | null = null;
    try {
      const body = await resp.json();
      const detail = body?.detail ?? body;
      reasonCode = detail?.reason_code ?? null;
    } catch {
      /* non-JSON error response */
    }
    throw new ApiError(
      resp.status,
      reasonCode,
      `Request failed: ${resp.status} ${path}`,
    );
  }
  return resp.blob();
}

function instancePath(path: string): string {
  if (typeof window === "undefined") return path;
  const match = window.location.pathname.match(/^(\/instances\/[^/]+)/);
  return match ? `${match[1]}${path}` : path;
}

function withQuery(
  path: string,
  params: Record<string, string | number | undefined>,
): string {
  const q = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") q.set(key, String(value));
  }
  const suffix = q.toString();
  return suffix ? `${path}?${suffix}` : path;
}

function postJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/** Mint a bearer token for the local owner principal and hold it in memory. */
export async function connect(): Promise<AuthSession> {
  const session = await postJson<AuthSession>("/api/auth/session", {
    as_principal: null,
  });
  setToken(session.token);
  return session;
}

// ── Lock screen: local-account auth ─────────────────────────────────────────

export type HealthView = {
  status: string;
  /** "ok" when the encrypted store opens and reads; "unavailable" otherwise. */
  store?: string;
  /** Stable code for an unavailable store, e.g. store_memory_lock_unavailable. */
  reason?: string;
  detail?: string;
  cipher_memory_security?: string;
  memory_security_mode?: "auto" | "on" | "off";
  memory_security_probe?: "supported" | "failed" | "not_run";
  memory_security_reason?: string;
  memory_security_checked_at?: string | null;
  sqlcipher_version?: string | null;
};

/**
 * Privacy-safe pre-auth reachability probe. `/api/health` is the only
 * unauthenticated read: it names whether the server answers and whether the
 * encrypted store opens, and nothing else about the workspace. Both facts are
 * needed pre-auth, because a store that will not open is exactly what makes
 * every sign-in fail (BUG-86) — reporting only reachability let the lock
 * screen call the runtime operational while refusing every attempt.
 */
export function health(): Promise<HealthView> {
  return request<HealthView>("/api/health");
}

export function createInstance(
  name: string,
  username: string,
  password: string,
): Promise<InstanceLaunchResult> {
  return postJson<InstanceLaunchResult>("/api/instances", {
    name,
    username,
    password,
  });
}

export interface LoginResult {
  stage: "session" | "mfa_required";
  principal_id: string;
  token: string | null;
  ticket: string | null;
}

/** On a full 'session' result the bearer token is stored in memory. */
function adoptSession(result: LoginResult): LoginResult {
  if (result.stage === "session" && result.token) {
    setToken(result.token);
  }
  return result;
}

export const auth = {
  register: (username: string, password: string) =>
    postJson<LoginResult>("/api/auth/register", { username, password }).then(
      adoptSession,
    ),
  login: (username: string, password: string) =>
    postJson<LoginResult>("/api/auth/login", { username, password }).then(
      adoptSession,
    ),
  verifyMfa: (ticket: string, code: string) =>
    postJson<LoginResult>("/api/auth/mfa/verify", { ticket, code }).then(
      adoptSession,
    ),
  bootstrapStatus: () =>
    request<{ can_register: boolean }>("/api/auth/bootstrap-status"),
  beginPasswordRecovery: (username: string) =>
    postJson<PasswordRecoveryBeginResult>("/api/auth/password-recovery/begin", {
      username,
    }),
  completePasswordRecovery: (
    ticket: string,
    code: string,
    newPassword: string,
  ) =>
    postJson<{ ok: boolean }>("/api/auth/password-recovery/complete", {
      ticket,
      code,
      new_password: newPassword,
    }),
  logout: async () => {
    try {
      await postJson<{ ok: boolean }>("/api/auth/logout", {});
    } finally {
      setToken(null);
    }
  },
  elevate: (password?: string, mfaCode?: string) =>
    postJson<{ token: string }>("/api/auth/elevate", {
      password,
      mfa_code: mfaCode,
    }),
  enrollMfa: () =>
    postJson<{
      secret: string;
      provisioning_uri: string;
      backup_codes: string[];
    }>("/api/auth/mfa/enroll", {}),
  activateMfa: (code: string) =>
    postJson<{ ok: boolean }>("/api/auth/mfa/activate", { code }),
  changePassword: (oldPassword: string, newPassword: string) =>
    postJson<{ ok: boolean }>("/api/auth/password", {
      old_password: oldPassword,
      new_password: newPassword,
    }),
  listDeviceSessions: () =>
    request<
      Array<{
        session_id: string;
        created_at: string;
        last_seen_at: string | null;
        device_label: string | null;
        revoked: boolean;
        scope: string;
        current: boolean;
      }>
    >("/api/auth/sessions"),
  revokeDeviceSession: (sessionId: string) =>
    postJson<{ ok: boolean }>(
      `/api/auth/sessions/${encodeURIComponent(sessionId)}/revoke`,
      {},
    ),
  deleteAccount: () =>
    request<{ ok: boolean }>("/api/account", { method: "DELETE" }),
};

export interface SettingsView {
  settings: Record<string, unknown>;
  status: { vault: string; mfa_enrolled: boolean; username: string };
}

export const api = {
  // ── Local-account settings, vault key, MFA status ──
  settings: () => request<SettingsView>("/api/settings"),
  composerApprovalMode: () =>
    request<ComposerApprovalModeSettings>(
      "/api/settings/composer-approval-mode",
    ),
  setComposerApprovalMode: (mode: ApprovalMode) =>
    request<ComposerApprovalModeSettings>(
      "/api/settings/composer-approval-mode",
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approval_mode: mode }),
      },
    ),
  putSettings: (settings: Record<string, unknown>) =>
    request<{ settings: Record<string, unknown> }>("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ settings }),
    }),
  vaultStatus: () => request<{ state: string }>("/api/vault/status"),
  setVaultKey: (key: string, mfaCode?: string) =>
    request<{ state: string }>("/api/vault/key", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key, mfa_code: mfaCode }),
    }),
  clearVaultKey: (mfaCode?: string) =>
    request<{ state: string }>("/api/vault/key", {
      method: "DELETE",
      headers: mfaCode ? { "X-MFA-Code": mfaCode } : undefined,
    }),

  // ── Read-only governed views ──
  sessionContextUsage: (sessionId: string) =>
    request<ContextUsage>(
      `/api/sessions/${encodeURIComponent(sessionId)}/context-usage`,
    ),
  // B6 — the agent's standing plan for one conversation, so a reload or a
  // second tab picks the checklist back up instead of starting blank.
  sessionPlan: (sessionId: string) =>
    request<AgentPlan>(`/api/sessions/${encodeURIComponent(sessionId)}/plan`),
  capabilityGates: () => request<CapabilityGate[]>("/api/capability-gates"),
  capabilityGate: (capability: string) =>
    request<CapabilityGate>(
      `/api/capability-gates/${encodeURIComponent(capability)}`,
    ),
  runtimeMode: () => request<RuntimeMode>("/api/runtime-mode"),
  // ── Host lifecycle (BUG-40) ──
  // The menu-bar control's contract: what state the host is in, what background
  // work is in flight, and the four actions the distribution design requires.
  // Quit and Restart report waiting work first and only stop once confirmed.
  host: () => request<HostStatusView>("/api/host"),
  pauseHost: (reason?: string) =>
    postJson<HostActionResult>("/api/host/pause", { reason: reason ?? null }),
  resumeHost: () => postJson<HostActionResult>("/api/host/resume", {}),
  quitHost: (confirm = false) =>
    postJson<HostActionResult>("/api/host/quit", { confirm }),
  restartHost: (confirm = false) =>
    postJson<HostActionResult>("/api/host/restart", { confirm }),
  // ── Install provenance and the signed update channel (BUG-44) ──
  // The read is local only: opening the panel must never be a way to cause an
  // outbound request. The check is the one that asks, and only when the owner
  // has pinned a channel.
  hostUpdate: () => request<UpdateStatusView>("/api/host/update"),
  checkHostUpdate: () =>
    postJson<UpdateCheckResult>("/api/host/update/check", {}),
  runtimeReadiness: () => request<RuntimeReadiness>("/api/runtime-readiness"),
  diagnostics: () => request<Diagnostics>("/api/diagnostics"),
  models: () => request<ModelsView>("/api/models"),
  weeklyModelUsage: (refreshNative = false) =>
    request<ProviderWeeklyUsageView>(
      withQuery("/api/models/weekly-usage", {
        refresh_native: refreshNative ? "true" : undefined,
      }),
    ),
  setWeeklyModelBudget: (profileId: string, tokenBudget: number | null) =>
    request<{ ok: boolean; profile_id: string }>(
      `/api/models/${encodeURIComponent(profileId)}/weekly-budget`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token_budget: tokenBudget }),
      },
    ),
  modelReadiness: () =>
    request<{ items: ModelReadinessView[] }>("/api/model-readiness"),
  checkModelReadiness: (profile_id: string, model: string) =>
    postJson<ModelReadinessView>("/api/model-readiness/check", {
      profile_id,
      model,
    }),
  // Where each work surface's model picker starts. A preference only: the turn
  // still names its exact profile and model, and readiness judges that pair.
  surfaceModels: () =>
    request<{ surfaces: Record<string, { profile_id: string; model: string }> }>(
      "/api/surface-models",
    ),
  setSurfaceModel: (surface: string, profile_id: string, model: string) =>
    request<{ ok: boolean }>("/api/surface-models", {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ surface, profile_id, model }),
    }),
  modelSetup: () => request<ModelSetupState>("/api/model-setup"),
  updateModelSetup: (
    body: Omit<
      ModelSetupState,
      "owner_principal_id" | "created_at" | "updated_at"
    >,
  ) =>
    request<ModelSetupState>("/api/model-setup", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  setup: () => request<SetupState>("/api/setup"),
  updateSetup: (
    body: Omit<SetupState, "owner_principal_id" | "privacy_acknowledged_at" | "backup_verified_at" | "created_at" | "updated_at">,
  ) => request<SetupState>("/api/setup", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }),
  createSetupBackup: (target: string) =>
    postJson<{ ok: boolean; path: string; setup: SetupState }>("/api/setup/backup/create", { target }),
  modelLibrary: () => request<ModelLibraryView>("/api/model-library"),
  addModelLibraryRoot: (path: string) =>
    postJson<{ ok: boolean; path: string }>("/api/model-library/roots", {
      path,
    }),
  removeModelLibraryRoot: (path: string) =>
    request<{ ok: boolean }>("/api/model-library/roots", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    }),
  rescanModelLibrary: () =>
    postJson<{ ok: boolean; models: ModelLibraryView["models"] }>(
      "/api/model-library/rescan",
      {},
    ),
  deployLocalModel: (modelId: string) =>
    postJson<ModelOperation>(
      `/api/model-library/${encodeURIComponent(modelId)}/deploy`,
      {},
    ),
  modelOperations: () =>
    request<{ items: ModelOperation[] }>("/api/model-operations"),
  previewModelOperation: (kind: ModelOperation["kind"], target: string) =>
    postJson<
      | RuntimeInstallPlan
      | { kind: string; target: string; action: string; confirmed: false }
    >("/api/model-operations/preview", { kind, target, confirmed: false }),
  pullOllamaModel: (model: string) =>
    postJson<ModelOperation>("/api/ollama/pull", { model, confirmed: true }),
  cancelModelOperation: (operationId: string) =>
    postJson<ModelOperation>(
      `/api/model-operations/${encodeURIComponent(operationId)}/cancel`,
      {},
    ),
  retryModelOperation: (operationId: string) =>
    postJson<ModelOperation>(
      `/api/model-operations/${encodeURIComponent(operationId)}/retry`,
      {},
    ),
  partialFiles: (operationId: string) =>
    request<PartialFiles>(
      `/api/model-operations/${encodeURIComponent(operationId)}/partial-files`,
    ),
  deletePartialFiles: (operationId: string) =>
    postJson<PartialFiles & { ok: boolean }>(
      `/api/model-operations/${encodeURIComponent(operationId)}/delete-partial-files?confirmed=true`,
      {},
    ),
  cleanupModelOperation: (operationId: string) =>
    request<{ ok: boolean }>(
      `/api/model-operations/${encodeURIComponent(operationId)}`,
      { method: "DELETE" },
    ),
  saveHuggingFaceCredential: (token: string) =>
    request<{ configured: boolean }>("/api/hugging-face/credential", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    }),
  trendingHuggingFace: () =>
    request<{ items: HuggingFaceSearchResult[] }>("/api/hugging-face/trending"),
  searchHuggingFace: (query: string) =>
    request<{ items: HuggingFaceSearchResult[] }>(
      withQuery("/api/hugging-face/search", { query }),
    ),
  huggingFaceVariants: (repoId: string) => {
    const [owner, repository] = repoId.split("/", 2);
    return request<{ items: HuggingFaceVariant[] }>(
      `/api/hugging-face/${encodeURIComponent(owner)}/${encodeURIComponent(repository)}/variants`,
    );
  },
  previewHuggingFaceDownload: (
    variant: HuggingFaceVariant,
    destination?: string,
  ) =>
    postJson<HuggingFaceDownloadPreview>("/api/hugging-face/download/preview", {
      repo_id: variant.repo_id,
      revision: variant.revision,
      files: variant.files,
      destination: destination || null,
      confirmed: false,
    }),
  downloadHuggingFaceModel: (
    variant: HuggingFaceVariant,
    destination: string,
  ) =>
    postJson<HuggingFaceDownloadResult>("/api/hugging-face/download", {
      repo_id: variant.repo_id,
      revision: variant.revision,
      files: variant.files,
      destination,
      confirmed: true,
    }),
  previewModelConversion: (
    source: string,
    output: string,
    revision: string,
    quantization: string,
  ) =>
    postJson<ModelConversionPreview>("/api/model-conversion/preview", {
      source,
      output,
      revision,
      quantization,
      confirmed: false,
    }),
  startModelConversion: (
    source: string,
    output: string,
    revision: string,
    quantization: string,
  ) =>
    postJson<ModelOperation>("/api/model-conversion", {
      source,
      output,
      revision,
      quantization,
      confirmed: true,
    }),
  modelCapacities: () => request<ModelCapacitiesView>("/api/models/capacities"),
  refreshModelCapacities: (force = false) =>
    postJson<{
      ok: boolean;
      profiles: Array<{
        profile_id: string;
        status: string;
        reason_code: string | null;
      }>;
    }>(
      withQuery("/api/models/capacities/refresh", {
        force: force ? "true" : undefined,
      }),
      {},
    ),
  setModelCapacity: (
    profileId: string,
    model: string,
    tokens: number | null,
    reason: string,
  ) =>
    request<{
      ok: boolean;
      profile_id: string;
      model: string;
      tokens: number | null;
    }>(`/api/models/${encodeURIComponent(profileId)}/capacity`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model, tokens, reason }),
    }),
  // Read-only status of governed service connectors (never reaches the network;
  // never exposes a credential value). Enabling one is done via the capability
  // gate + decision-mode control plane, not here.
  connections: () => request<ConnectionsView>("/api/connections"),
  // ── Local MCP servers (Control Deck task 4b) ────────────────────────────
  // Owner-scoped. Create and test-connect run through the governed capability
  // (a disabled gate returns 403 disabled_by_capability_gate); rename and
  // delete are human-only owner-scoped operations.
  mcpServers: () => request<McpServer[]>("/api/mcp/servers"),
  // Whether a connected server's tools can actually be called in a turn. The
  // handshake and the agent's reach are separate facts, so the page states both.
  mcpAgentAccess: () => request<McpAgentAccess>("/api/mcp/agent-access"),
  createMcpServer: (name: string, template: string) =>
    postJson<{ ok: boolean; server_id: string | null; name: string | null }>(
      "/api/mcp/servers",
      { name, template },
    ),
  connectMcpServer: (serverId: string) =>
    postJson<{ ok: boolean; status: string; tools: string[] }>(
      `/api/mcp/servers/${encodeURIComponent(serverId)}/connect`,
      {},
    ),
  renameMcpServer: (serverId: string, name: string) =>
    request<{ ok: boolean; name: string }>(
      `/api/mcp/servers/${encodeURIComponent(serverId)}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      },
    ),
  deleteMcpServer: (serverId: string) =>
    request<{ ok: boolean; server_id: string }>(
      `/api/mcp/servers/${encodeURIComponent(serverId)}`,
      { method: "DELETE" },
    ),
  createRemoteMcpServer: (
    name: string,
    endpoint_url: string,
    auth_ref: string | null,
  ) =>
    postJson<{ ok: boolean; server_id: string | null; name: string | null }>(
      "/api/mcp/servers/remote",
      { name, endpoint_url, auth_ref },
    ),
  mcpSessions: (serverId: string) =>
    request<McpSession[]>(
      `/api/mcp/servers/${encodeURIComponent(serverId)}/sessions`,
    ),
  mcpFindings: (serverId: string) =>
    request<McpFinding[]>(
      `/api/mcp/servers/${encodeURIComponent(serverId)}/findings`,
    ),
  pauseMcpServer: (serverId: string) =>
    postJson<{ ok: boolean; monitor_state: string }>(
      `/api/mcp/servers/${encodeURIComponent(serverId)}/pause`,
      {},
    ),
  resumeMcpServer: (serverId: string) =>
    postJson<{ ok: boolean; monitor_state: string }>(
      `/api/mcp/servers/${encodeURIComponent(serverId)}/resume`,
      {},
    ),
  notifications: () => request<Notification[]>("/api/notifications"),
  markNotificationRead: (id: string) =>
    postJson<{ ok: boolean }>(
      `/api/notifications/${encodeURIComponent(id)}/read`,
      {},
    ),
  standingGrants: (includeInactive = true) =>
    request<{ ok: boolean; grants: StandingGrant[] }>(
      `/api/standing-grants?include_inactive=${includeInactive ? "true" : "false"}`,
    ),
  createStandingGrant: (body: {
    action_type: string;
    risk_ceiling: string;
    tool_name?: string;
    scope_pattern?: string;
    reason?: string;
    ttl_days?: number;
  }) =>
    postJson<{ ok: boolean; grant: StandingGrant }>(
      "/api/standing-grants",
      body,
    ),
  revokeStandingGrant: (grantId: string) =>
    postJson<{ ok: boolean; grant_id: string }>(
      `/api/standing-grants/${encodeURIComponent(grantId)}/revoke`,
      {},
    ),
  securityCredentials: () =>
    request<CredentialLifecycle[]>("/api/security/credentials"),
  securityFindings: () => request<McpFinding[]>("/api/security/findings"),
  securityHealth: () => request<SecurityHealth[]>("/api/security/health"),
  capabilityContainment: () =>
    request<CapabilityContainmentView>("/api/security/containment"),
  setCapabilityContainment: (
    capability: string,
    subjectId: string,
    action: "pause" | "kill" | "resume",
  ) =>
    postJson<ContainedSubject>(
      `/api/security/containment/${encodeURIComponent(capability)}/` +
        `${encodeURIComponent(subjectId)}/${action}`,
      {},
    ),
  plugins: () => request<PluginsView>("/api/plugins"),
  verifySecurityCredential: (provider: string) =>
    postJson<CredentialLifecycle>(
      `/api/security/credentials/${encodeURIComponent(provider)}/verify`,
      {},
    ),
  scanSecurity: () => postJson<McpFinding[]>("/api/security/scan", {}),
  checkSecurityHealth: () =>
    postJson<SecurityHealth[]>("/api/security/health-check", {}),
  checkPasswordBreach: (password: string, enabled: boolean) =>
    postJson<McpFinding[]>("/api/security/breach-check", { password, enabled }),
  connectorStore: () => request<ConnectorStoreView>("/api/connector-store"),
  installConnector: (connectorId: string) =>
    postJson<{ ok: boolean; installed: boolean }>(
      `/api/connector-store/${encodeURIComponent(connectorId)}/install`,
      {},
    ),
  uninstallConnector: (connectorId: string) =>
    request<{ ok: boolean; installed: boolean }>(
      `/api/connector-store/${encodeURIComponent(connectorId)}`,
      { method: "DELETE" },
    ),
  setConnectorCredentials: (
    connectorId: string,
    values: Record<string, string>,
    expiresAt?: string,
  ) =>
    request<{ ok: boolean; auth_status: string }>(
      `/api/connector-store/${encodeURIComponent(connectorId)}/credentials`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ values, expires_at: expiresAt || null }),
      },
    ),
  setConnectorEnabled: (connectorId: string, enabled: boolean) =>
    request<{ ok: boolean; enabled: boolean }>(
      `/api/connector-store/${encodeURIComponent(connectorId)}/enabled?enabled=${enabled}`,
      { method: "PUT" },
    ),
  registerConnectorManifest: (
    connectorId: string,
    manifest: Record<string, unknown>,
  ) =>
    postJson<{ ok: boolean; operations: unknown[] }>(
      `/api/connector-store/${encodeURIComponent(connectorId)}/manifest`,
      { manifest },
    ),
  checkLanguage: (text: string) =>
    postJson<{
      status: "available" | "unavailable";
      reason_code?: string;
      matches: Array<{
        offset: number;
        length: number;
        message: string;
        replacements: string[];
        rule_id: string;
        category: string;
      }>;
    }>("/api/language/check", { text, language: "en-US" }),
  // On-demand listing of the models a provider serves (user-initiated; provider
  // policy is enforced server-side before any network contact).
  providerModels: (profileId: string) =>
    request<ProviderModelList>(
      `/api/models/${encodeURIComponent(profileId)}/provider-models`,
    ),
  // Persist (or clear, with null) the user-owned advisor model profile — the
  // model a local model may consult through the governed consult_advisor tool.
  // Gate-manager only, enforced server-side; selecting an advisor grants nothing.
  setModelAdvisor: (profile_id: string | null) =>
    request<{ ok: boolean; advisor_profile_id: string | null }>(
      "/api/model-advisor",
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile_id }),
      },
    ),
  // Persist the operator's model selection (human gate-manager only, enforced
  // server-side; placeholder profiles require a concrete model).
  selectModel: (profile_id: string, model?: string) =>
    request<{ ok: boolean; profile_id: string; model: string }>(
      "/api/model-selection",
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile_id, model: model || null }),
      },
    ),
  saveModelConnection: (
    profileId: string,
    endpoint: string,
    apiKey: string,
    adminApiKey = "",
  ) =>
    request<{ ok: boolean; connection_configured: boolean }>(
      `/api/models/${encodeURIComponent(profileId)}/connection`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          endpoint: endpoint || null,
          api_key: apiKey || null,
          admin_api_key: adminApiKey || null,
        }),
      },
    ),
  // Persist the user-owned ordered model fallback sequence (human gate-manager only,
  // enforced server-side). Returns the cleaned/de-duplicated sequence.
  setModelFallback: (profile_ids: string[]) =>
    request<{ ok: boolean; fallback_sequence: string[] }>(
      "/api/model-fallback",
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile_ids }),
      },
    ),
  // Upload one image (base64) into the governed attachment store. Validation
  // is fail-closed server-side (media-type allowlist, 5 MB cap, magic-byte
  // sniff); the response is metadata only.
  uploadAttachment: (body: {
    filename: string;
    media_type: string;
    data_base64: string;
  }) => postJson<UploadedAttachment>("/api/attachments", body),
  // ── File inspector (view-only, session-scoped) ──
  // The preview is authorized by the session that carried the attachment, so
  // these paths 404 for a file this conversation never had. Nothing here
  // uploads, mutates, or downloads.
  // ── BUG-22: conversation transcript export ──
  // The manifest is read first so the owner reviews exactly what will leave the
  // machine — which messages, which files, and the redaction policy — before a
  // format is chosen. The export itself returns the document; scope comes from
  // the authenticated session and the session id, never from the request body.
  sessionExportManifest: (sessionId: string) =>
    request<TranscriptExportManifest>(
      `/api/sessions/${encodeURIComponent(sessionId)}/export/manifest`,
    ),
  exportSession: async (
    sessionId: string,
    format: "html" | "markdown" | "pdf",
    filename: string,
  ): Promise<void> => {
    const blob = await requestBlob(
      `/api/sessions/${encodeURIComponent(sessionId)}/export`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ format }),
      },
    );
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url));
  },
  // ── BUG-21: the normalised price registry ──
  modelPricing: () => request<ModelPricingView>("/api/models/pricing"),
  refreshModelPricing: () =>
    postJson<{ ok: boolean; changes_written: number }>(
      "/api/models/pricing/refresh",
      {},
    ),
  setModelPrice: (
    profileId: string,
    body: {
      model: string;
      input_per_mtok?: string | null;
      output_per_mtok?: string | null;
      cache_write_per_mtok?: string | null;
      cache_read_per_mtok?: string | null;
      currency?: string | null;
      effective_from?: string | null;
      reason?: string | null;
    },
  ) =>
    request<{ ok: boolean }>(
      `/api/models/${encodeURIComponent(profileId)}/price`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    ),
  sessionAttachments: (sessionId: string) =>
    request<SessionAttachmentsView>(
      `/api/sessions/${encodeURIComponent(sessionId)}/attachments`,
    ),
  attachmentPreview: (sessionId: string, attachmentId: string) =>
    request<AttachmentPreview>(
      `/api/sessions/${encodeURIComponent(sessionId)}/attachments/${encodeURIComponent(attachmentId)}/preview`,
    ),
  // PDFs and images are displayed by the browser itself. Their bytes are
  // fetched with the in-memory bearer token (an <object> or <img> tag cannot
  // send one) and handed over as a same-origin blob URL; the caller revokes it
  // when the pane closes.
  attachmentPreviewObjectUrl: async (bytesPath: string): Promise<string> => {
    const blob = await requestBlob(bytesPath);
    return URL.createObjectURL(blob);
  },
  // BUG-28 — the bytes of one authorised file, for saving rather than reading.
  // Fetched with the bearer token for the same reason previews are: a bare
  // <a download> cannot send one. The server always answers
  // application/octet-stream, so nothing downloaded is ever handed to the
  // browser as something it will run.
  attachmentDownload: (
    sessionId: string,
    attachmentId: string,
  ): Promise<Blob> =>
    requestBlob(
      `/api/sessions/${encodeURIComponent(sessionId)}/attachments/${encodeURIComponent(attachmentId)}/download`,
    ),
  // BUG-27 — which exchange produced a generated file, resolved the same way
  // memory provenance is, so both surfaces give the same honest answers.
  attachmentProvenance: (sessionId: string, attachmentId: string) =>
    request<SourceExcerptView>(
      `/api/sessions/${encodeURIComponent(sessionId)}/attachments/${encodeURIComponent(attachmentId)}/provenance`,
    ),
  // C6 — what the turns in this conversation actually read. Labels and
  // locators only; the material behind a chip is fetched when it is opened.
  sessionSources: (sessionId: string) =>
    request<TurnSourcesView>(
      `/api/sessions/${encodeURIComponent(sessionId)}/sources`,
    ),
  // C4 — one cited source, opened at the passage the turn used. Resolution is
  // re-run now, so a changed or unreadable source says so instead of showing a
  // passage that is no longer there.
  // `quote` is the answer sentence an inline marker terminated, when there is
  // one: it locates the run inside a source the turn read whole.
  turnSourceExcerpt: (
    sessionId: string,
    turnId: string,
    sourceId: string,
    quote = "",
  ) =>
    request<TurnSourceExcerptView>(
      withQuery(
        `/api/sessions/${encodeURIComponent(sessionId)}/turns/${encodeURIComponent(turnId)}` +
          `/sources/${encodeURIComponent(sourceId)}/excerpt`,
        quote === "" ? {} : { quote },
      ),
    ),
  // BUG-27 — the passage a memory was drawn from. Every non-resolvable case
  // comes back as a named status rather than an error.
  memorySource: (memoryId: string) =>
    request<SourceExcerptView>(
      `/api/memory/${encodeURIComponent(memoryId)}/source`,
    ),
  events: (
    params: {
      session_id?: string;
      turn_id?: string;
      event_type?: string;
      limit?: number;
    } = {},
  ) => request<EventEntry[]>(withQuery("/api/events", params)),
  brain: () => request<BrainView>("/api/brain"),
  addBrainSource: (path: string) =>
    postJson<BrainSourceResult>("/api/brain/sources", { path }),
  /** An empty path answers with the roots themselves, not with a listing. */
  browseBrainSources: (path = "") =>
    request<BrainSourceBrowse>(
      withQuery("/api/brain/sources/browse", { path }),
    ),
  brainSourceRoots: () =>
    request<{ roots: BrainSourceRoot[] }>("/api/brain/sources/roots"),
  /** Grant one folder on this computer. Read where it is; nothing is copied. */
  grantBrainSourceFolder: (path: string) =>
    postJson<{ ok: boolean; root_id: string; path: string }>(
      "/api/brain/sources/grants",
      { path },
    ),
  revokeBrainSourceFolder: (rootId: string) =>
    request<{ ok: boolean; root_id: string }>(
      withQuery("/api/brain/sources/grants", { root_id: rootId }),
      { method: "DELETE" },
    ),
  /**
   * Copy one file from the computer into the workspace. `storeCopy` is the
   * owner's permission for the duplication and has no default on the server:
   * choosing a file is not consent to store it.
   */
  uploadBrainSourceFile: (
    filename: string,
    contentBase64: string,
    storeCopy: boolean,
  ) =>
    postJson<{ ok: boolean; path: string; stored_copy: boolean; byte_size: number }>(
      "/api/brain/sources/upload",
      { filename, content_base64: contentBase64, store_copy: storeCopy },
    ),
  reviewBrainSource: (path: string) =>
    postJson<BrainSourceReview>("/api/brain/sources/review", { path }),
  brainPreferences: () =>
    request<{ settings: Record<string, unknown> }>("/api/brain/settings"),
  saveBrainPreferences: (settings: Record<string, unknown>) =>
    request<{
      ok: boolean;
      settings: Record<string, unknown>;
      updated_at: string;
    }>("/api/brain/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ settings }),
    }),
  removeBrainSource: (path: string) =>
    request<BrainSourceResult>(withQuery("/api/brain/sources", { path }), {
      method: "DELETE",
    }),
  executionEnvironments: () =>
    request<ExecutionEnvironmentsView>("/api/execution-environments"),
  configureExecutionEnvironment: (body: {
    profile_id?: string;
    kind: "ssh" | "daytona" | "container";
    name: string;
    config: Record<string, unknown>;
    enabled: boolean;
  }) =>
    request<{ ok: boolean; profile_id: string }>(
      "/api/execution-environments/configure",
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    ),
  selectExecutionEnvironment: (profile_id: string) =>
    request<{ ok: boolean; selected_profile_id: string }>(
      "/api/execution-environments/selection",
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile_id }),
      },
    ),
  checkpoints: (sessionId?: string, projectId?: string) =>
    request<Checkpoint[]>(
      withQuery("/api/checkpoints", {
        session_id: sessionId,
        project_id: projectId,
      }),
    ),
  checkpoint: (id: string) =>
    request<Checkpoint>(`/api/checkpoints/${encodeURIComponent(id)}`),
  // Preflight only. Reading a plan performs no restore; executing one still
  // goes through the governed approval path.
  checkpointRestorePlan: (id: string) =>
    request<RestorePlan>(
      `/api/checkpoints/${encodeURIComponent(id)}/restore-plan`,
    ),
  // ── Installed skills (Extensions → Skills) ───────────────────────────
  // A skill is instruction text the owner installs; it grants no capability and
  // runs nothing. `verifySkillUrl` reads a linked document and reports what it
  // is without storing it, so Chat and Build can offer an informed import.
  skills: () =>
    request<{ skills: SkillView[] }>("/api/skills").then((body) => body.skills),
  uploadSkill: (filename: string, data_base64: string) =>
    postJson<SkillMutationResult>("/api/skills", { filename, data_base64 }),
  verifySkillUrl: (url: string) =>
    postJson<SkillVerification>("/api/skills/verify", { url }),
  importSkillUrl: (url: string) =>
    postJson<SkillMutationResult>("/api/skills/import", { url }),
  buildSkill: (name: string, description: string, body: string) =>
    postJson<SkillMutationResult>("/api/skills/build", {
      name,
      description,
      body,
    }),
  renameSkill: (id: string, name: string) =>
    request<{ ok: boolean; skill_id: string; name: string }>(
      `/api/skills/${encodeURIComponent(id)}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      },
    ),
  setSkillActive: (id: string, active: boolean) =>
    request<{ ok: boolean; skill_id: string; active: boolean }>(
      `/api/skills/${encodeURIComponent(id)}/active`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active }),
      },
    ),
  downloadSkill: (id: string) =>
    requestBlob(`/api/skills/${encodeURIComponent(id)}/download`),
  deleteSkill: (id: string) =>
    request<{ ok: boolean; skill_id: string }>(
      `/api/skills/${encodeURIComponent(id)}`,
      {
        method: "DELETE",
      },
    ),

  extensions: () => request<ExtensionsOverview>("/api/extensions"),
  projectFiles: (id: string) =>
    request<ProjectFilesView>(`/api/projects/${encodeURIComponent(id)}/files`),
  diagnosticsExport: () =>
    request<DiagnosticsExport>("/api/diagnostics/export"),
  // `origin: "chat"` narrows the list to conversations the owner typed. Task
  // runs live in a server-owned session that is still listed in Sessions; it is
  // only "recent chats" that must mean chats (BUG-10).
  sessions: (projectId?: string, includeArchived = false, origin?: string) =>
    request<SessionSummary[]>(
      withQuery("/api/sessions", {
        project_id: projectId,
        include_archived: includeArchived ? "true" : undefined,
        origin,
      }),
    ),
  searchChats: (q: string) =>
    request<SessionSummary[]>(withQuery("/api/chat-search", { q })),

  // ── Web access (RAIKER-2021) ─────────────────────────────────────────
  // What web reads may not reach. The address guard that refuses private and
  // loopback destinations is not represented here because it is not editable —
  // the read below reports it so the page can say so.
  webBlocklist: () => request<WebBlocklist>("/api/web-access/blocklist"),
  addWebBlocklistRule: (rule: string, note = "") =>
    request<{ rule_id: string; rule: string; kind: string }>("/api/web-access/blocklist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rule, note }),
    }),
  deleteWebBlocklistRule: (ruleId: string) =>
    request<{ deleted: boolean }>(`/api/web-access/blocklist/${encodeURIComponent(ruleId)}`, {
      method: "DELETE",
    }),
  testWebBlocklist: (host: string) =>
    request<WebBlocklistProbe>("/api/web-access/blocklist/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ host }),
    }),

  // ── Git credential (RAIKER-2022) ─────────────────────────────────────
  // The token is write-only across this boundary: it goes up, and no read ever
  // returns it.
  gitCredential: (sessionId?: string) =>
    request<GitCredentialStatus>(
      withQuery("/api/git-credential", sessionId ? { session_id: sessionId } : {}),
    ),
  putGitCredential: (token: string) =>
    request<GitCredentialStatus>("/api/git-credential", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    }),
  deleteGitCredential: () =>
    request<GitCredentialStatus>("/api/git-credential", { method: "DELETE" }),
  grantGitCredential: (scope: string, sessionId?: string) =>
    request<GitCredentialStatus>("/api/git-credential/grant", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scope, session_id: sessionId ?? null }),
    }),
  revokeGitCredential: () =>
    request<GitCredentialStatus>("/api/git-credential/grant", { method: "DELETE" }),

  // ── Reliable memory controls (backlog item 3) ────────────────────────
  // User-facing surface over the existing governed memory store. List carries
  // provenance/scope/sensitivity/confidence/retention + pin; forget reuses
  // the governed forget path (human-only); incognito withholds approved
  // project memory from the turn context.
  memories: (scope?: string) =>
    request<MemoryControlView[]>(withQuery("/api/memory", { scope })),
  memoryProposals: () => request<MemoryProposal[]>("/api/memory/proposals"),
  decideMemoryProposal: (
    id: string,
    body: {
      decision: "approved" | "rejected";
      edited_text?: string;
      reason?: string;
      expected_decision: string;
    },
  ) =>
    postJson<{
      ok: boolean;
      candidate_id: string;
      decision: string;
      memory_id?: string;
    }>(`/api/memory/proposals/${encodeURIComponent(id)}/decision`, body),
  memoryHistory: (id: string) =>
    request<{ ok: boolean; memory_id: string; events: MemoryHistoryEvent[] }>(
      `/api/memory/${encodeURIComponent(id)}/history`,
    ),
  changeMemoryScope: (
    id: string,
    scope: string,
    expectedUpdatedAt: string | null,
    reason: string,
  ) =>
    request<{
      ok: boolean;
      memory_id: string;
      scope: string;
      updated_at: string;
    }>(`/api/memory/${encodeURIComponent(id)}/scope`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scope,
        expected_updated_at: expectedUpdatedAt,
        reason,
      }),
    }),
  previewMemoryPurge: (id: string) =>
    request<{
      ok: boolean;
      memory_id: string;
      artifacts: string[];
      backup_disposition: string;
      requires_confirmation: string;
    }>(`/api/memory/${encodeURIComponent(id)}/purge-preview`),
  purgeMemory: (id: string) =>
    request<{ ok: boolean; memory_id: string; purged: boolean }>(
      `/api/memory/${encodeURIComponent(id)}/purge`,
      { method: "DELETE", headers: { "X-Memory-Purge-Confirm": id } },
    ),
  setMemoryPinned: (id: string, pinned: boolean) =>
    request<{ ok: boolean; memory_id: string; pinned: boolean }>(
      `/api/memory/${encodeURIComponent(id)}/pin`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pinned }),
      },
    ),
  editMemory: (id: string, text: string) =>
    request<{ ok: boolean; memory_id: string }>(
      `/api/memory/${encodeURIComponent(id)}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      },
    ),
  setMemorySearchEnabled: (id: string, enabled: boolean) =>
    request<{ ok: boolean; memory_id: string; search_enabled: boolean }>(
      `/api/memory/${encodeURIComponent(id)}/search`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      },
    ),
  setMemoryExpiry: (id: string, expiresAt: string | null) =>
    request<{ ok: boolean; memory_id: string; expires_at: string | null }>(
      `/api/memory/${encodeURIComponent(id)}/expiry`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expires_at: expiresAt }),
      },
    ),
  exportMemories: () =>
    request<{ ok: boolean; memories: MemoryControlView[] }>(
      "/api/memory/export",
    ),
  importMemories: (
    memories: Array<Partial<MemoryControlView> & { text: string }>,
  ) =>
    request<{ ok: boolean; count: number }>("/api/memory/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ memories }),
    }),
  forgetMemory: (id: string) =>
    request<{ ok: boolean; memory_id: string }>(
      `/api/memory/${encodeURIComponent(id)}`,
      { method: "DELETE" },
    ),
  memorySettings: () => request<MemorySettingsView>("/api/memory/settings"),
  setMemoryIncognito: (incognito: boolean) =>
    request<{ ok: boolean; incognito: boolean }>("/api/memory/incognito", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ incognito }),
    }),

  // ── Build workspace repositories ────────────────────────────────────────
  // References only. A local folder must resolve inside the workspace (fail
  // closed server-side); a GitHub repository records an `owner/repo` coordinate
  // and performs no network call — its content still reaches a turn through the
  // brokered `github_read` tool under the connector_github_runtime gate.
  codeRepos: () => request<CodeReposView>("/api/code/repos"),
  connectLocalRepo: (path: string) =>
    postJson<{ ok: boolean; repo_id: string; local_subpath: string }>(
      "/api/code/repos",
      {
        kind: "local",
        path,
      },
    ),
  connectGithubRepo: (owner: string, repo: string, branch?: string) =>
    postJson<{
      ok: boolean;
      repo_id: string;
      label: string;
      branch: string | null;
    }>("/api/code/repos", {
      kind: "github",
      owner,
      repo,
      branch: branch || null,
    }),
  selectCodeRepo: (repo_id: string | null) =>
    request<{ ok: boolean; selected_repo_id: string | null }>(
      "/api/code/repos/selection",
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_id }),
      },
    ),
  disconnectCodeRepo: (repoId: string) =>
    request<{ ok: boolean; repo_id: string }>(
      `/api/code/repos/${encodeURIComponent(repoId)}`,
      { method: "DELETE" },
    ),

  // B9 — the code map over the selected repository. Reading its state is
  // metadata only; rebuilding fails closed with a reason when the owner has the
  // `code_map_indexing` capability turned off.
  codeMap: () => request<CodeMapStatus>("/api/code/map"),
  rebuildCodeMap: () =>
    postJson<{
      ok: boolean;
      status: string;
      file_count: number;
      symbol_count: number;
    }>("/api/code/map/rebuild", {}),

  // ── Projects (organizing scopes; creating/selecting one grants nothing) ──
  projects: () => request<ProjectsList>("/api/projects"),
  project: (id: string) =>
    request<ProjectDetail>(`/api/projects/${encodeURIComponent(id)}`),
  exportProject: async (id: string): Promise<void> => {
    const path = `/api/projects/${encodeURIComponent(id)}/export`;
    const blob = await requestBlob(path, { method: "POST" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `project-${id}.jsonl`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url));
  },
  // Create a named project for the authenticated local human.
  // The root subpath is derived and contained server-side — no path is sent.
  createProject: (name: string) =>
    postJson<{
      ok: boolean;
      project_id: string;
      name: string;
      root_subpath: string;
    }>("/api/projects", { name }),
  // Set (or clear, with null) the active project; new sessions are stamped with it.
  selectProject: (project_id: string | null) =>
    request<{ ok: boolean; active_project_id: string | null }>(
      "/api/projects/selection",
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_id }),
      },
    ),
  deleteProject: (id: string, confirmed = false) =>
    request<{ ok: boolean }>(`/api/projects/${encodeURIComponent(id)}`, {
      method: "DELETE",
      headers: confirmed ? { "X-Project-Delete-Confirm": id } : undefined,
    }),
  saveProjectContext: (
    id: string,
    context: {
      instructions: string;
      attachment_ids: string[];
      memory_enabled: boolean;
      memory_mode: "inherit" | "enabled" | "disabled";
    },
  ) =>
    request<{ ok: boolean }>(
      `/api/projects/${encodeURIComponent(id)}/context`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(context),
      },
    ),
  // Nested projects/folders: tree, move, archive
  projectTree: () => request<ProjectTreeNode[]>("/api/projects/tree"),
  moveProject: (id: string, parent_id: string | null) =>
    request<{ ok: boolean; project_id: string; new_parent_id: string | null }>(
      `/api/projects/${encodeURIComponent(id)}/move`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ parent_id }),
      },
    ),
  archiveProject: (id: string) =>
    request<{ ok: boolean; project_id: string }>(
      `/api/projects/${encodeURIComponent(id)}/archive`,
      { method: "PUT" },
    ),
  session: (id: string) =>
    request<SessionDetail>(`/api/sessions/${encodeURIComponent(id)}`),
  renameSession: (id: string, title: string) =>
    request<{ ok: boolean; session_id: string; title: string }>(
      `/api/sessions/${encodeURIComponent(id)}/rename`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      },
    ),
  archiveSession: (id: string) =>
    request<{ ok: boolean; session_id: string; archived: boolean }>(
      `/api/sessions/${encodeURIComponent(id)}/archive`,
      { method: "PUT" },
    ),
  unarchiveSession: (id: string) =>
    request<{ ok: boolean; session_id: string; archived: boolean }>(
      `/api/sessions/${encodeURIComponent(id)}/unarchive`,
      { method: "PUT" },
    ),
  // Pin (or unpin) a session. Organizing label only — grants nothing.
  setSessionPinned: (id: string, pinned: boolean) =>
    request<{ ok: boolean; session_id: string; pinned: boolean }>(
      `/api/sessions/${encodeURIComponent(id)}/pin`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pinned }),
      },
    ),
  // Permanently delete one session and its cascaded rows. Requires the explicit
  // confirmation header (mirrors project deletion). Human-only; an account
  // cannot delete another account's session.
  deleteSession: (id: string) =>
    request<{ ok: boolean; session_id: string }>(
      `/api/sessions/${encodeURIComponent(id)}`,
      {
        method: "DELETE",
        headers: { "X-Session-Delete-Confirm": id },
      },
    ),
  deleteSessions: (session_ids: string[]) =>
    request<{ ok: boolean; session_ids: string[] }>("/api/sessions/bulk", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_ids }),
    }),
  // Replace the tag set for one session. Tags are organizing labels only —
  // they grant nothing. The server normalizes (trim, lowercase, dedupe,
  // length/count caps). Human-only; an account cannot retag another account's
  // session.
  setSessionTags: (id: string, tags: string[]) =>
    request<{ ok: boolean; session_id: string; tags: string[] }>(
      `/api/sessions/${encodeURIComponent(id)}/tags`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tags }),
      },
    ),
  // Move one chat into a project, or out of every project with a null
  // project_id. A project is an organizing scope — the move grants nothing and
  // only changes the bounded context the chat receives on its next turn.
  // Human-only; an account cannot move another account's chat.
  setSessionProject: (id: string, project_id: string | null) =>
    request<{ ok: boolean; session_id: string; project_id: string | null }>(
      `/api/sessions/${encodeURIComponent(id)}/project`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_id }),
      },
    ),
  turn: (id: string) =>
    request<TurnDetail>(`/api/turns/${encodeURIComponent(id)}`),
  // `project_id` scopes the list to one project's schedules (project-scoped
  // schedules); omitting it lists every task visible to the account.
  tasks: (
    params: { session_id?: string; status?: string; project_id?: string } = {},
  ) => request<TaskView[]>(withQuery("/api/tasks", params)),
  createTask: (body: {
    title: string;
    description: string;
    priority?: string;
    scheduled_at?: string;
    recurrence?: string;
    parent_task_id?: string;
    // Create the task under a specific project. Omitted → the active project.
    project_id?: string | null;
    model_profile?: string;
    model?: string;
    attachments?: PromptAttachment[];
  }) => postJson<TaskView>("/api/tasks", body),
  // BUG-64 — creation alone does not execute model-proposed work. This is the
  // owner's separate, explicit intent to make one parked task due now.
  runTask: (taskId: string) =>
    postJson<TaskView>(`/api/tasks/${encodeURIComponent(taskId)}/run`, {}),
  // BUG-25 — ask the host to continue one parked scheduled run now. The
  // scheduler does this on its own tick; this is the owner's retry for when
  // automatic continuation could not proceed, and it runs the same path.
  resumeTask: (taskId: string) =>
    postJson<{
      ok: boolean;
      reason_code: string | null;
      task_status: string;
      summary: string;
    }>(`/api/tasks/${encodeURIComponent(taskId)}/resume`, {}),

  // ── Prompts / interrupts ──
  // Non-streaming prompt submit; returns the final governed AgentResponse.
  submitPrompt: (body: PromptRequestBody) =>
    postJson<AgentResponse>("/api/prompts", body),
  // Issue a governed safe-boundary interrupt for one task or all active tasks in a session.
  interrupt: (body: InterruptRequestBody) =>
    postJson<InterruptResult>("/api/interrupts", body),

  // ── Approvals (resolution is metadata-only: records a decision, never executes) ──
  approvals: (statusFilter = "pending") =>
    request<ApprovalView[]>(
      withQuery("/api/approvals", { status_filter: statusFilter }),
    ),
  approval: (id: string) =>
    request<ApprovalDetailView>(`/api/approvals/${encodeURIComponent(id)}`),
  resolveApproval: (id: string, body: { approve: boolean; reason: string }) =>
    postJson<ResolveApprovalResult>(
      `/api/approvals/${encodeURIComponent(id)}/resolve`,
      body,
    ),
  // B2 — non-streaming continuation of a turn that was parked for this approval.
  resumeAfterApproval: (id: string) =>
    postJson<AgentResponse>(
      `/api/approvals/${encodeURIComponent(id)}/resume`,
      {},
    ),
  // BUG-24 — parked turns this account may continue right now, whoever resolved
  // the approval and wherever they resolved it. Ids only; polling changes
  // nothing, and the server still enforces exactly-once resumption.
  resumableTurns: (sessionId?: string) =>
    request<ResumableTurnsView>(
      withQuery("/api/approvals/resumable", { session_id: sessionId }),
    ),
  resolveCriticalApproval: (
    id: string,
    body: { approve: boolean; reason: string },
  ) =>
    postJson<ResolveCriticalApprovalResult>(
      `/api/approvals/${encodeURIComponent(id)}/resolve-critical`,
      body,
    ),

  // ── Runtime mutations. These reuse the existing governed control routes; the UI adds no
  // authority. Every call is enforced server-side by RuntimeAuthority. ──
  activateRuntimeMode: (mode_name: string, reason: string) =>
    postJson<{ ok: boolean }>("/api/runtime-mode/activate", {
      mode_name,
      reason,
    }),
  disableRuntimeMode: (reason: string) =>
    postJson<{ ok: boolean }>("/api/runtime-mode/disable", { reason }),
  setCapabilityState: (
    capability: string,
    body: { target_state: string; reason: string; confirmation_token?: string },
  ) =>
    postJson<{ ok: boolean; capability: string; target_state: string }>(
      `/api/capability-gates/${encodeURIComponent(capability)}/set`,
      body,
    ),
  disableCapability: (capability: string, reason: string) =>
    postJson<{ ok: boolean; capability: string }>(
      `/api/capability-gates/${encodeURIComponent(capability)}/disable`,
      { reason },
    ),
  // Record a human threat-model acknowledgement (owner/gate-manager only). This
  // is the in-app equivalent of the operator/CLI ack step and only satisfies the
  // acknowledgement precondition — the capability transition still runs after it.
  recordThreatModelAck: (capability: string, reason: string) =>
    postJson<{ ok: boolean; capability: string; acknowledged: boolean }>(
      `/api/capability-gates/${encodeURIComponent(capability)}/threat-ack`,
      { reason },
    ),

  // ── Per-capability decision modes (ask | allow | auto | deny) ──
  capabilityDecisionMode: (capability: string) =>
    request<CapabilityDecisionMode>(
      `/api/capability-modes/${encodeURIComponent(capability)}`,
    ),
  setCapabilityDecisionMode: (
    capability: string,
    mode: "ask" | "allow" | "auto" | "deny",
    reason: string,
  ) =>
    postJson<{ ok: boolean; capability: string; decision_mode: string }>(
      `/api/capability-modes/${encodeURIComponent(capability)}/${mode}`,
      { reason },
    ),
};

/**
 * Stream a governed turn over SSE (POST /api/prompts/stream). The turn is created by the
 * stream from the prompt body, so this is a POST that reads the response body incrementally
 * rather than an EventSource (which can't send the bearer token or a request body).
 *
 * `onEvent` is invoked for each parsed `StreamEvent`; the promise resolves once the stream
 * closes (the final event carries the complete AgentResponse). Tool execution still flows
 * through the governed broker/policy/approval path — this only observes the turn.
 */
export async function streamPrompt(
  body: PromptRequestBody,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  return streamSse(
    "/api/prompts/stream",
    JSON.stringify(body),
    onEvent,
    signal,
  );
}

/**
 * Stream the continuation of a turn that was parked for an approval (B2).
 *
 * Resolving an approval closes the tool call the model was waiting on, so the
 * *same* turn can pick up from where it stopped instead of the owner re-prompting
 * and the model losing its working state. Same governed path as an ordinary
 * turn — this only surfaces the continuation as it happens.
 */
export async function streamResumeAfterApproval(
  approvalId: string,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  return streamSse(
    `/api/approvals/${encodeURIComponent(approvalId)}/resume/stream`,
    null,
    onEvent,
    signal,
  );
}

async function streamSse(
  path: string,
  body: string | null,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const headers = new Headers({ "Content-Type": "application/json" });
  if (token !== null) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  // Streaming routes go through `instancePath` like every other call, so a
  // dashboard served under /instances/<name> streams from its own instance
  // rather than the default workspace.
  const url = instancePath(path);
  const resp = await fetch(url, {
    method: "POST",
    headers,
    ...(body === null ? {} : { body }),
    signal,
  });
  if (!resp.ok || resp.body === null) {
    throw new ApiError(
      resp.status,
      null,
      `Stream failed: ${resp.status} ${url}`,
    );
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      buffer = drainSseBuffer(buffer, onEvent);
    }
  } finally {
    reader.releaseLock();
  }
  // Flush any trailing event that wasn't terminated by a blank line.
  drainSseBuffer(buffer + "\n\n", onEvent);
}

/** Parse complete `data:` SSE records out of `buffer`, returning the unconsumed remainder. */
function drainSseBuffer(
  buffer: string,
  onEvent: (event: StreamEvent) => void,
): string {
  let rest = buffer;
  let sep = rest.indexOf("\n\n");
  while (sep !== -1) {
    const chunk = rest.slice(0, sep);
    rest = rest.slice(sep + 2);
    const event = parseSseChunk(chunk);
    if (event !== null) onEvent(event);
    sep = rest.indexOf("\n\n");
  }
  return rest;
}

function parseSseChunk(chunk: string): StreamEvent | null {
  const data = chunk
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n");
  if (data === "") return null;
  try {
    return JSON.parse(data) as StreamEvent;
  } catch {
    return null;
  }
}
