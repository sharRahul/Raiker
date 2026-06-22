import type {
  AgentResponse,
  ApprovalDetailView,
  ApprovalView,
  AuthSession,
  CapabilityGate,
  Checkpoint,
  Diagnostics,
  EventEntry,
  InterruptRequestBody,
  InterruptResult,
  ModelsView,
  PromptRequestBody,
  ResolveApprovalResult,
  RuntimeMode,
  RuntimeReadiness,
  SessionSummary,
  StreamEvent,
  TaskView,
} from "./apiTypes";

// Bearer token held in memory only — never localStorage/sessionStorage (security requirement).
let token: string | null = null;

export function setToken(value: string | null): void {
  token = value;
}

export function hasToken(): boolean {
  return token !== null;
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

/** Mint a bearer token for the local owner principal and hold it in memory. */
export async function connect(): Promise<AuthSession> {
  const session = await request<AuthSession>("/api/auth/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ as_principal: null }),
  });
  setToken(session.token);
  return session;
}

export const api = {
  capabilityGates: () => request<CapabilityGate[]>("/api/capability-gates"),
  runtimeMode: () => request<RuntimeMode>("/api/runtime-mode"),
  runtimeReadiness: () => request<RuntimeReadiness>("/api/runtime-readiness"),
  diagnostics: () => request<Diagnostics>("/api/diagnostics"),
  models: () => request<ModelsView>("/api/models"),
  events: (params: { session_id?: string; turn_id?: string; event_type?: string; limit?: number } = {}) => {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== "") q.set(k, String(v));
    }
    const suffix = q.toString() ? `?${q.toString()}` : "";
    return request<EventEntry[]>(`/api/events${suffix}`);
  },
  checkpoints: (sessionId?: string) =>
    request<Checkpoint[]>(`/api/checkpoints${sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ""}`),
  sessions: () => request<SessionSummary[]>("/api/sessions"),
  tasks: (params: { session_id?: string; status?: string } = {}) => {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== "") q.set(k, String(v));
    }
    const suffix = q.toString() ? `?${q.toString()}` : "";
    return request<TaskView[]>(`/api/tasks${suffix}`);
  },
  // Non-streaming prompt submit; returns the final governed AgentResponse.
  submitPrompt: (body: PromptRequestBody) =>
    request<AgentResponse>("/api/prompts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  // Issue a governed safe-boundary interrupt for one task or all active tasks in a session.
  interrupt: (body: InterruptRequestBody) =>
    request<InterruptResult>("/api/interrupts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  approvals: () => request<ApprovalView[]>("/api/approvals"),
  approval: (id: string) => request<ApprovalDetailView>(`/api/approvals/${encodeURIComponent(id)}`),
  // Resolution is metadata-only — it records a decision and never executes the action.
  resolveApproval: (id: string, body: { approve: boolean; reason: string }) =>
    request<ResolveApprovalResult>(`/api/approvals/${encodeURIComponent(id)}/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
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
