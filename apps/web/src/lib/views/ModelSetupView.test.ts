import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { stubFetch } from "../test-helpers";
import ModelSetupView from "./ModelSetupView.svelte";

afterEach(() => vi.unstubAllGlobals());

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
  it("presents the five-stage checklist and lets model setup be deferred", async () => {
    const fetchMock = stubFetch({
      "GET /api/setup": required,
      "PUT /api/setup": { ...required, status: "in_progress", stage: "privacy", model_deferred: true },
      "GET /api/models": { profiles: [], chat_profiles: [] },
    });
    render(ModelSetupView);

    expect(await screen.findByRole("heading", { name: "Choose where Raiker thinks" })).toBeInTheDocument();
    for (const stage of ["Account", "Model", "Privacy", "Backup", "Finish"]) {
      expect(screen.getByText(stage)).toBeInTheDocument();
    }
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

    await fireEvent.click(within(dialog).getAllByRole("button", { name: "Use" })[0]);
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([url, init]) =>
            String(url).endsWith("/api/model-selection") && init?.method === "PUT",
        ),
      ).toBe(true),
    );
    expect(await screen.findByText(/Opus 4.5 is selected/)).toBeInTheDocument();
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

  it("states the privacy boundary as an explicit choice", async () => {
    stubFetch({
      "GET /api/setup": { ...required, status: "in_progress", stage: "privacy" },
      "PUT /api/setup": { ...required, status: "in_progress", stage: "backup", privacy_mode: "local_first" },
      "GET /api/models": { profiles: [], chat_profiles: [] },
    });
    render(ModelSetupView);
    expect(await screen.findByRole("heading", { name: "Choose your privacy boundary" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Local-first/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Balanced/i })).toBeInTheDocument();
  });

  it("never calls a deferred backup protected", async () => {
    stubFetch({
      "GET /api/setup": { ...required, status: "in_progress", stage: "backup" },
      "PUT /api/setup": { ...required, status: "in_progress", stage: "finish", backup_mode: "later" },
      "GET /api/models": { profiles: [], chat_profiles: [] },
    });
    render(ModelSetupView);
    expect(await screen.findByRole("heading", { name: "Create your first backup" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Set up later" })).toBeInTheDocument();
    expect(screen.getByText(/No backup is configured/)).toBeInTheDocument();
  });
});
