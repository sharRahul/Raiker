import type {
  AgentResponse,
  ApprovalDetailView,
  ApprovalView,
  AuthSession,
  BrainView,
  BrainSourceResult,
  CapabilityDecisionMode,
  CapabilityGate,
  Checkpoint,
  CredentialLifecycle,
  ConnectionsView,
  ConnectorStoreView,
  Diagnostics,
  EventEntry,
  InterruptRequestBody,
  InstanceLaunchResult,
  InterruptResult,
  McpServer,
  McpSession,
  McpFinding,
  Notification,
  MemoryControlView,
  MemorySettingsView,
  ModelsView,
  PasswordRecoveryBeginResult,
  ProjectDetail,
  ProjectTreeNode,
  ProjectsList,
  PromptRequestBody,
  ProviderModelList,
  ResolveApprovalResult,
  RuntimeMode,
  RuntimeReadiness,
  SecurityHealth,
  SessionDetail,
  SessionSummary,
  StandingGrant,
  StreamEvent,
  TaskView,
  TurnDetail,
  UploadedAttachment,
} from "./apiTypes";

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
      reasonCode = null;
    }
    throw new ApiError(resp.status, reasonCode, `Request failed: ${resp.status} ${path}`);
  }
  return (await resp.json()) as T;
}

async function requestBlob(path: string, init: RequestInit = {}): Promise<Blob> {
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
      reasonCode = null;
    }
    throw new ApiError(resp.status, reasonCode, `Request failed: ${resp.status} ${path}`);
  }
  return resp.blob();
}

function instancePath(path: string): string {
  if (typeof window === "undefined") return path;
  const match = window.location.pathname.match(/^(\/instances\/[^/]+)/);
  return match ? `${match[1]}${path}` : path;
}

function withQuery(path: string, params: Record<string, string | number | undefined>): string {
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
  const session = await postJson<AuthSession>("/api/auth/session", { as_principal: null });
  setToken(session.token);
  return session;
}

// ── Lock screen: local-account auth ─────────────────────────────────────────

/**
 * Privacy-safe pre-auth reachability probe. `/api/health` is the only
 * unauthenticated read and returns nothing beyond `{status: "ok"}` — it backs
 * the lock screen's "I cannot reach my runtime." state without leaking any
 * workspace detail before authentication.
 */
export function health(): Promise<{ status: string }> {
  return request<{ status: string }>("/api/health");
}

export function createInstance(name: string, username: string, password: string): Promise<InstanceLaunchResult> {
  return postJson<InstanceLaunchResult>("/api/instances", { name, username, password });
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
    postJson<LoginResult>("/api/auth/register", { username, password }).then(adoptSession),
  login: (username: string, password: string) =>
    postJson<LoginResult>("/api/auth/login", { username, password }).then(adoptSession),
  verifyMfa: (ticket: string, code: string) =>
    postJson<LoginResult>("/api/auth/mfa/verify", { ticket, code }).then(adoptSession),
  bootstrapStatus: () => request<{ can_register: boolean }>("/api/auth/bootstrap-status"),
  beginPasswordRecovery: (username: string) =>
    postJson<PasswordRecoveryBeginResult>("/api/auth/password-recovery/begin", { username }),
  completePasswordRecovery: (ticket: string, code: string, newPassword: string) =>
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
    postJson<{ token: string }>("/api/auth/elevate", { password, mfa_code: mfaCode }),
  enrollMfa: () =>
    postJson<{ secret: string; provisioning_uri: string; backup_codes: string[] }>(
      "/api/auth/mfa/enroll",
      {},
    ),
  activateMfa: (code: string) => postJson<{ ok: boolean }>("/api/auth/mfa/activate", { code }),
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
    postJson<{ ok: boolean }>(`/api/auth/sessions/${encodeURIComponent(sessionId)}/revoke`, {}),
  deleteAccount: () => request<{ ok: boolean }>("/api/account", { method: "DELETE" }),
};

