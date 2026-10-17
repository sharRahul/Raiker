import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { allProfiles, resetModels } from "../models.svelte";
import { stubFetch } from "../test-helpers";
import ModelSetupView from "./ModelSetupView.svelte";

afterEach(() => {
  vi.unstubAllGlobals();
  resetModels();
});

const required = {
  owner_principal_id: "principal_owner",
  status: "required",
  stage: "model",
  selected_profile_id: null,
  selected_model: null,
  model_deferred: false,
  privacy_mode: null,
  privacy_acknowledged_at: null,
  backup_mode: "later",
  backup_target: null,
  backup_verified_at: null,
  background_service_enabled: false,
  created_at: null,
  updated_at: null,
};

/** The registry shape the matrix builds its rows from: one row per provider. */
function profile(partial: Record<string, unknown>) {
  return {
    profile_id: "p",
    provider: "ollama",
    model: "<model>",
    default_state: "enabled_runtime",
    local_only: true,
    requires_network: false,
    endpoint_kind: "loopback",
    requires_egress_policy: false,
    requires_budget_policy: false,
    runtime_gate: null,
    off_machine: false,
    selected: false,
    connection_configured: false,
    prompt_cache_ttl: null,
    ...partial,
  };
}

const REGISTRY = [
  profile({ profile_id: "raiker-local-llama-cpp", provider: "llama.cpp", model: "local-gguf" }),
  profile({ profile_id: "ollama-local", provider: "ollama" }),
  profile({ profile_id: "lm-studio-local", provider: "lm-studio" }),
  profile({
    profile_id: "anthropic-hosted",
    provider: "anthropic",
    local_only: false,
    requires_network: true,
    endpoint_kind: "remote_hosted",
    off_machine: true,
  }),
  profile({
    profile_id: "openrouter-policy-gated",
    provider: "openrouter",
    local_only: false,
    requires_network: true,
    endpoint_kind: "remote_hosted",
    off_machine: true,
  }),
  profile({
    profile_id: "chatgpt-codex-subscription",
    provider: "chatgpt-codex",
    local_only: false,
    requires_network: true,
    endpoint_kind: "remote_hosted",
    off_machine: true,
  }),
];

