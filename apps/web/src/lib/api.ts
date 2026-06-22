import type {
  AuthSession,
  CapabilityGate,
  Checkpoint,
  Diagnostics,
  EventEntry,
  ModelsView,
  RuntimeMode,
  RuntimeReadiness,
  SessionSummary,
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
};
