// Shared fetch stub for component tests. Routes are matched by "METHOD path"
// prefix (query strings ignored), so tests declare only the endpoints they use;
// anything unrouted rejects loudly instead of fabricating data.
import { vi } from "vitest";
import type {
  CapabilityGate,
  ContentPart,
  Diagnostics,
  ModelProfile,
  ModelsView,
  RuntimeMode,
  TaskView,
} from "./apiTypes";

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
  search_indexes: [],
  scheduler_queue: { due: 0, oldest_due_at: null, oldest_wait_seconds: null, host_paused: false },
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
    requires_threat_model_ack: false,
    requires_human_confirmation: false,
    threat_model_ack_recorded: false,
    gate_reality: "own_gate",
    governance_note: "",
    unset_resolution: "off",
    enforced_enabled: false,
    side_effect: "",
    ungoverned_consequence: "",
    authority_requirement: "",
    network_boundary: "",
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
 * Attach, dictation and the project select are reached through the composer's
 * menus. These helpers are that step, in one place, so a spec says *what* it
 * is exercising rather than where today's design happens to keep it.
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

/** A declared answer part with the keys the server always sends filled in. */
export function part(over: Partial<ContentPart> & Pick<ContentPart, "type">): ContentPart {
  return { text: "", data: {}, reason_code: "", ...over };
}

/** A task row as the server sends it, with the fields a test does not care about defaulted. */
export function taskView(over: Partial<TaskView> = {}): TaskView {
  return {
    task_id: "task_1",
    session_id: "sess_inbox_owner",
    status: "queued",
    title: "Task",
    objective: "",
    current_step: null,
    progress_percent: null,
    created_at: "2026-09-15T08:00:00Z",
    updated_at: "2026-09-15T08:00:00Z",
    completed_at: null,
    summary: null,
    priority: null,
    scheduled_at: null,
    recurrence: null,
    reminder_at: null,
    parent_task_id: null,
    project_id: null,
    model_profile: null,
    model: null,
    surface: "chat",
    thread_session_id: null,
    thread_turns: 0,
    attachments: [],
    schedule_timezone: null,
    schedule_until: null,
    missed_run_policy: null,
    delivery_state: null,
    delivery_detail: null,
    max_run_minutes: 60,
    max_tool_calls: null,
    // Empty, so `taskPhase` derives the phase from the status a test sets
    // rather than reading a default that disagrees with it.
    phase: "",
    ...over,
  };
}

/** A model profile as the server sends it: nothing configured, checked or used yet. */
export function modelProfile(over: Partial<ModelProfile> = {}): ModelProfile {
  return {
    profile_id: "local-gguf",
    provider: "llama.cpp",
    model: "local-gguf",
    default_state: "enabled",
    local_only: true,
    requires_network: false,
    endpoint_kind: "local_process",
    requires_egress_policy: false,
    requires_budget_policy: false,
    runtime_gate: null,
    off_machine: false,
    selected: false,
    connection_configured: false,
    usage_admin_configured: false,
    workspace_configured: false,
    prompt_cache_ttl: null,
    context_window_tokens: null,
    context_window_source: null,
    configured: false,
    provider_detected: null,
    provider_running: null,
    readiness_state: "not_configured",
    readiness_summary: "No readiness check exists for this exact model.",
    readiness_reason_code: "model_not_checked",
    readiness_checked_at: null,
    readiness_expires_at: null,
    readiness_remediation: "Set up or check this model before sending.",
    ready: false,
    billable: false,
    models_used: 0,
    turns_used: 0,
    total_tokens: 0,
    total_cost: null,
    cost_currency: null,
    price_source: null,
    price_as_of: null,
    supports_reasoning: false,
    supports_reasoning_effort: false,
    reasoning_effort_values: [],
    reasoning_modes: [],
    supports_reasoning_summary: false,
    image_models: [],
    supports_tool_calls: null,
    supports_vision: null,
    rate_input_per_mtok: null,
    rate_output_per_mtok: null,
    rate_currency: null,
    ...over,
  };
}

/**
 * The Models snapshot. `chat_profiles` defaults to the configured profiles, the
 * subset the server sends, so a test that names only `profiles` sees the same
 * pickers a real snapshot would give it.
 */
export function modelsView(over: Partial<ModelsView> = {}): ModelsView {
  const profiles = over.profiles ?? [];
  return {
    profiles,
    chat_profiles: profiles.filter((profile) => profile.configured),
    current_profile_id: null,
    hosted_model_gate_state: "disabled",
    private_network_model_gate_state: "disabled",
    hosted_model_gate_enforced: true,
    private_network_model_gate_enforced: true,
    model_egress_allowlist_configured: false,
    remote_profile_count: 0,
    ready_provider_count: 0,
    usable_provider_count: 0,
    fallback_sequence: [],
    no_silent_hosted_fallback: true,
    current_model: null,
    advisor_profile_id: null,
    advisor_model_gate_state: "disabled",
    advisor_model: null,
    advisor_readiness_state: "not_configured",
    advisor_readiness_summary: null,
    advisor_readiness_remediation: null,
    advisor_readiness_checked_at: null,
    catalogues: {},
    ...over,
  };
}