describe("first-run setup", () => {
  it("opens on the model, with no welcome screen to read first (Quiet UI)", async () => {
    // FIRST-02 — no Account stage after the account exists. Quiet UI — no
    // Welcome either: the app introduces Chat, Build and Design itself.
    stubFetch({
      "GET /api/setup": { ...required, stage: "welcome" },
      "GET /api/models": { profiles: [], chat_profiles: [] },
      "GET /api/host/update": { installation: { distribution: "desktop", version: "1.0.0" } },
    });
    render(ModelSetupView);

    expect(await screen.findByRole("heading", { name: "Choose how Raiker should think" })).toBeInTheDocument();
    const rail = screen.getByRole("list", { name: "Setup progress" });
    for (const stage of ["Model", "Privacy", "Ready"]) {
      expect(within(rail).getByText(stage)).toBeInTheDocument();
    }
    for (const gone of ["Welcome", "Permissions", "Account", "Backup"]) {
      expect(within(rail).queryByText(gone)).not.toBeInTheDocument();
    }
  });

  it("shows a stored account stage as the first stage rather than a blank one", async () => {
    stubFetch({
      "GET /api/setup": { ...required, stage: "account" },
      "GET /api/models": { profiles: [], chat_profiles: [] },
    });
    render(ModelSetupView);

    // A source checkout keeps the device check, so it opens there.
    expect(await screen.findByRole("heading", { name: "What this computer can run" })).toBeInTheDocument();
  });

  it("leads with the easiest working path and keeps the matrix on request", async () => {
    // FIRST-05 — a runtime installed here needs no account and no key.
    stubFetch({
      "GET /api/setup": required,
      "GET /api/models": {
        profiles: [profile({ profile_id: "ollama-local", provider: "ollama", provider_detected: true, configured: true })],
        chat_profiles: [],
      },
      "GET /api/model-library": { roots: [], models: [] },
      "GET /api/models/ollama-local/provider-models": {
        profile_id: "ollama-local", provider: "ollama", status: "unavailable", reason_code: "x", models: [],
      },
    });
    render(ModelSetupView);

    expect(await screen.findByText("Recommended")).toBeInTheDocument();
    expect(screen.getByText(/Ollama is installed here/)).toBeInTheDocument();
    // The full matrix is one press away rather than the opening move.
    expect(screen.getByRole("button", { name: "Other options" })).toBeInTheDocument();
  });

  // Found in the 2026-10-11 live round: a global model chosen on Models before
  // returning to setup left this step offering only "Decide later".
  it("counts a global model already chosen elsewhere as the choice", async () => {
    const fetchMock = stubFetch({
      "GET /api/setup": required,
      "PUT /api/setup": {
        ...required, status: "in_progress", selected_profile_id: "openrouter-policy-gated", selected_model: "openai/gpt-4o-mini",
      },
      "GET /api/models": {
        profiles: [],
        chat_profiles: [],
        current_profile_id: "openrouter-policy-gated",
        current_model: "openai/gpt-4o-mini",
      },
    });
    render(ModelSetupView);

    expect(await screen.findByRole("button", { name: "Continue" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Decide later" })).not.toBeInTheDocument();
    const put = fetchMock.mock.calls.find(([url, init]) => String(url).endsWith("/api/setup") && init?.method === "PUT");
    expect(JSON.parse(String(put?.[1]?.body))).toMatchObject({
      selected_profile_id: "openrouter-policy-gated", selected_model: "openai/gpt-4o-mini", model_deferred: false,
    });
  });

  it("opens the providers when the recommendation asks for a model", async () => {
    stubFetch({
      "GET /api/setup": required,
      "GET /api/models": {
        profiles: [
          profile({
            profile_id: "openrouter-policy-gated", provider: "openrouter", local_only: false,
            requires_network: true, endpoint_kind: "remote_hosted", off_machine: true,
            connection_configured: true, configured: true,
          }),
        ],
        chat_profiles: [],
      },
      "GET /api/model-library": { roots: [], models: [] },
      // BUG-332 — asked once before it is recommended as connected.
      "GET /api/models/openrouter-policy-gated/provider-models": {
        status: "available", models: ["openai/gpt-4o-mini"], reason_code: null,
      },
    });
    render(ModelSetupView);

    expect(await screen.findByText(/OpenRouter is connected/)).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Choose a model" }));
    expect(screen.queryByRole("button", { name: "Other options" })).not.toBeInTheDocument();
    // BUG-344 — one press: that provider's picker opens, not a second button.
    const picker = await screen.findByRole("dialog", { name: "OpenRouter models" });
    expect(within(picker).getAllByRole("button", { name: /^Use / })).toHaveLength(1);
  });

  it("does not call a stored key that lists nothing connected (BUG-332)", async () => {
    stubFetch({
      "GET /api/setup": required,
      "GET /api/models": {
        profiles: [
          profile({
            profile_id: "anthropic-hosted", provider: "anthropic", local_only: false,
            requires_network: true, endpoint_kind: "remote_hosted", off_machine: true,
            connection_configured: true, configured: true,
          }),
        ],
        chat_profiles: [],
      },
      "GET /api/model-library": { roots: [], models: [] },
      "GET /api/models/anthropic-hosted/provider-models": {
        status: "unavailable", models: [], reason_code: "provider_workspace_required",
      },
    });
    render(ModelSetupView);

    expect(await screen.findByText("Anthropic needs its workspace ID")).toBeInTheDocument();
    expect(screen.queryByText(/Anthropic is connected/)).toBeNull();
    expect(screen.getByRole("button", { name: "Add the workspace ID" })).toBeInTheDocument();
  });

  it("lets model setup be deferred", async () => {
    const fetchMock = stubFetch({
      "GET /api/setup": required,
      "PUT /api/setup": { ...required, status: "in_progress", stage: "privacy", model_deferred: true },
      "GET /api/models": { profiles: [], chat_profiles: [] },
    });
    render(ModelSetupView);

    expect(
      await screen.findByRole("heading", { name: "Choose how Raiker should think" }),
    ).toBeInTheDocument();
    // FIRST-06 — the Models page is deeper configuration, not the way out of an
    // incomplete flow.
    expect(screen.getByRole("link", { name: "Advanced setup" })).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Decide later" }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([url, init]) =>
      String(url).endsWith("/api/setup") && init?.method === "PUT",
    )).toBe(true));
  });

  it("gives every provider its own row, detecting the local ones on open", async () => {
    // The old stage listed only profiles that already had a concrete model, so a
    // fresh install read "No model connection yet" and sent the owner elsewhere.
    stubFetch({
      "GET /api/setup": required,
      "GET /api/models": { profiles: REGISTRY, chat_profiles: [] },
      "GET /api/model-library": { roots: [{ path: "D:\\Models" }], models: [] },
      "GET /api/models/ollama-local/provider-models": {
        profile_id: "ollama-local",
        provider: "ollama",
        status: "available",
        reason_code: null,
        models: ["gemma4:31b-cloud", "qwen3:8b"],
      },
      "GET /api/models/lm-studio-local/provider-models": {
        profile_id: "lm-studio-local",
        provider: "lm-studio",
        status: "unavailable",
        reason_code: "provider_unreachable",
        models: [],
      },
    });
    render(ModelSetupView);

    // One row each, and the local runtimes are asked without being clicked.
    expect(await screen.findByText("Local GGUF")).toBeInTheDocument();
    for (const label of ["Ollama", "LM Studio", "Anthropic", "OpenRouter"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    // BUG-264 — the row no longer carries a `<select>` of the catalogue. It
    // reports what the runtime answered and opens the picker, which is the one
    // place a model is chosen and the only one with a search.
    const ollama = await screen.findByRole("group", { name: "Ollama" });
    expect(await within(ollama).findByText(/2 models from Ollama/)).toBeInTheDocument();
    expect(within(ollama).getByRole("button", { name: "Choose a model" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Ollama model")).not.toBeInTheDocument();
    // A runtime that is not running says so rather than offering a guess.
    expect(await screen.findByText(/LM Studio is not running on this device/)).toBeInTheDocument();
    // A key-based provider has an input until a key is stored, and no picker.
    expect(screen.getByLabelText("Anthropic API key")).toBeInTheDocument();
    expect(screen.queryByLabelText("Anthropic model")).not.toBeInTheDocument();
  });

  it("stores a key, then lists that provider's own models and pins one", async () => {
    const fetchMock = stubFetch({
      "GET /api/setup": required,
      "PUT /api/setup": { ...required, status: "in_progress", selected_model: "claude-opus-4-5" },
      "GET /api/models": { profiles: REGISTRY, chat_profiles: [] },
      "GET /api/model-library": { roots: [], models: [] },
      "GET /api/models/ollama-local/provider-models": {
        profile_id: "ollama-local", provider: "ollama", status: "unavailable", reason_code: "x", models: [],
      },
      "GET /api/models/lm-studio-local/provider-models": {
        profile_id: "lm-studio-local", provider: "lm-studio", status: "unavailable", reason_code: "x", models: [],
      },
      "PUT /api/models/anthropic-hosted/connection": { ok: true, connection_configured: true },
      "GET /api/models/anthropic-hosted/provider-models": {
        profile_id: "anthropic-hosted",
        provider: "anthropic",
        status: "available",
        reason_code: null,
        models: ["claude-opus-4-5", "claude-haiku-4-5-20251001"],
      },
      "PUT /api/model-selection": { ok: true, profile_id: "anthropic-hosted", model: "claude-opus-4-5" },
      "POST /api/model-readiness/check": { profile_id: "anthropic-hosted", model: "claude-opus-4-5", state: "ready", ready: true },
    });
    render(ModelSetupView);

    const row = await screen.findByRole("group", { name: "Anthropic" });
    await fireEvent.input(within(row).getByLabelText("Anthropic API key"), {
      target: { value: "sk-ant-test" },
    });
    await fireEvent.click(within(row).getByRole("button", { name: "Save and list models" }));

    expect(await screen.findByText(/Anthropic answered with 2 models/)).toBeInTheDocument();
    // The key's value never comes back — the row can only say one is stored.
    expect(screen.queryByLabelText("Anthropic API key")).not.toBeInTheDocument();

    // BUG-264 — choosing happens in the picker, which is also where the search
    // is. The catalogue is the provider's own answer; no model name is invented.
    await fireEvent.click(within(row).getByRole("button", { name: "Choose a model" }));
    const dialog = await screen.findByRole("dialog", { name: "Anthropic models" });
    expect(
      [...dialog.querySelectorAll(".name")].map((name) => name.textContent),
    ).toEqual(["Opus 4.5", "Haiku 4.5"]);

    await fireEvent.click(within(dialog).getAllByRole("button", { name: /^Use / })[0]);
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([url, init]) =>
            String(url).endsWith("/api/model-selection") && init?.method === "PUT",
        ),
      ).toBe(true),
    );
    expect(await screen.findByText(/Opus 4.5 is selected/)).toBeInTheDocument();
    // The choice is the owner's own act, so its first check is taken with it.
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([url, init]) =>
            String(url).endsWith("/api/model-readiness/check") && init?.method === "POST",
        ),
      ).toBe(true),
    );
    // …and the composer's shared store holds what setup now knows, so Ready →
    // Chat opens on the chosen, checked model rather than the earlier default.
    await waitFor(() => expect(allProfiles().length).toBeGreaterThan(0));
  });

  // BUG-274 — an identity-linked key authenticates and then acts inside one
  // workspace. First run is where an owner most often meets that refusal, and
  // it used to answer with a bare reason code and no way forward.
  it("raises the workspace field on the row the provider asked it of", async () => {
    const fetchMock = stubFetch({
      "GET /api/setup": required,
      "GET /api/models": { profiles: REGISTRY, chat_profiles: [] },
      "GET /api/model-library": { roots: [], models: [] },
      "GET /api/models/ollama-local/provider-models": {
        profile_id: "ollama-local", provider: "ollama", status: "unavailable", reason_code: "x", models: [],
      },
      "GET /api/models/lm-studio-local/provider-models": {
        profile_id: "lm-studio-local", provider: "lm-studio", status: "unavailable", reason_code: "x", models: [],
      },
      "PUT /api/models/anthropic-hosted/connection": { ok: true, connection_configured: true },
      "GET /api/models/anthropic-hosted/provider-models": {
        profile_id: "anthropic-hosted",
        provider: "anthropic",
        status: "unavailable",
        reason_code: "provider_workspace_required:http_400",
        models: [],
      },
    });
    render(ModelSetupView);

    const row = await screen.findByRole("group", { name: "Anthropic" });
    // Not offered up front: a box asking for a "workspace ID" on first run is a
    // question most owners cannot answer.
    expect(within(row).queryByLabelText("Anthropic workspace ID")).toBeNull();

    await fireEvent.input(within(row).getByLabelText("Anthropic API key"), {
      target: { value: "sk-ant-test" },
    });
    await fireEvent.click(within(row).getByRole("button", { name: "Save and list models" }));

    // The refusal is a repair, in words, not a reason code.
    expect(await within(row).findByText(/identity-linked/i)).toBeInTheDocument();
    const field = await within(row).findByLabelText("Anthropic workspace ID");
    await fireEvent.input(field, { target: { value: "wrkspc_01" } });
    await fireEvent.click(within(row).getByRole("button", { name: "Add workspace" }));

    // Sent on its own, so it merges into the connection rather than replacing
    // the key that was just stored.
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/models/anthropic-hosted/connection",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({
            endpoint: null,
            api_key: null,
            admin_api_key: null,
            workspace_id: "wrkspc_01",
          }),
        }),
      ),
    );
  });

  it("signs in to the ChatGPT subscription without asking for an API key", async () => {
    const fetchMock = stubFetch({
      "GET /api/setup": required,
      "GET /api/models": { profiles: REGISTRY, chat_profiles: [] },
      "GET /api/model-library": { roots: [], models: [] },
      "GET /api/models/ollama-local/provider-models": {
        profile_id: "ollama-local", provider: "ollama", status: "unavailable", reason_code: "x", models: [],
      },
      "GET /api/models/lm-studio-local/provider-models": {
        profile_id: "lm-studio-local", provider: "lm-studio", status: "unavailable", reason_code: "x", models: [],
      },
      "GET /api/models/chatgpt-codex/status": { connection_status: "signed_out", plan_type: null },
      "POST /api/models/chatgpt-codex/login": { ok: true, connection_status: "login_pending" },
    });
    render(ModelSetupView);

    const row = await screen.findByRole("group", { name: "ChatGPT subscription" });
    expect(within(row).queryByLabelText(/API key/i)).not.toBeInTheDocument();
    await fireEvent.click(within(row).getByRole("button", { name: "Sign in with ChatGPT" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/models/chatgpt-codex/login",
        expect.objectContaining({ method: "POST" }),
      ),
    );
    expect(await within(row).findByText(/Finish sign-in in the browser/)).toBeInTheDocument();
  });

  it("names the connected plan and still offers a way to change accounts", async () => {
    // The row used to replace every account control with a model picker as soon
    // as Codex reported a session, so an owner holding both a Plus and a Pro
    // subscription had no way to move Raiker from one to the other.
    stubFetch({
      "GET /api/setup": required,
      "GET /api/models": { profiles: REGISTRY, chat_profiles: [] },
      "GET /api/model-library": { roots: [], models: [] },
      "GET /api/models/ollama-local/provider-models": {
        profile_id: "ollama-local", provider: "ollama", status: "unavailable", reason_code: "x", models: [],
      },
      "GET /api/models/lm-studio-local/provider-models": {
        profile_id: "lm-studio-local", provider: "lm-studio", status: "unavailable", reason_code: "x", models: [],
      },
      "GET /api/models/chatgpt-codex/status": { connection_status: "connected", plan_type: "pro" },
      "GET /api/models/chatgpt-codex-subscription/provider-models": {
        profile_id: "chatgpt-codex-subscription", provider: "chatgpt-codex",
        status: "available", reason_code: null, models: ["gpt-5.6"],
      },
    });
    render(ModelSetupView);

    const row = await screen.findByRole("group", { name: "ChatGPT subscription" });
    expect(await within(row).findByText("Pro connected")).toBeInTheDocument();
    expect(within(row).getByRole("button", { name: "Switch account" })).toBeInTheDocument();
    expect(within(row).getByRole("button", { name: "Sign out" })).toBeInTheDocument();
    expect(within(row).queryByLabelText(/API key/i)).not.toBeInTheDocument();
  });

  it("says Codex is missing rather than blaming the status read", async () => {
    stubFetch({
      "GET /api/setup": required,
      "GET /api/models": { profiles: REGISTRY, chat_profiles: [] },
      "GET /api/model-library": { roots: [], models: [] },
      "GET /api/models/ollama-local/provider-models": {
        profile_id: "ollama-local", provider: "ollama", status: "unavailable", reason_code: "x", models: [],
      },
      "GET /api/models/lm-studio-local/provider-models": {
        profile_id: "lm-studio-local", provider: "lm-studio", status: "unavailable", reason_code: "x", models: [],
      },
      "GET /api/models/chatgpt-codex/status": { connection_status: "codex_missing", plan_type: null },
    });
    render(ModelSetupView);

    const row = await screen.findByRole("group", { name: "ChatGPT subscription" });
    expect(await within(row).findByText("Codex is not installed on this device.")).toBeInTheDocument();
    expect(within(row).getByRole("button", { name: "Sign in with ChatGPT" })).toBeInTheDocument();
  });

  it("puts a filter over a catalogue too long to scroll", async () => {
    // OpenRouter really does serve 413 models. A native select of that length is
    // technically honest and practically unusable, and the first-run wizard is the
    // worst place to make someone scroll one.
    const many = Array.from({ length: 40 }, (_, index) => `vendor/model-${index}-instruct`);
    stubFetch({
      "GET /api/setup": required,
      "GET /api/models": { profiles: REGISTRY, chat_profiles: [] },
      "GET /api/model-library": { roots: [], models: [] },
      "GET /api/models/ollama-local/provider-models": {
        profile_id: "ollama-local", provider: "ollama", status: "unavailable", reason_code: "x", models: [],
      },
      "GET /api/models/lm-studio-local/provider-models": {
        profile_id: "lm-studio-local", provider: "lm-studio", status: "unavailable", reason_code: "x", models: [],
      },
      "PUT /api/models/openrouter-policy-gated/connection": { ok: true, connection_configured: true },
      "GET /api/models/openrouter-policy-gated/provider-models": {
        profile_id: "openrouter-policy-gated",
        provider: "openrouter",
        status: "available",
        reason_code: null,
        models: many,
      },
    });
    render(ModelSetupView);

    const row = await screen.findByRole("group", { name: "OpenRouter" });
    await fireEvent.input(within(row).getByLabelText("OpenRouter API key"), {
      target: { value: "sk-or-test" },
    });
    await fireEvent.click(within(row).getByRole("button", { name: "Save and list models" }));

    // BUG-260/BUG-264 — the search is inside the picker, over the whole
    // catalogue, instead of a filter field wedged beside a dropdown.
    await fireEvent.click(await within(row).findByRole("button", { name: "Choose a model" }));
    const dialog = await screen.findByRole("dialog", { name: "OpenRouter models" });
    const search = within(dialog).getByLabelText("Search models");
    expect(dialog.querySelectorAll(".name")).toHaveLength(40);

    await fireEvent.input(search, { target: { value: "model-7-" } });
    await waitFor(() => expect(dialog.querySelectorAll(".name")).toHaveLength(1));
    expect(dialog).toHaveTextContent("Model 7 Instruct");

    // A search that matches nothing says so rather than showing an empty list.
    await fireEvent.input(search, { target: { value: "nothing-like-this" } });
    await waitFor(() => expect(dialog).toHaveTextContent(/No model matches/));
  });

  it("asks where model requests may travel, not which authority system to adopt", async () => {
    // FIRST-07 — `Local-first` and `Balanced` read as a second Permissions.
    stubFetch({
      "GET /api/setup": { ...required, status: "in_progress", stage: "privacy" },
      "PUT /api/setup": { ...required, status: "in_progress", stage: "finish", privacy_mode: "local_first" },
      "GET /api/models": { profiles: [], chat_profiles: [] },
    });
    render(ModelSetupView);

    expect(
      await screen.findByRole("heading", { name: "Where may Raiker send model requests?" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Local only/i })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Local, and the providers I connect/i }),
    ).toBeInTheDocument();
    // Quiet UI — the question and its two answers; no paragraph under them.
    expect(screen.queryByText(/Permissions still govern what Raiker may do/)).not.toBeInTheDocument();
  });

  it("finishes into work, with backup recommended rather than required", async () => {
    // FIRST-08/09 — a NAS path asked for before first use is friction in front
    // of the work, and "Open Workbench" named a place nothing else calls that.
    stubFetch({
      "GET /api/setup": {
        ...required,
        status: "in_progress",
        stage: "finish",
        privacy_mode: "local_first",
        selected_model: "claude-sonnet-4",
        selected_profile_id: "p",
      },
      "GET /api/models": { profiles: [], chat_profiles: [] },
    });
    render(ModelSetupView);

    expect(await screen.findByRole("heading", { name: "Your Raiker is ready" })).toBeInTheDocument();
    for (const mode of ["Chat", "Build", "Design"]) {
      expect(screen.getByRole("button", { name: mode })).toBeInTheDocument();
    }
    expect(screen.getByRole("button", { name: "Start using Raiker" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Open Workbench" })).not.toBeInTheDocument();
    // Still offered, and still real: nothing claims a backup until one verifies.
    expect(screen.getByRole("button", { name: "Set up backup" })).toBeInTheDocument();
    // Quiet UI — no summary table restating the choices just made.
    expect(screen.queryByText("Model requests")).not.toBeInTheDocument();
  });

  /*
   * REM-LAUNCH-01 — the last stage may not claim a readiness it has not got.
   *
   * "Your Raiker is ready" was unconditional, and sat directly above a summary
   * whose Model row could read "Decide later". First run is the one place an
   * owner has nothing to check the claim against.
   */
  it("says setup is saved, not ready, when the model was deferred", async () => {
    stubFetch({
      "GET /api/setup": {
        ...required,
        status: "in_progress",
        stage: "finish",
        model_deferred: true,
        privacy_mode: "balanced",
      },
      "GET /api/models": { profiles: [], chat_profiles: [] },
    });
    render(ModelSetupView);

    expect(await screen.findByRole("heading", { name: "Setup saved" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Your Raiker is ready" })).toBeNull();
    // Exploration is still permitted — every mode opens — and the one that
    // cannot do its work yet names the page that fixes it.
    for (const mode of ["Chat", "Build", "Design"]) {
      expect(screen.getByRole("button", { name: mode })).toBeEnabled();
    }
    expect(screen.getAllByTitle("Needs a model to answer with.")).toHaveLength(2);
    expect(screen.getByRole("link", { name: "Connect an image provider" })).toHaveAttribute(
      "href",
      "#/models?tab=add",
    );
  });

  it("keeps Design's prerequisite separate from Chat's", async () => {
    // A chat model is not an image model, and a launch screen that requires
    // every optional service before it will call anything ready is the defect
    // in the other direction.
    stubFetch({
      "GET /api/setup": {
        ...required,
        status: "in_progress",
        stage: "finish",
        selected_model: "claude-sonnet-4",
        selected_profile_id: "p",
      },
      "GET /api/models": { profiles: [], chat_profiles: [] },
    });
    render(ModelSetupView);

    await screen.findByRole("heading", { name: "Your Raiker is ready" });
    expect(screen.queryByTitle("Needs a model to answer with.")).toBeNull();
    expect(screen.getByTitle("Needs a provider that returns images.")).toBeInTheDocument();
  });

  it("never calls a deferred backup protected", async () => {
    stubFetch({
      "GET /api/setup": { ...required, status: "in_progress", stage: "finish" },
      "GET /api/models": { profiles: [], chat_profiles: [] },
    });
    render(ModelSetupView);

    await fireEvent.click(await screen.findByRole("button", { name: "Set up backup" }));
    expect(screen.getByLabelText(/Backup folder/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Create and verify backup" }),
    ).toBeInTheDocument();
  });
});

const check = (id: string, state: string, extra: Record<string, unknown> = {}) => ({
  id,
  label: id,
  state,
  detail: `${id} detail`,
  remedy: "",
  mandatory: true,
  data: {},
  ...extra,
});

describe("DIST-05 — a desktop installation was checked while it installed", () => {
  const desktopUpdate = { installation: { distribution: "desktop", version: "1.0.0" } };

  it("asks only model, privacy and done, with no device or installation stage", async () => {
    const fetchMock = stubFetch({
      "GET /api/setup": { ...required, stage: "welcome" },
      "GET /api/models": { profiles: [], chat_profiles: [] },
      "GET /api/host/update": desktopUpdate,
      "PUT /api/setup": { ...required, status: "in_progress", stage: "privacy", model_deferred: true },
    });
    render(ModelSetupView);

    expect(await screen.findByRole("heading", { name: "Choose how Raiker should think" })).toBeInTheDocument();
    const rail = screen.getByRole("list", { name: "Setup progress" });
    await waitFor(() => expect(within(rail).queryByText("This device")).toBeNull());
    expect(within(rail).queryByText("Check")).toBeNull();
    expect(within(rail).getAllByRole("listitem")).toHaveLength(3);

    await fireEvent.click(screen.getByRole("button", { name: "Decide later" }));
    const put = fetchMock.mock.calls.find(([url, init]) => String(url).includes("/api/setup") && init?.method === "PUT");
    expect(JSON.parse(String(put?.[1]?.body)).stage).toBe("privacy");
  });

  it("opens a stored device stage on Model rather than a check that already ran", async () => {
    stubFetch({
      "GET /api/setup": { ...required, status: "in_progress", stage: "system" },
      "GET /api/models": { profiles: [], chat_profiles: [] },
      "GET /api/host/update": desktopUpdate,
    });
    render(ModelSetupView);
    expect(await screen.findByRole("heading", { name: "Choose how Raiker should think" })).toBeInTheDocument();
  });
});

describe("DIST-05/06 — this device, permissions and the installation check", () => {
  it("says what this device can run, measured locally, without requiring a GPU", async () => {
    stubFetch({
      "GET /api/setup": { ...required, status: "in_progress", stage: "system" },
      "GET /api/models": { profiles: [], chat_profiles: [] },
      "GET /api/setup/system": {
        checks: [
          check("os", "pass", { label: "Operating system", detail: "Ubuntu 24.04" }),
          check("gpu", "info", { label: "Graphics acceleration", detail: "No dedicated GPU driver found", mandatory: false,
            remedy: "Optional. Hosted providers and small local models need no GPU." }),
        ],
        blocking: [],
        ready: true,
        recommended_local_model: { parameters: "3B–8B", download: "about 2–5 GB", note: "Small local models run." },
        locations: { data: "/home/o/.local/share/raiker", models: "/m", backups: "/b" },
      },
    });
    render(ModelSetupView);

    expect(await screen.findByRole("heading", { name: "What this computer can run" })).toBeInTheDocument();
    const checks = await screen.findByRole("list", { name: "Device checks" });
    expect(within(checks).getByText("Ubuntu 24.04")).toBeInTheDocument();
    // The state is said in words, not colour alone, and a missing GPU is a note.
    expect(within(checks).getByText("Note")).toBeInTheDocument();
    expect(within(checks).getByText(/need no GPU/)).toBeInTheDocument();
    expect(screen.getByText(/Nothing is downloaded unless you choose a model/)).toBeInTheDocument();
    expect(screen.getByText("/home/o/.local/share/raiker")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("names a blocking requirement instead of hiding it", async () => {
    stubFetch({
      "GET /api/setup": { ...required, status: "in_progress", stage: "system" },
      "GET /api/models": { profiles: [], chat_profiles: [] },
      "GET /api/setup/system": {
        checks: [check("memory", "fail", { label: "Memory", detail: "2.0 GB", remedy: "Raiker needs at least 4 GB of memory." })],
        blocking: ["memory"],
        ready: false,
        recommended_local_model: { parameters: "1B–3B", download: "about 1–2 GB", note: "Limited." },
        locations: { data: "/d", models: "/m", backups: "/b" },
      },
    });
    render(ModelSetupView);

    expect(await screen.findByText("Raiker needs at least 4 GB of memory.")).toBeInTheDocument();
    expect(screen.getByText("Needs attention")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/does not meet a requirement/);
  });

  it("opens a stored permissions stage on the stage after it (Quiet UI)", async () => {
    // Permissions was a read-only copy of the Permissions page; it is not a
    // setup stage any more, and nothing in setup writes a permission.
    const fetchMock = stubFetch({
      "GET /api/setup": { ...required, status: "in_progress", stage: "permissions" },
      "GET /api/models": { profiles: [], chat_profiles: [] },
      "POST /api/setup/verify": { checks: [], failed: [], ready: true },
    });
    render(ModelSetupView);

    expect(await screen.findByRole("heading", { name: "Checking your installation" })).toBeInTheDocument();
    const writes = fetchMock.mock.calls.filter(([url, init]) =>
      String(url).includes("capabilit") && (init?.method ?? "GET").toUpperCase() !== "GET",
    );
    expect(writes).toHaveLength(0);
  });

  it("checks every mandatory part and makes one request to the chosen model", async () => {
    const fetchMock = stubFetch({
      "GET /api/setup": {
        ...required, status: "in_progress", stage: "verify",
        selected_profile_id: "ollama-local", selected_model: "llama3.2:3b",
      },
      "GET /api/models": { profiles: [], chat_profiles: [] },
      "POST /api/setup/verify": {
        checks: [check("database", "pass", { label: "Encrypted database", detail: "Opened and read" })],
        failed: [],
        ok: true,
      },
      "POST /api/model-readiness/check": {
        profile_id: "ollama-local", model: "llama3.2:3b", state: "ready", ready: true,
        summary: "The model answered.", remediation: "", reason_code: "", evidence: {},
        owner_principal_id: "o", endpoint_fingerprint: "f", checked_at: null, expires_at: null,
      },
    });
    render(ModelSetupView);

    expect(await screen.findByRole("heading", { name: "Checking your installation" })).toBeInTheDocument();
    expect(await screen.findByText("Opened and read")).toBeInTheDocument();
    expect(await screen.findByText("The model answered.")).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/api/model-readiness/check"))).toBe(true);
    expect(screen.getByRole("button", { name: "Continue" })).toBeEnabled();
  });

  it("says when a required part failed and still lets the owner continue", async () => {
    stubFetch({
      "GET /api/setup": { ...required, status: "in_progress", stage: "verify", model_deferred: true },
      "GET /api/models": { profiles: [], chat_profiles: [] },
      "POST /api/setup/verify": {
        checks: [check("web", "fail", { label: "Application window content", detail: "The interface files are missing", remedy: "Reinstall Raiker." })],
        failed: ["web"],
        ok: false,
      },
    });
    render(ModelSetupView);

    expect(await screen.findByText("Reinstall Raiker.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Diagnostics" })).toHaveAttribute("href", "#/diagnostics");
    expect(screen.getByRole("button", { name: "Continue anyway" })).toBeEnabled();
  });
});

describe("BUG-331 — the model step does not wait on every provider", () => {
  it("shows the step from setup at once and the providers when they answer", async () => {
    let answerModels: (value: unknown) => void = () => {};
    const models = new Promise((resolve) => (answerModels = resolve));
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
        if (url.includes("/api/setup")) return { ok: true, status: 200, json: async () => required } as Response;
        if (url.includes("/api/models")) {
          await models;
          return {
            ok: true,
            status: 200,
            json: async () => ({ profiles: REGISTRY, current_profile_id: null, current_model: null }),
          } as Response;
        }
        return { ok: true, status: 200, json: async () => ({}) } as Response;
      }),
    );
    render(ModelSetupView);
    expect(await screen.findByRole("heading", { name: "Choose how Raiker should think" })).toBeInTheDocument();
    expect(screen.getByText(/Looking for the providers and runtimes/)).toBeInTheDocument();
    expect(screen.queryByText("Preparing your setup…")).toBeNull();
    answerModels(null);
    await waitFor(() => expect(screen.queryByText(/Looking for the providers and runtimes/)).toBeNull());
  });
});

