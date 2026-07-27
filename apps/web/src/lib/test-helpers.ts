// Shared fetch stub for component tests. Routes are matched by "METHOD path"
// prefix (query strings ignored), so tests declare only the endpoints they use;
// anything unrouted rejects loudly instead of fabricating data.
import { vi } from "vitest";
import type { CapabilityGate, Diagnostics, RuntimeMode } from "./apiTypes";

/** A fetch that never settles — for asserting route-level loading states. */
export function stubFetchPending(): ReturnType<typeof vi.fn> {
  const mock = vi.fn(() => new Promise<never>(() => {}));
  vi.stubGlobal("fetch", mock);
  return mock;
}

export function stubFetch(routes: Record<string, unknown>): ReturnType<typeof vi.fn> {
  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const path = url.split("?")[0];
    const method = (init?.method ?? "GET").toUpperCase();
    const key = `${method} ${path}`;
    if (key in routes) {
      const value = routes[key];
      return {
        ok: true,
        status: 200,
        json: async () => value,
        // Binary routes (the PDF preview) are read with `.blob()`. A route may
        // declare a Blob directly; anything else is serialised so the stub
        // still answers rather than throwing "blob is not a function".
        blob: async () => (value instanceof Blob ? value : new Blob([JSON.stringify(value)])),
      } as Response;
    }
    return {
      ok: false,
      status: 404,
      json: async () => ({ detail: { reason_code: `unrouted:${key}` } }),
    } as Response;
  });
  vi.stubGlobal("fetch", mock);
  return mock;
}

export const AUTH_SESSION = {
  token: "test-token",
  session_id: "apisess_1",
  principal_id: "prin_owner",
  expires_at: null,
};

export const RUNTIME_MODE: RuntimeMode = {
  mode_name: "local_single_user_runtime",
  status: "active",
  activated_by: "prin_owner",
  activated_at: "2026-07-07T00:00:00Z",
  reason: "test",
  allowed_modes: ["local_single_user_runtime"],
};

export const DIAGNOSTICS: Diagnostics = {
  runtime_mode: "local_single_user_runtime",
  production_ready_local_single_user_runtime: true,
  summary: {},
  disabled_capabilities: ["finance_runtime"],
  counts: { sessions: 1, events: 2, checkpoints: 0, tasks: 0 },
  readiness: {},
  missing_config: [],
  provider_health: [],
  scope_note: "Status reflects the local single-user runtime only.",
};

export function makeGate(partial: Partial<CapabilityGate>): CapabilityGate {
  return {
    capability: "x",
    phase: 3,
    state: "disabled",
    default_state: "disabled",
    source: "static_default",
    runtime_enabled: false,
    allowed_transitions: [],
    can_current_principal_change: false,
    blocked_reason_code: null,
    readiness: {},
    decision_mode: "ask",
    ...partial,
  };
}

export const LOGIN_RESULT = {
  stage: "session",
  principal_id: "prin_owner",
  token: "test-token",
  ticket: null,
};

export const BOOTSTRAP_ROUTES: Record<string, unknown> = {
  "GET /api/health": { status: "ok" },
  "POST /api/auth/session": AUTH_SESSION,
  "POST /api/auth/login": LOGIN_RESULT,
  "POST /api/auth/register": LOGIN_RESULT,
  "GET /api/runtime-mode": RUNTIME_MODE,
  "GET /api/diagnostics": DIAGNOSTICS,
  "GET /api/projects": { projects: [], active_project_id: null },
  "GET /api/models": {
    profiles: [],
    current_profile_id: null,
    current_model: null,
    advisor_profile_id: null,
    advisor_model_gate_state: "enabled_runtime",
    hosted_model_gate_state: "enabled_runtime",
    private_network_model_gate_state: "enabled_runtime",
    model_egress_allowlist_configured: false,
    remote_profile_count: 0,
    fallback_sequence: [],
    no_silent_hosted_fallback: true,
  },
};
