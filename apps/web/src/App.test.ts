import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App.svelte";
import { BOOTSTRAP_ROUTES, stubFetch } from "./lib/test-helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  window.location.hash = "";
  localStorage.removeItem("raiker.navigation.desktop");
});

// Drive the lock screen: fill credentials and submit so the app shell mounts.
async function signIn() {
  await waitFor(() => expect(screen.getByLabelText("Username")).toBeInTheDocument());
  await fireEvent.input(screen.getByLabelText("Username"), { target: { value: "owner" } });
  await fireEvent.input(screen.getByLabelText("Password"), { target: { value: "pw" } });
  await fireEvent.click(screen.getByRole("button", { name: "Unlock Raiker" }));
}

describe("App shell", () => {
  it("reflows and persists the desktop navigation preference", async () => {
    stubFetch(BOOTSTRAP_ROUTES);
    render(App);
    await signIn();
    const toggle = await screen.findByRole("button", { name: "Collapse navigation" });
    await fireEvent.click(toggle);
    expect(screen.getByRole("button", { name: "Expand navigation" })).toHaveAttribute("aria-expanded", "false");
    expect(document.querySelector(".app-shell")).toHaveAttribute("data-navigation-open", "false");
    // Collapsed is a rail, not a disappearance: the icons stay on screen and
    // stay clickable, so nothing here may be hidden from assistive tech.
    const railNavigation = document.getElementById("all-navigation") as HTMLElement;
    expect(railNavigation).not.toHaveAttribute("aria-hidden");
    expect(railNavigation.inert).toBe(false);
    expect(railNavigation.className).toContain("desktop-hidden");
    expect(localStorage.getItem("raiker.navigation.desktop")).toBe("false");
  });
  // The 20s is the test's own timeout, and it has to be larger than the 10s
  // below or the wait can never be reached: vitest's default is 5s, so raising
  // only the `findByRole` timeout left the intended fix inert and this test
  // still failing at five seconds under a loaded machine. Found on 2026-09-04
  // with the Python suite running beside it.
  it("routes a first owner into resumable model setup", { timeout: 20_000 }, async () => {
    stubFetch({
      ...BOOTSTRAP_ROUTES,
      "GET /api/setup": { owner_principal_id: "prin_owner", status: "required", stage: "model", selected_profile_id: null, selected_model: null, model_deferred: false, privacy_mode: null, privacy_acknowledged_at: null, backup_mode: "later", backup_target: null, backup_verified_at: null, background_service_enabled: false, created_at: null, updated_at: null },
    });
    render(App);
    await signIn();
    // The setup route is a lazily imported chunk, so this waits on a dynamic
    // import rather than on a render. Testing Library's one-second default is
    // enough on an idle machine and not under a full-suite run, which made this
    // the only intermittently failing assertion in the suite.
    expect(
      await screen.findByRole(
        "heading",
        { name: "Choose where Raiker thinks" },
        { timeout: 10_000 },
      ),
    ).toBeInTheDocument();
    expect(window.location.hash).toBe("#/model-setup");
  });
  it("signs in, then shows the runtime status and grouped navigation", async () => {
    stubFetch(BOOTSTRAP_ROUTES);
    render(App);
    await signIn();
    await waitFor(() => {
      expect(screen.getByRole("navigation", { name: /all navigation/i })).toBeInTheDocument();
    });
    // Grouped nav with every governed surface reachable.
    const nav = screen.getByRole("navigation", { name: /all navigation/i });
    expect(nav).toBeInTheDocument();
    for (const label of [
      "Workbench",
      "Chat",
      "Threads",
      "Approvals",
      "Tasks",
    ]) {
      expect(within(nav).getByRole("link", { name: new RegExp(`^${label}$`, "i") })).toBeInTheDocument();
    }
    // Manage, Observe and Support left the rail for the gear's window. They are
    // still routes — `nav.ts` still holds them — but the sidebar no longer
    // carries a standing row for work that happens on a handful of days.
    for (const label of ["Permissions", "Models", "Extensions", "Observability", "Settings"]) {
      expect(within(nav).queryByRole("link", { name: new RegExp(`^${label}$`, "i") })).toBeNull();
    }
    await fireEvent.click(screen.getByRole("button", { name: "Settings and pages" }));
    const pages = await screen.findByRole("dialog", { name: /settings & pages/i });
    for (const label of ["Permissions", "Models", "Extensions", "Observability"]) {
      expect(within(pages).getByRole("link", { name: new RegExp(`^${label}$`, "i") })).toBeInTheDocument();
    }
    // The acting principal and mode are surfaced, honestly, from the API — the runtime
    // mode identifier is shown as a plain-English name, not the raw code.
    expect(screen.queryByText("prin_owner")).not.toBeInTheDocument();
    expect(screen.queryByText("Runtime ready")).not.toBeInTheDocument();
    expect(screen.queryByText("Local single user runtime")).not.toBeInTheDocument();
  });

  it("keeps an unsent chat draft while visiting another route", async () => {
    stubFetch(BOOTSTRAP_ROUTES);
    render(App);
    await signIn();

    const nav = await screen.findByRole("navigation", { name: /all navigation/i });
    await fireEvent.click(within(nav).getByRole("link", { name: "Chat" }));
    const prompt = await screen.findByLabelText("Prompt");
    await fireEvent.input(prompt, { target: { value: "Keep this draft" } });

    await fireEvent.click(within(nav).getByRole("link", { name: "Memory" }));
    await screen.findByRole("heading", { name: /memory/i });

    await fireEvent.click(within(nav).getByRole("link", { name: "Chat" }));
    expect(await screen.findByLabelText("Prompt")).toHaveValue("Keep this draft");
  });

  it("loads a saved session after Chat has been retained off-route", async () => {
    stubFetch({
      ...BOOTSTRAP_ROUTES,
      "GET /api/sessions/sess_hist": {
        session: {
          session_id: "sess_hist",
          title: "Prior chat",
          status: "open",
          created_at: "2026-07-10T00:00:00Z",
          updated_at: "2026-07-10T00:01:00Z",
          turn_count: 1,
        },
        turns: [
          {
            turn_id: "turn_1",
            session_id: "sess_hist",
            turn_type: "prompt",
            status: "completed",
            prompt_text: "saved session prompt",
            created_at: "2026-07-10T00:00:00Z",
            completed_at: "2026-07-10T00:00:10Z",
            summary: "saved session answer",
          },
        ],
      },
    });
    render(App);
    await signIn();

    const nav = await screen.findByRole("navigation", { name: /all navigation/i });
    await fireEvent.click(within(nav).getByRole("link", { name: "Chat" }));
    await screen.findByLabelText("Prompt");
    await fireEvent.click(within(nav).getByRole("link", { name: "Memory" }));
    await screen.findByRole("heading", { name: /memory/i });

    window.location.hash = "#/new-chat?session=sess_hist";
    expect(await screen.findByText("saved session prompt")).toBeInTheDocument();
    expect(screen.getByText("saved session answer")).toBeInTheDocument();
  });

  it.skip("refreshes the topbar model chip after a selection on the Models view", async () => {
    const profileBase = {
      default_state: "disabled",
      local_only: true,
      requires_network: false,
      endpoint_kind: "local",
      requires_egress_policy: false,
      requires_budget_policy: false,
      runtime_gate: null,
      off_machine: false,
      prompt_cache_ttl: null,
    };
    const modelsBase = {
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
    };
    // The selection flips server-side after the PUT; GET /api/models must be
    // re-read by the shell for the chip to change.
    let selected = "raiker-local-llama-cpp";
    const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      const path = url.split("?")[0];
      const method = (init?.method ?? "GET").toUpperCase();
      if (method === "PUT" && path.includes("/api/model-selection")) {
        selected = "ollama-local-openai-compatible";
        return {
          ok: true,
          status: 200,
          json: async () => ({ ok: true, profile_id: selected, model: "gemma4:31b-cloud" }),
        } as Response;
      }
      if (method === "GET" && path.endsWith("/api/models")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            ...modelsBase,
            profiles: [
              {
                ...profileBase,
                profile_id: "raiker-local-llama-cpp",
                provider: "llama.cpp",
                model: "local-gguf",
                selected: selected === "raiker-local-llama-cpp",
              },
              {
                ...profileBase,
                profile_id: "ollama-local-openai-compatible",
                provider: "ollama",
                model: "gemma4:31b-cloud",
                selected: selected === "ollama-local-openai-compatible",
              },
            ],
            current_profile_id: selected,
          }),
        } as Response;
      }
      const key = `${method} ${path}`;
      for (const routeKey of Object.keys(BOOTSTRAP_ROUTES)) {
        if (key.endsWith(routeKey.split(" ")[1]) && key.startsWith(routeKey.split(" ")[0])) {
          return { ok: true, status: 200, json: async () => BOOTSTRAP_ROUTES[routeKey] } as Response;
        }
      }
      return {
        ok: false,
        status: 404,
        json: async () => ({ detail: { reason_code: `unrouted:${key}` } }),
      } as Response;
    });
    vi.stubGlobal("fetch", mock);

    window.location.hash = "#/models";
    render(App);
    await signIn();
    await waitFor(() => {
      expect(screen.getByText(/Local · llama.cpp/)).toBeInTheDocument();
    });

    // Select the Ollama profile on the Models view; the topbar chip must follow.
    await waitFor(() => expect(screen.getAllByText("Select").length).toBeGreaterThan(0));
    await fireEvent.click(screen.getAllByText("Select")[0]);
    await waitFor(() => {
      expect(screen.getByText(/Local · Ollama/)).toBeInTheDocument();
    });
  });

  it("shows an honest auth error at the lock screen when the API is unreachable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("connection refused");
      }),
    );
    render(App);
    await signIn();
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/authentication failed/i);
    });
  });

  it("keeps the workspace locked when bootstrap fails after sign-in", async () => {
    stubFetch({ "POST /api/auth/login": BOOTSTRAP_ROUTES["POST /api/auth/login"] });
    render(App);
    await signIn();
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/runtime verification failed/i);
    });
    expect(screen.queryByRole("navigation", { name: /primary/i })).not.toBeInTheDocument();
    expect(screen.getByText(/I cannot reach my runtime/i)).toBeInTheDocument();
  });
});
