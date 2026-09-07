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
    // A route may be declared with its query string, so two calls to the same
    // path can answer differently — browsing folder A and folder B, say. The
    // exact key wins; the path-only key stays the default, so every existing
    // route keeps matching whatever query it is called with.
    const exactKey = `${method} ${url}`;
    const key = exactKey in routes ? exactKey : `${method} ${path}`;
    if (key in routes) {
      const value = routes[key];
      // A route may declare a non-2xx answer as `{ __status: 409 }` so a test
      // can exercise the branch a real refusal takes, not only the happy path.
      const declared =
        value !== null && typeof value === "object" && "__status" in value
          ? Number((value as { __status: unknown }).__status)
          : 200;
      if (declared >= 400) {
        return {
          ok: false,
          status: declared,
          json: async () => value,
        } as Response;
      }
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
  mode_name: "raiker_runtime",
  status: "active",
  activated_by: "prin_owner",
  activated_at: "2026-07-07T00:00:00Z",
  reason: "test",
  allowed_modes: ["raiker_runtime"],
};

export const DIAGNOSTICS: Diagnostics = {
  runtime_mode: "raiker_runtime",
  production_ready_local_single_user_runtime: true,
  summary: {},
  disabled_capabilities: ["finance_runtime"],
  counts: { sessions: 1, events: 2, checkpoints: 0, tasks: 0 },
  readiness: {},
  missing_config: [],
  provider_health: [],
  background_workers: [],
  model_profile_source: { kind: "packaged", location: "raiker.config/model-profiles.json" },
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
  "GET /api/model-setup": { owner_principal_id: "prin_owner", status: "complete", step: "ready", path: null, selected_profile_id: null, selected_model: null, created_at: null, updated_at: null },
  "GET /api/setup": { owner_principal_id: "prin_owner", status: "complete", stage: "finish", selected_profile_id: null, selected_model: null, model_deferred: true, privacy_mode: "local_first", privacy_acknowledged_at: null, backup_mode: "later", backup_target: null, backup_verified_at: null, background_service_enabled: false, created_at: null, updated_at: null },
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

/**
 * COMPOSER-02 — driving a composer whose controls are behind its two menus.
 *
 * The bar used to carry an attach control, a dictation trigger and a project
 * select as permanent buttons, and every spec that exercised one reached for it
 * by name. They are all still there and all still do the same thing; what
 * changed is that reaching them is two steps rather than one. These helpers are
 * that second step, in one place, so a spec still says *what* it is exercising
 * rather than where today's design happens to keep it.
 *
 * Imported lazily inside each helper because `@testing-library/svelte` pulls in
 * a DOM, and this module is also imported by tests that run without one.
 */
async function composerMenuItem(trigger: string, item: string): Promise<void> {
  const { fireEvent, screen, within } = await import("@testing-library/svelte");
  await fireEvent.click(await screen.findByRole("button", { name: trigger }));
  const menu = await screen.findByRole("menu", { name: trigger });
  await fireEvent.click(within(menu).getByRole("menuitem", { name: item }));
}

/** Open the attachment panel, the way `+` does. */
export async function openComposerAttach(): Promise<void> {
  await composerMenuItem("Add to this turn", "Upload a file");
}

/** Start dictating, the way `+` does. */
export async function startComposerDictation(): Promise<void> {
  await composerMenuItem("Add to this turn", "Dictate");
}

/** Reveal the project chooser, the way `+` does. */
export async function openComposerProject(): Promise<void> {
  await composerMenuItem("Add to this turn", "Work in a project");
}

/** Choose an item from the composer's Tools menu. */
export async function chooseComposerTool(label: string): Promise<void> {
  await composerMenuItem("Tools", label);
}