export interface SettingsView {
  settings: Record<string, unknown>;
  status: { vault: string; mfa_enrolled: boolean; username: string };
}

export const api = {
  // ── Local-account settings, vault key, MFA status ──
  settings: () => request<SettingsView>("/api/settings"),
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
  capabilityGates: () => request<CapabilityGate[]>("/api/capability-gates"),
  capabilityGate: (capability: string) =>
    request<CapabilityGate>(`/api/capability-gates/${encodeURIComponent(capability)}`),
  runtimeMode: () => request<RuntimeMode>("/api/runtime-mode"),
  runtimeReadiness: () => request<RuntimeReadiness>("/api/runtime-readiness"),
  diagnostics: () => request<Diagnostics>("/api/diagnostics"),
  models: () => request<ModelsView>("/api/models"),
  // Read-only status of governed service connectors (never reaches the network;
  // never exposes a credential value). Enabling one is done via the capability
  // gate + decision-mode control plane, not here.
  connections: () => request<ConnectionsView>("/api/connections"),
  // ── Local MCP servers (Control Deck task 4b) ────────────────────────────
  // Owner-scoped. Create and test-connect run through the governed capability
  // (a disabled gate returns 403 disabled_by_capability_gate); rename and
  // delete are human-only owner-scoped operations.
  mcpServers: () => request<McpServer[]>("/api/mcp/servers"),
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
    request<{ ok: boolean; name: string }>(`/api/mcp/servers/${encodeURIComponent(serverId)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }),
  deleteMcpServer: (serverId: string) =>
    request<{ ok: boolean; server_id: string }>(
      `/api/mcp/servers/${encodeURIComponent(serverId)}`,
      { method: "DELETE" },
    ),
  createRemoteMcpServer: (name: string, endpoint_url: string, auth_ref: string | null) =>
    postJson<{ ok: boolean; server_id: string | null; name: string | null }>(
      "/api/mcp/servers/remote",
      { name, endpoint_url, auth_ref },
    ),
  mcpSessions: (serverId: string) =>
    request<McpSession[]>(`/api/mcp/servers/${encodeURIComponent(serverId)}/sessions`),
  mcpFindings: (serverId: string) =>
    request<McpFinding[]>(`/api/mcp/servers/${encodeURIComponent(serverId)}/findings`),
  pauseMcpServer: (serverId: string) =>
    postJson<{ ok: boolean; monitor_state: string }>(`/api/mcp/servers/${encodeURIComponent(serverId)}/pause`, {}),
  resumeMcpServer: (serverId: string) =>
    postJson<{ ok: boolean; monitor_state: string }>(`/api/mcp/servers/${encodeURIComponent(serverId)}/resume`, {}),
  notifications: () => request<Notification[]>("/api/notifications"),
  markNotificationRead: (id: string) =>
    postJson<{ ok: boolean }>(`/api/notifications/${encodeURIComponent(id)}/read`, {}),
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
  }) => postJson<{ ok: boolean; grant: StandingGrant }>("/api/standing-grants", body),
  revokeStandingGrant: (grantId: string) =>
    postJson<{ ok: boolean; grant_id: string }>(
      `/api/standing-grants/${encodeURIComponent(grantId)}/revoke`,
      {},
    ),
  securityCredentials: () => request<CredentialLifecycle[]>("/api/security/credentials"),
  securityFindings: () => request<McpFinding[]>("/api/security/findings"),
  securityHealth: () => request<SecurityHealth[]>("/api/security/health"),
  verifySecurityCredential: (provider: string) =>
    postJson<CredentialLifecycle>(`/api/security/credentials/${encodeURIComponent(provider)}/verify`, {}),
  scanSecurity: () => postJson<McpFinding[]>("/api/security/scan", {}),
  checkSecurityHealth: () => postJson<SecurityHealth[]>("/api/security/health-check", {}),
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
  registerConnectorManifest: (connectorId: string, manifest: Record<string, unknown>) =>
    postJson<{ ok: boolean; operations: unknown[] }>(
      `/api/connector-store/${encodeURIComponent(connectorId)}/manifest`,
      { manifest },
    ),
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
    request<{ ok: boolean; advisor_profile_id: string | null }>("/api/model-advisor", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_id }),
    }),
  // Persist the operator's model selection (human gate-manager only, enforced
  // server-side; placeholder profiles require a concrete model).
  selectModel: (profile_id: string, model?: string) =>
    request<{ ok: boolean; profile_id: string; model: string }>("/api/model-selection", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_id, model: model || null }),
    }),
  saveModelConnection: (profileId: string, endpoint: string, apiKey: string) =>
    request<{ ok: boolean; connection_configured: boolean }>(
      `/api/models/${encodeURIComponent(profileId)}/connection`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ endpoint: endpoint || null, api_key: apiKey || null }),
      },
    ),
  // Persist the user-owned ordered model fallback sequence (human gate-manager only,
  // enforced server-side). Returns the cleaned/de-duplicated sequence.
  setModelFallback: (profile_ids: string[]) =>
    request<{ ok: boolean; fallback_sequence: string[] }>("/api/model-fallback", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_ids }),
    }),
  // Upload one image (base64) into the governed attachment store. Validation
  // is fail-closed server-side (media-type allowlist, 5 MB cap, magic-byte
  // sniff); the response is metadata only.
  uploadAttachment: (body: { filename: string; media_type: string; data_base64: string }) =>
    postJson<UploadedAttachment>("/api/attachments", body),
  events: (params: { session_id?: string; turn_id?: string; event_type?: string; limit?: number } = {}) =>
    request<EventEntry[]>(withQuery("/api/events", params)),
  brain: () => request<BrainView>("/api/brain"),
  addBrainSource: (path: string) => postJson<BrainSourceResult>("/api/brain/sources", { path }),
  removeBrainSource: (path: string) =>
    request<BrainSourceResult>(withQuery("/api/brain/sources", { path }), { method: "DELETE" }),
  checkpoints: (sessionId?: string, projectId?: string) =>
    request<Checkpoint[]>(
      withQuery("/api/checkpoints", { session_id: sessionId, project_id: projectId }),
    ),
  checkpoint: (id: string) => request<Checkpoint>(`/api/checkpoints/${encodeURIComponent(id)}`),
  sessions: (projectId?: string, includeArchived = false) =>
    request<SessionSummary[]>(
      withQuery("/api/sessions", {
        project_id: projectId,
        include_archived: includeArchived ? "true" : undefined,
      }),
    ),
  searchChats: (q: string) => request<SessionSummary[]>(withQuery("/api/chat-search", { q })),

  // ── Reliable memory controls (backlog item 3) ────────────────────────
  // User-facing surface over the existing governed memory store. List carries
  // provenance/scope/sensitivity/confidence/retention + pin; forget reuses
  // the governed forget path (human-only); incognito withholds approved
  // project memory from the turn context.
  memories: (scope?: string) =>
    request<MemoryControlView[]>(withQuery("/api/memory", { scope })),
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
    request<{ ok: boolean; memory_id: string }>(`/api/memory/${encodeURIComponent(id)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    }),
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
    request<{ ok: boolean; memories: MemoryControlView[] }>("/api/memory/export"),
  importMemories: (memories: Array<Partial<MemoryControlView> & { text: string }>) =>
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

  // ── Projects (organizing scopes; creating/selecting one grants nothing) ──
  projects: () => request<ProjectsList>("/api/projects"),
  project: (id: string) => request<ProjectDetail>(`/api/projects/${encodeURIComponent(id)}`),
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
    postJson<{ ok: boolean; project_id: string; name: string; root_subpath: string }>(
      "/api/projects",
      { name },
    ),
  // Set (or clear, with null) the active project; new sessions are stamped with it.
  selectProject: (project_id: string | null) =>
    request<{ ok: boolean; active_project_id: string | null }>("/api/projects/selection", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id }),
    }),
  deleteProject: (id: string, confirmed = false) =>
    request<{ ok: boolean }>(`/api/projects/${encodeURIComponent(id)}`, {
      method: "DELETE",
      headers: confirmed ? { "X-Project-Delete-Confirm": id } : undefined,
    }),
  saveProjectContext: (id: string, context: { instructions: string; attachment_ids: string[]; memory_enabled: boolean; memory_mode: "inherit" | "enabled" | "disabled" }) =>
    request<{ ok: boolean }>(`/api/projects/${encodeURIComponent(id)}/context`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(context),
    }),
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
  session: (id: string) => request<SessionDetail>(`/api/sessions/${encodeURIComponent(id)}`),
  renameSession: (id: string, title: string) =>
    request<{ ok: boolean; session_id: string; title: string }>(
      `/api/sessions/${encodeURIComponent(id)}/rename`,
      { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title }) },
    ),
  archiveSession: (id: string) =>
    request<{ ok: boolean; session_id: string; archived: boolean }>(
      `/api/sessions/${encodeURIComponent(id)}/archive`, { method: "PUT" },
    ),
  unarchiveSession: (id: string) =>
    request<{ ok: boolean; session_id: string; archived: boolean }>(
      `/api/sessions/${encodeURIComponent(id)}/unarchive`, { method: "PUT" },
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
  turn: (id: string) => request<TurnDetail>(`/api/turns/${encodeURIComponent(id)}`),
  // `project_id` scopes the list to one project's schedules (project-scoped
  // schedules); omitting it lists every task visible to the account.
  tasks: (params: { session_id?: string; status?: string; project_id?: string } = {}) =>
    request<TaskView[]>(withQuery("/api/tasks", params)),
  createTask: (body: {
    title: string;
    description: string;
    priority?: string;
    scheduled_at?: string;
    recurrence?: string;
    parent_task_id?: string;
    // Create the task under a specific project. Omitted → the active project.
    project_id?: string | null;
  }) => postJson<TaskView>("/api/tasks", body),

  // ── Prompts / interrupts ──
  // Non-streaming prompt submit; returns the final governed AgentResponse.
  submitPrompt: (body: PromptRequestBody) => postJson<AgentResponse>("/api/prompts", body),
  // Issue a governed safe-boundary interrupt for one task or all active tasks in a session.
  interrupt: (body: InterruptRequestBody) => postJson<InterruptResult>("/api/interrupts", body),

  // ── Approvals (resolution is metadata-only: records a decision, never executes) ──
  approvals: (statusFilter = "pending") =>
    request<ApprovalView[]>(withQuery("/api/approvals", { status_filter: statusFilter })),
  approval: (id: string) => request<ApprovalDetailView>(`/api/approvals/${encodeURIComponent(id)}`),
  resolveApproval: (id: string, body: { approve: boolean; reason: string }) =>
    postJson<ResolveApprovalResult>(`/api/approvals/${encodeURIComponent(id)}/resolve`, body),

  // ── Runtime mutations. These reuse the existing governed control routes; the UI adds no
  // authority. Every call is enforced server-side by RuntimeAuthority. ──
  activateRuntimeMode: (mode_name: string, reason: string) =>
    postJson<{ ok: boolean }>("/api/runtime-mode/activate", { mode_name, reason }),
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
    request<CapabilityDecisionMode>(`/api/capability-modes/${encodeURIComponent(capability)}`),
  setCapabilityDecisionMode: (capability: string, mode: "ask" | "allow" | "auto" | "deny", reason: string) =>
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
  const headers = new Headers({ "Content-Type": "application/json" });
  if (token !== null) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const resp = await fetch("/api/prompts/stream", {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal,
  });
  if (!resp.ok || resp.body === null) {
    throw new ApiError(resp.status, null, `Stream failed: ${resp.status} /api/prompts/stream`);
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
function drainSseBuffer(buffer: string, onEvent: (event: StreamEvent) => void): string {
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
