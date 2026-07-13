import type {
  AgentResponse,
  ApprovalDetailView,
  ApprovalView,
  AuthSession,
  CapabilityDecisionMode,
  CapabilityGate,
  Checkpoint,
  ConnectionsView,
  ConnectorStoreView,
  Diagnostics,
  EventEntry,
  InterruptRequestBody,
  InterruptResult,
  ModelsView,
  ProjectDetail,
  ProjectsList,
  PromptRequestBody,
  ProviderModelList,
  ResolveApprovalResult,
  RuntimeMode,
  RuntimeReadiness,
  SessionDetail,
  SessionSummary,
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
  const resp = await fetch(path, { ...init, headers });
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
  checkpoints: (sessionId?: string, projectId?: string) =>
    request<Checkpoint[]>(
      withQuery("/api/checkpoints", { session_id: sessionId, project_id: projectId }),
    ),
  checkpoint: (id: string) => request<Checkpoint>(`/api/checkpoints/${encodeURIComponent(id)}`),
  sessions: (projectId?: string) =>
    request<SessionSummary[]>(withQuery("/api/sessions", { project_id: projectId })),

  // ── Projects (organizing scopes; creating/selecting one grants nothing) ──
  projects: () => request<ProjectsList>("/api/projects"),
  project: (id: string) => request<ProjectDetail>(`/api/projects/${encodeURIComponent(id)}`),
  // Create a named project (human gate-manager only, enforced server-side).
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
  session: (id: string) => request<SessionDetail>(`/api/sessions/${encodeURIComponent(id)}`),
  turn: (id: string) => request<TurnDetail>(`/api/turns/${encodeURIComponent(id)}`),
  tasks: (params: { session_id?: string; status?: string } = {}) =>
    request<TaskView[]>(withQuery("/api/tasks", params)),
  createTask: (body: {
    title: string;
    description: string;
    priority?: string;
    scheduled_at?: string;
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
