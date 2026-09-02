// Coverage for the Models view: its action-category tabs (Local, Hosted,
// Hugging Face, Activity, Routing, Pricing, Posture), provider selection and catalogue, and the fallback-sequence
// and advisor editors on the Routing tab. The read is the single GET
// /api/models; writes go to PUT /api/model-fallback, /api/model-selection, and
// /api/model-advisor (human gate-manager only, enforced server-side).
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ModelProfile, ModelsView as ModelsData } from "../apiTypes";
import { stubFetch, stubFetchPending } from "../test-helpers";
import ModelsView from "./ModelsView.svelte";

afterEach(() => vi.unstubAllGlobals());

function profile(partial: Partial<ModelProfile>): ModelProfile {
  return {
    profile_id: "p",
    provider: "llama.cpp",
    model: "local-gguf",
    default_state: "disabled",
    local_only: true,
    requires_network: false,
    endpoint_kind: "local",
    requires_egress_policy: false,
    requires_budget_policy: false,
    runtime_gate: null,
    off_machine: false,
    selected: false,
    prompt_cache_ttl: null,
    ...partial,
  };
}

function models(partial: Partial<ModelsData>): ModelsData {
  return {
    profiles: [
      profile({ profile_id: "raiker-local-llama-cpp", provider: "llama.cpp" }),
      profile({
        profile_id: "anthropic-hosted",
        provider: "anthropic",
        off_machine: true,
      }),
    ],
    current_profile_id: null,
    current_model: null,
    advisor_profile_id: null,
    advisor_model_gate_state: "enabled_runtime",
    hosted_model_gate_state: "enabled_runtime",
    private_network_model_gate_state: "enabled_runtime",
    model_egress_allowlist_configured: false,
    remote_profile_count: 1,
    fallback_sequence: [],
    no_silent_hosted_fallback: true,
    ...partial,
  };
}

describe("ModelsView state grammar", () => {
  it("refreshes connected provider catalogues before reloading model choices", async () => {
    const mock = stubFetch({
      "GET /api/models": models({
        profiles: [
          profile({
            profile_id: "ollama-local-openai-compatible",
            provider: "ollama",
            model: "qwen3",
          }),
        ],
      }),
      "POST /api/models/catalogues/refresh": {
        providers: [
          {
            profile_id: "ollama-local-openai-compatible",
            provider: "ollama",
            status: "available",
            reason_code: null,
            model_count: 1,
          },
        ],
      },
    });
    render(ModelsView, { tab: "local" });

    await fireEvent.click(
      await screen.findByRole("button", { name: "Refresh connected providers" }),
    );

    await waitFor(() =>
      expect(mock).toHaveBeenCalledWith(
        "/api/models/catalogues/refresh",
        expect.objectContaining({ method: "POST" }),
      ),
    );
    await waitFor(() => {
      const reads = mock.mock.calls.filter(([url]) => url === "/api/models");
      expect(reads.length).toBeGreaterThanOrEqual(2);
    });
  });

  it("consolidates four llama.cpp slots and adds one four-slot MLX row below it", async () => {
    const localProfiles = [1, 2, 3, 4].flatMap((slot) => [
      profile({
        profile_id: `raiker-local-llama-cpp${slot === 1 ? "" : `-${slot}`}`,
        provider: "llama.cpp",
      }),
      profile({
        profile_id: `raiker-local-mlx${slot === 1 ? "" : `-${slot}`}`,
        provider: "mlx",
        model: "<model>",
      }),
    ]);
    stubFetch({
      "GET /api/models": models({ profiles: localProfiles }),
      "GET /api/model-library": {
        roots: [],
        models: [
          { model_id: "gguf-1", name: "Gemma GGUF", primary_path: "/models/gemma.gguf", complete: true, format: "gguf" },
          { model_id: "mlx-1", name: "Gemma MLX", primary_path: "/models/gemma-mlx", complete: true, format: "mlx" },
        ],
      },
    });

    render(ModelsView, { tab: "local" });

    const gguf = await screen.findByRole("group", { name: "llama.cpp GGUF" });
    const mlx = screen.getByRole("group", { name: "MLX" });
    expect(within(gguf).getAllByRole("combobox")).toHaveLength(4);
    expect(within(mlx).getAllByRole("combobox")).toHaveLength(4);
    expect(gguf.compareDocumentPosition(mlx) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(document.querySelectorAll('.framework-row[data-provider="llama.cpp"]')).toHaveLength(1);
    expect(document.querySelectorAll('.framework-row[data-provider="mlx"]')).toHaveLength(1);
  });

  it("sets the global default from every configured provider/model pair", async () => {
    const anthropic = profile({
      profile_id: "anthropic",
      provider: "anthropic",
      model: "opus",
      configured: true,
    });
    const ollama = profile({
      profile_id: "ollama",
      provider: "ollama",
      model: "gemma4:31b-cloud",
      configured: true,
      selected: true,
    });
    const mock = stubFetch({
      "GET /api/models": models({
        profiles: [anthropic, ollama],
        chat_profiles: [anthropic, ollama],
        current_profile_id: "ollama",
        current_model: "gemma4:31b-cloud",
      }),
      "PUT /api/model-selection": { ok: true },
    });
    render(ModelsView);

    const select = await screen.findByRole("combobox", {
      name: "Global model",
    });
    expect(select).toHaveValue('["ollama","gemma4:31b-cloud"]');
    await fireEvent.change(select, {
      target: { value: '["anthropic","opus"]' },
    });

    await waitFor(() =>
      expect(mock).toHaveBeenCalledWith(
        "/api/model-selection",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({ profile_id: "anthropic", model: "opus" }),
        }),
      ),
    );
  });

  // BUG-69 — the headline counted providers with a saved credential and called
  // them "set up". A saved key is not a working model: on 2026-08-09 a live run
  // showed "1 of 10 providers set up" on this page while Chat, correctly, said
  // "No readiness check exists for this exact model" and refused to send.
  it("counts models proven ready, not providers holding a credential", async () => {
    const anthropic = profile({
      profile_id: "anthropic",
      provider: "anthropic",
      model: "opus",
      configured: true,
      connection_configured: true,
      ready: false,
      readiness_state: "not_configured",
    });
    stubFetch({
      "GET /api/models": models({
        profiles: [anthropic],
        chat_profiles: [anthropic],
        ready_provider_count: 0,
      }),
    });
    render(ModelsView);

    expect(await screen.findByText("0 models ready")).toBeInTheDocument();
    expect(screen.queryByText("providers set up")).not.toBeInTheDocument();
  });

  // The page used to put local runtimes, hosted accounts, advanced routers,
  // install actions, and the GGUF library in one scroll called "Providers".
  // They are separate jobs: obtaining a model that runs on this machine, and
  // signing in to somebody else's. Each now owns a tab.
  const localProfile = () =>
    profile({
      profile_id: "ollama-local-openai-compatible",
      provider: "ollama",
      model: "gemma4:31b-cloud",
      local_only: true,
      requires_network: false,
      endpoint_kind: "local",
    });
  const hostedProfile = () =>
    profile({
      profile_id: "anthropic-hosted",
      provider: "anthropic",
      model: "claude-haiku-4-5-20251001",
      local_only: false,
      requires_network: true,
      off_machine: true,
      endpoint_kind: "hosted",
    });

  it("keeps hosted accounts off the Local tab", async () => {
    stubFetch({
      "GET /api/models": models({
        profiles: [localProfile(), hostedProfile()],
        chat_profiles: [localProfile(), hostedProfile()],
      }),
      "GET /api/model-library": { roots: [], models: [] },
    });
    render(ModelsView, { tab: "local" });

    expect(await screen.findByText("On this device")).toBeInTheDocument();
    // Building a local model lives here: install a runtime, pull, and index.
    expect(screen.getByText("Install, connect, or pull")).toBeInTheDocument();
    expect(screen.queryByText("Your hosted providers")).not.toBeInTheDocument();
    expect(screen.queryByText("Advanced connections")).not.toBeInTheDocument();
  });

  it("keeps local runtimes and install actions off the Hosted tab", async () => {
    stubFetch({
      "GET /api/models": models({
        profiles: [localProfile(), hostedProfile()],
        chat_profiles: [localProfile(), hostedProfile()],
      }),
    });
    render(ModelsView, { tab: "hosted" });

    expect(await screen.findByText("Your hosted providers")).toBeInTheDocument();
    expect(screen.queryByText("On this device")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Install, connect, or pull"),
    ).not.toBeInTheDocument();
  });

  // Readiness and the global default describe the whole page, not one panel.
  // Reaching them used to mean navigating back to Providers first.
  it("shows readiness and the global default from every tab", async () => {
    stubFetch({
      "GET /api/models": models({
        profiles: [hostedProfile()],
        chat_profiles: [hostedProfile()],
        ready_provider_count: 0,
      }),
    });
    render(ModelsView, { tab: "pricing" });

    expect(await screen.findByText("0 models ready")).toBeInTheDocument();
    expect(
      screen.getByRole("combobox", { name: "Global model" }),
    ).toBeInTheDocument();
  });

  it("shows each provider's exact readiness state, not just its connection", async () => {
    const anthropic = profile({
      profile_id: "anthropic",
      provider: "anthropic",
      model: "opus",
      configured: true,
      connection_configured: true,
      ready: false,
      readiness_state: "quota_exhausted",
      readiness_summary:
        "Anthropic accepted the credential but the account has no credit or quota left.",
    });
    stubFetch({
      "GET /api/models": models({
        profiles: [anthropic],
        chat_profiles: [anthropic],
        ready_provider_count: 0,
      }),
    });
    render(ModelsView);

    expect(await screen.findByText("No credit")).toBeInTheDocument();
  });

  // A "selected" chip on the provider card read as "only this provider is
  // selected", i.e. that the others had been turned off. They had not — every
  // configured provider stays usable, and a per-chat picker can still choose
  // one. The row keeps its highlight; the misleading label is gone.
  it("does not label a provider as selected", async () => {
    const anthropic = profile({
      profile_id: "anthropic",
      provider: "anthropic",
      model: "opus",
      configured: true,
    });
    const ollama = profile({
      profile_id: "ollama",
      provider: "ollama",
      model: "gemma4:31b-cloud",
      configured: true,
      selected: true,
    });
    stubFetch({
      "GET /api/models": models({
        profiles: [anthropic, ollama],
        chat_profiles: [anthropic, ollama],
        current_profile_id: "ollama",
        current_model: "gemma4:31b-cloud",
      }),
    });
    render(ModelsView);
    await screen.findByRole("combobox", { name: "Global model" });
    expect(screen.queryByText("selected")).not.toBeInTheDocument();
  });

  it("shows the discovered local context capacity and its source", async () => {
    stubFetch({
      "GET /api/models": models({
        profiles: [
          profile({
            profile_id: "raiker-local-llama-cpp",
            selected: true,
            context_window_tokens: 32768,
            context_window_source: "provider",
          }),
        ],
      }),
    });
    render(ModelsView);
    await fireEvent.click(
      await screen.findByRole("button", { name: "Details" }),
    );
    expect(
      screen.getByText(/32,768 tokens · Reported by the provider runtime/),
    ).toBeInTheDocument();
  });

  it("shows a route-level loading state while model truth is fetched", async () => {
    stubFetchPending();
    render(ModelsView);
    const statuses = await screen.findAllByRole("status");
    expect(
      statuses.some((el) => /loading models/i.test(el.textContent ?? "")),
    ).toBe(true);
  });

  it("shows a route-level error state when model truth cannot load", async () => {
    stubFetch({});
    render(ModelsView);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/couldn't load models/i);
    expect(alert).toHaveTextContent(/unavailable \(404\)/i);
  });

  it("does not describe an API-key provider as having no API cost", async () => {
    stubFetch({
      "GET /api/models": models({
        profiles: [
          profile({
            profile_id: "anthropic-hosted",
            provider: "anthropic",
            local_only: false,
            requires_network: true,
            endpoint_kind: "remote_hosted",
            off_machine: true,
            billable: true,
          }),
        ],
      }),
    });
    render(ModelsView, { tab: "hosted" });

    // BUG-208 slice E — a provider with no turns has no cost to report, so the
    // usage strip is not rendered at all. What must never happen is the opposite
    // claim, and that is what this test was really guarding.
    await screen.findByRole("heading", { name: "Anthropic" });
    expect(screen.queryByText("No API cost — runs on this machine")).toBeNull();
    expect(screen.queryByText("Not used yet")).toBeNull();
  });
});

// The Models page is split by action category: Local, Hosted, Hugging Face,
// Activity, Routing, Pricing, and Posture. Tests that exercise the fallback
// sequence or the advisor render the Routing tab; a hosted or advanced profile
// renders the Hosted tab; everything else stays on the default Local tab.
describe("ModelsView routing, selection, and provider catalogue", () => {
  it("renders the persisted sequence in order", async () => {
    stubFetch({
      "GET /api/models": models({
        fallback_sequence: ["anthropic-hosted", "raiker-local-llama-cpp"],
      }),
    });
    render(ModelsView, { props: { tab: "routing" } });
    await waitFor(() =>
      expect(screen.getByText("Model fallback sequence")).toBeTruthy(),
    );
    const list = screen.getByRole("list");
    expect(list.textContent).toContain("Anthropic");
    expect(list.textContent).toContain("llama.cpp");
    expect(list.textContent).not.toContain("anthropic-hosted");
  });

  it("shows a cache chip for a profile with prompt caching enabled", async () => {
    stubFetch({
      "GET /api/models": models({
        profiles: [
          profile({
            profile_id: "anthropic-hosted",
            provider: "anthropic",
            prompt_cache_ttl: "5m",
          }),
        ],
      }),
    });
    render(ModelsView);
    await waitFor(() => expect(screen.getByText("Cache 5m")).toBeTruthy());
  });

  it("sends the optional usage admin key separately from the inference key", async () => {
    const anthropic = profile({
      profile_id: "anthropic-hosted",
      provider: "anthropic",
      local_only: false,
      requires_network: true,
      endpoint_kind: "remote_hosted",
      off_machine: true,
      connection_configured: false,
    });
    const mock = stubFetch({
      "GET /api/models": models({ profiles: [anthropic] }),
      "PUT /api/models/anthropic-hosted/connection": {
        ok: true,
        connection_configured: true,
      },
    });
    render(ModelsView, { props: { tab: "hosted" } });

    await fireEvent.click(await screen.findByRole("button", { name: "Connect" }));
    await fireEvent.input(screen.getByLabelText("Anthropic API key"), {
      target: { value: "inference-key" },
    });
    await fireEvent.input(
      screen.getByLabelText(/Organization usage admin key/),
      { target: { value: "usage-admin-key" } },
    );
    await fireEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: "Connect" }),
    );

    await waitFor(() =>
      expect(mock).toHaveBeenCalledWith(
        "/api/models/anthropic-hosted/connection",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({
            endpoint: null,
            api_key: "inference-key",
            admin_api_key: "usage-admin-key",
          }),
        }),
      ),
    );
  });

  it("shows the empty state when no fallback is configured", async () => {
    stubFetch({ "GET /api/models": models({ fallback_sequence: [] }) });
    render(ModelsView, { props: { tab: "routing" } });
    await waitFor(() =>
      expect(screen.getByText(/No fallback configured/)).toBeTruthy(),
    );
  });

  it("adds a backend and PUTs the sequence", async () => {
    const mock = stubFetch({
      "GET /api/models": models({ fallback_sequence: [] }),
      "PUT /api/model-fallback": {
        ok: true,
        fallback_sequence: ["raiker-local-llama-cpp"],
      },
    });
    render(ModelsView, { props: { tab: "routing" } });
    await waitFor(() =>
      expect(screen.getByText("Model fallback sequence")).toBeTruthy(),
    );

    const select = screen.getByLabelText(
      "Add a fallback backend",
    ) as HTMLSelectElement;
    await fireEvent.change(select, {
      target: { value: "raiker-local-llama-cpp" },
    });
    await fireEvent.click(screen.getByText("Add"));
    await fireEvent.click(screen.getByText("Save sequence"));

    await waitFor(() => {
      const put = mock.mock.calls.find(
        (c) => (c[1]?.method ?? "GET").toUpperCase() === "PUT",
      );
      expect(put).toBeTruthy();
      expect(JSON.parse(put![1]!.body as string)).toEqual({
        profile_ids: ["raiker-local-llama-cpp"],
      });
    });
  });

  it("selects a concrete-model profile directly via PUT /api/model-selection", async () => {
    const mock = stubFetch({
      "GET /api/models": models({}),
      "PUT /api/model-selection": {
        ok: true,
        profile_id: "raiker-local-llama-cpp",
        model: "local-gguf",
      },
    });
    render(ModelsView);
    const llamaRow = await screen.findByRole("group", { name: "llama.cpp GGUF" });
    await fireEvent.click(within(llamaRow).getByText("Select"));

    await waitFor(() => {
      const put = mock.mock.calls.find(
        (c) =>
          (c[1]?.method ?? "GET").toUpperCase() === "PUT" &&
          String(c[0]).includes("/api/model-selection"),
      );
      expect(put).toBeTruthy();
      expect(JSON.parse(put![1]!.body as string)).toEqual({
        profile_id: "raiker-local-llama-cpp",
        model: null,
      });
    });
  });

  it("notifies onchanged after a successful selection so the shell can refresh", async () => {
    stubFetch({
      "GET /api/models": models({}),
      "PUT /api/model-selection": {
        ok: true,
        profile_id: "raiker-local-llama-cpp",
        model: "local-gguf",
      },
    });
    const onchanged = vi.fn();
    render(ModelsView, { props: { onchanged } });
    await waitFor(() =>
      expect(screen.getAllByText("Select").length).toBeGreaterThan(0),
    );

    await fireEvent.click(screen.getAllByText("Select")[0]);

    await waitFor(() => expect(onchanged).toHaveBeenCalled());
  });

  // BUG-69 — "Test" listed the catalogue and reported "Anthropic responded and
  // exposed 10 models", which reads as "this works". It proved nothing about
  // the pinned model and wrote no readiness observation, so every surface
  // stayed blocked while the page said success. The obvious control has to be
  // the authoritative one.
  it("runs the exact-model readiness check from the provider card's Test action", async () => {
    const anthropic = profile({
      profile_id: "anthropic-hosted",
      provider: "anthropic",
      model: "claude-haiku-4-5-20251001",
      configured: true,
      connection_configured: true,
      ready: false,
    });
    const mock = stubFetch({
      "GET /api/models": models({
        profiles: [anthropic],
        chat_profiles: [anthropic],
        ready_provider_count: 0,
      }),
      "POST /api/model-readiness/check": {
        state: "quota_exhausted",
        ready: false,
        reason_code: "provider_quota_exhausted",
        summary:
          "Anthropic accepted the credential but the account has no credit or quota left.",
        remediation: "Add credit or raise the quota, then check again.",
      },
    });
    render(ModelsView);
    await waitFor(() => expect(screen.getByText("Test")).toBeTruthy());

    await fireEvent.click(screen.getByText("Test"));

    await waitFor(() => {
      const post = mock.mock.calls.find(
        (c) =>
          (c[1]?.method ?? "GET").toUpperCase() === "POST" &&
          String(c[0]).includes("/api/model-readiness/check"),
      );
      expect(post).toBeTruthy();
      expect(JSON.parse(post![1]!.body as string)).toEqual({
        profile_id: "anthropic-hosted",
        model: "claude-haiku-4-5-20251001",
      });
    });
    // The verdict and its repair, not "responded and exposed 10 models".
    expect(
      await screen.findByText(
        "Anthropic accepted the credential but the account has no credit or quota left. Add credit or raise the quota, then check again.",
      ),
    ).toBeInTheDocument();
  });

  it("lets the owner remove a connected provider credential", async () => {
    const anthropic = profile({
      profile_id: "anthropic-hosted",
      provider: "anthropic",
      model: "claude-haiku-4-5-20251001",
      configured: true,
      connection_configured: true,
      local_only: false,
      requires_network: true,
      off_machine: true,
      endpoint_kind: "hosted",
    });
    const mock = stubFetch({
      "GET /api/models": models({
        profiles: [anthropic],
        chat_profiles: [anthropic],
      }),
      "PUT /api/models/anthropic-hosted/connection": {
        ok: true,
        connection_configured: false,
      },
    });
    vi.stubGlobal("confirm", vi.fn(() => true));
    render(ModelsView, { props: { tab: "hosted" } });

    // BUG-208 slice E moved credential management into Details: it is not the
    // thing an owner came to the card to do, and the card had five controls.
    await fireEvent.click(await screen.findByRole("button", { name: "Details" }));
    await fireEvent.click(await screen.findByRole("button", { name: "Disconnect Anthropic" }));

    await waitFor(() =>
      expect(mock).toHaveBeenCalledWith(
        "/api/models/anthropic-hosted/connection",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({ endpoint: null, api_key: null, admin_api_key: null }),
        }),
      ),
    );
  });

  it("lists the provider's models on demand and selects one", async () => {
    const mock = stubFetch({
      "GET /api/models": models({
        profiles: [
          profile({
            profile_id: "ollama-local-openai-compatible",
            provider: "ollama",
            model: "<model>",
          }),
        ],
      }),
      "GET /api/models/ollama-local-openai-compatible/provider-models": {
        profile_id: "ollama-local-openai-compatible",
        provider: "ollama",
        status: "available",
        reason_code: null,
        models: ["qwen2.5", "llama3.2"],
      },
      "PUT /api/model-selection": {
        ok: true,
        profile_id: "ollama-local-openai-compatible",
        model: "qwen2.5",
      },
    });
    render(ModelsView);
    await waitFor(() => expect(screen.getByText("Choose model…")).toBeTruthy());

    await fireEvent.click(screen.getByText("Choose model…"));
    await waitFor(() =>
      expect(screen.getByLabelText("Available models")).toBeTruthy(),
    );

    const select = screen.getByLabelText(
      "Available models",
    ) as HTMLSelectElement;
    expect(select.textContent).toContain("Qwen 2.5");
    expect(select.textContent).toContain("Llama 3.2");
    await fireEvent.change(select, { target: { value: "qwen2.5" } });
    await fireEvent.click(screen.getByText("Use model"));

    await waitFor(() => {
      const put = mock.mock.calls.find(
        (c) =>
          (c[1]?.method ?? "GET").toUpperCase() === "PUT" &&
          String(c[0]).includes("/api/model-selection"),
      );
      expect(put).toBeTruthy();
      expect(JSON.parse(put![1]!.body as string)).toEqual({
        profile_id: "ollama-local-openai-compatible",
        model: "qwen2.5",
      });
    });
  });

  it("renders a provider catalogue with duplicate model ids once", async () => {
    stubFetch({
      "GET /api/models": models({
        profiles: [
          profile({
            profile_id: "openrouter-policy-gated",
            provider: "openrouter",
            model: "<model>",
            off_machine: true,
          }),
        ],
      }),
      "GET /api/models/openrouter-policy-gated/provider-models": {
        profile_id: "openrouter-policy-gated",
        provider: "openrouter",
        status: "available",
        reason_code: null,
        models: [
          "openai/gpt-4o-mini",
          "openai/gpt-4o-mini",
          "meta-llama/llama-3.1-8b-instruct",
        ],
      },
    });
    render(ModelsView, { tab: "hosted" });
    const chooseModel = await screen.findByRole("button", {
      name: /choose model/i,
    });
    await fireEvent.click(chooseModel);
    const select = (await screen.findByLabelText(
      "Available models",
    )) as HTMLSelectElement;
    expect(
      Array.from(select.options).filter(
        (option) => option.value === "openai/gpt-4o-mini",
      ),
    ).toHaveLength(1);
    expect(select.textContent).toContain("Llama 3.1 8B Instruct");
  });

  it("falls back to manual model entry when the provider list is unavailable", async () => {
    stubFetch({
      "GET /api/models": models({
        profiles: [
          profile({
            profile_id: "openai-hosted",
            provider: "openai",
            model: "<model>",
            off_machine: true,
          }),
        ],
      }),
      "GET /api/models/openai-hosted/provider-models": {
        profile_id: "openai-hosted",
        provider: "openai",
        status: "policy_denied",
        reason_code: "provider_requires_explicit_policy_approval",
        models: [],
      },
    });
    render(ModelsView);
    await waitFor(() => expect(screen.getByText("Choose model…")).toBeTruthy());

    await fireEvent.click(screen.getByText("Choose model…"));
    await waitFor(() =>
      expect(screen.getByText(/denied by provider policy/i)).toBeTruthy(),
    );
    expect(screen.getByLabelText("Custom model name")).toBeTruthy();
  });

  it("saves the advisor model via PUT /api/model-advisor", async () => {
    const mock = stubFetch({
      "GET /api/models": models({}),
      "PUT /api/model-advisor": {
        ok: true,
        advisor_profile_id: "anthropic-hosted",
      },
    });
    render(ModelsView, { props: { tab: "routing" } });
    await waitFor(() => expect(screen.getByText("Advisor model")).toBeTruthy());

    const select = screen.getByLabelText(
      "Advisor model profile",
    ) as HTMLSelectElement;
    // Only concrete-model profiles are offered as advisors.
    expect(select.textContent).toContain("Anthropic");
    await fireEvent.change(select, { target: { value: "anthropic-hosted" } });
    await fireEvent.click(screen.getByText("Save advisor"));

    await waitFor(() => {
      const put = mock.mock.calls.find(
        (c) =>
          (c[1]?.method ?? "GET").toUpperCase() === "PUT" &&
          String(c[0]).includes("/api/model-advisor"),
      );
      expect(put).toBeTruthy();
      expect(JSON.parse(put![1]!.body as string)).toEqual({
        profile_id: "anthropic-hosted",
      });
    });
  });

  it("clears the advisor by saving 'No advisor'", async () => {
    const mock = stubFetch({
      "GET /api/models": models({ advisor_profile_id: "anthropic-hosted" }),
      "PUT /api/model-advisor": { ok: true, advisor_profile_id: null },
    });
    render(ModelsView, { props: { tab: "routing" } });
    await waitFor(() => expect(screen.getByText("Advisor model")).toBeTruthy());

    const select = screen.getByLabelText(
      "Advisor model profile",
    ) as HTMLSelectElement;
    expect(select.value).toBe("anthropic-hosted");
    await fireEvent.change(select, { target: { value: "" } });
    await fireEvent.click(screen.getByText("Save advisor"));

    await waitFor(() => {
      const put = mock.mock.calls.find(
        (c) =>
          (c[1]?.method ?? "GET").toUpperCase() === "PUT" &&
          String(c[0]).includes("/api/model-advisor"),
      );
      expect(put).toBeTruthy();
      expect(JSON.parse(put![1]!.body as string)).toEqual({ profile_id: null });
    });
  });

  it("does not offer placeholder-model profiles as advisors", async () => {
    stubFetch({
      "GET /api/models": models({
        profiles: [
          profile({ profile_id: "anthropic-hosted", provider: "anthropic" }),
          profile({
            profile_id: "ollama-local-openai-compatible",
            provider: "ollama",
            model: "<model>",
          }),
        ],
      }),
    });
    render(ModelsView, { props: { tab: "routing" } });
    await waitFor(() => expect(screen.getByText("Advisor model")).toBeTruthy());
    const select = screen.getByLabelText(
      "Advisor model profile",
    ) as HTMLSelectElement;
    expect(select.textContent).toContain("Anthropic");
    expect(select.textContent).not.toContain("Ollama");
  });

  it("surfaces a server rejection reason", async () => {
    const mock = vi.fn(
      async (_input: RequestInfo | URL, init?: RequestInit) => {
        const method = (init?.method ?? "GET").toUpperCase();
        if (method === "PUT") {
          return {
            ok: false,
            status: 403,
            json: async () => ({
              detail: { reason_code: "not_authorized_gate_manager" },
            }),
          } as Response;
        }
        return {
          ok: true,
          status: 200,
          json: async () =>
            models({ fallback_sequence: ["raiker-local-llama-cpp"] }),
        } as Response;
      },
    );
    vi.stubGlobal("fetch", mock);

    render(ModelsView, { props: { tab: "routing" } });
    await waitFor(() =>
      expect(screen.getByText("Model fallback sequence")).toBeTruthy(),
    );
    // Reorder to make the form dirty, then save.
    await fireEvent.click(screen.getByLabelText("Remove"));
    await fireEvent.click(screen.getByText("Save sequence"));
    await waitFor(() =>
      expect(screen.getByText(/not_authorized_gate_manager/)).toBeTruthy(),
    );
  });
});

describe("ModelsView action-category tabs", () => {
  it("offers one tab per action category", async () => {
    stubFetch({ "GET /api/models": models({}) });
    render(ModelsView);
    const strip = await screen.findByRole("tablist", {
      name: "Model settings",
    });
    expect(
      within(strip)
        .getAllByRole("tab")
        .map((tab) => tab.textContent?.trim()),
    ).toEqual([
      "Local",
      "Hosted",
      "Hugging Face",
      "Activity",
      "Routing",
      "Pricing",
      "Posture",
    ]);
  });

  it("shows only the selected category, so one errand is one screen", async () => {
    stubFetch({ "GET /api/models": models({}) });
    render(ModelsView);
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Global model" }),
      ).toBeTruthy(),
    );
    // Pricing and the fallback list belong to other tabs and must not be here.
    expect(screen.queryByText("Model fallback sequence")).toBeNull();
    expect(screen.queryByRole("heading", { name: "Pricing" })).toBeNull();
    expect(screen.queryByText("Off-machine provider posture")).toBeNull();
  });

  it("puts Pricing on its own tab", async () => {
    stubFetch({
      "GET /api/models": models({}),
      "GET /api/models/pricing": { entries: [], sync: [], can_override: false },
    });
    render(ModelsView, { props: { tab: "pricing" } });
    expect(
      await screen.findByRole("heading", { name: "Pricing" }),
    ).toBeInTheDocument();
    // Provider cards belong to Local and Hosted. The readiness summary and the
    // global default are page-level on purpose and stay visible here.
    expect(screen.queryByText("On this device")).toBeNull();
    expect(screen.queryByText("Your hosted providers")).toBeNull();
  });

  it("puts the read-only posture on its own tab", async () => {
    stubFetch({ "GET /api/models": models({}) });
    render(ModelsView, { props: { tab: "posture" } });
    expect(
      await screen.findByText("Off-machine provider posture"),
    ).toBeInTheDocument();
    expect(screen.queryByText("On this device")).toBeNull();
    expect(screen.queryByText("Your hosted providers")).toBeNull();
  });

  it("marks the selected tab and links each panel back to it", async () => {
    stubFetch({ "GET /api/models": models({}) });
    render(ModelsView, { props: { tab: "routing" } });
    await waitFor(() =>
      expect(screen.getByText("Model fallback sequence")).toBeTruthy(),
    );
    expect(screen.getByRole("tab", { name: "Routing" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tabpanel")).toHaveAttribute(
      "aria-labelledby",
      "tab-routing",
    );
  });

  it("selecting a tab writes it into the hash, so a panel is shareable", async () => {
    stubFetch({ "GET /api/models": models({}) });
    render(ModelsView);
    await fireEvent.click(await screen.findByRole("tab", { name: "Pricing" }));
    expect(window.location.hash).toBe("#/models?tab=pricing");
    expect(screen.getByRole("tab", { name: "Pricing" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(await screen.findByRole("tabpanel")).toHaveAttribute(
      "aria-labelledby",
      "tab-pricing",
    );
  });
});

// BUG-47 — a provider test answers for the provider that ran it and no other.
// The reported defect was Ollama's *"responded and exposed 9 models"* appearing
// beneath the Anthropic and OpenRouter cards: the view held one result string
// for every card, and the local row that started the test had nowhere to show
// it at all. Two connected providers, one test, one message, in the right place.
describe("ModelsView provider test feedback", () => {
  // BUG-47 — every test result names the provider it came from and attaches to
  // the card whose Test produced it. Two local runtimes prove attribution
  // between sibling cards; the cross-layout leak that first exposed this (a
  // local result surfacing under the hosted cards) is now structurally
  // impossible, because local and hosted are different tabs.
  const ollama = () =>
    profile({
      profile_id: "ollama-local-openai-compatible",
      provider: "ollama",
      model: "gemma4:31b-cloud",
      connection_configured: true,
    });
  const llamaCpp = () =>
    profile({
      profile_id: "raiker-local-llama-cpp",
      provider: "llama.cpp",
      model: "local-gguf",
      connection_configured: true,
    });
  const anthropic = () =>
    profile({
      profile_id: "anthropic-hosted",
      provider: "anthropic",
      model: "claude-haiku-4-5-20251001",
      requires_network: true,
      off_machine: true,
      local_only: false,
      endpoint_kind: "hosted",
      connection_configured: true,
    });
  const openrouter = () =>
    profile({
      profile_id: "openrouter-policy-gated",
      provider: "openrouter",
      model: "openai/gpt-4o-mini",
      requires_network: true,
      off_machine: true,
      local_only: false,
      endpoint_kind: "hosted",
      connection_configured: true,
    });

  it("shows one provider's result only under that provider", async () => {
    stubFetch({
      "GET /api/models": models({ profiles: [ollama(), llamaCpp()] }),
      "GET /api/model-library": { roots: [], models: [] },
      "POST /api/model-readiness/check": {
        state: "ready",
        ready: true,
        reason_code: "model_ready",
        summary: "Ollama can reach gemma4:31b-cloud.",
        remediation: "",
      },
    });
    render(ModelsView, { tab: "local" });

    const tests = await screen.findAllByRole("button", { name: "Test" });
    expect(tests).toHaveLength(2);
    await fireEvent.click(tests[0]);

    const message = "Ollama can reach gemma4:31b-cloud.";
    await waitFor(() => expect(screen.getAllByText(message)).toHaveLength(1));
    const result = screen.getByText(message);
    expect(result).toHaveAttribute(
      "data-test-result",
      "ollama-local-openai-compatible",
    );
    const row = result.closest(".local-row");
    expect(row).not.toBeNull();
    // The sibling runtime's row is untouched.
    const rows = Array.from(document.querySelectorAll(".local-row"));
    expect(rows).toHaveLength(2);
    expect(
      within(rows.find((node) => node !== row) as HTMLElement).queryByText(
        message,
      ),
    ).toBeNull();
  });

  it("keeps each provider's result independent when both are tested", async () => {
    stubFetch({
      "GET /api/models": models({ profiles: [anthropic(), openrouter()] }),
      "POST /api/model-readiness/check": {
        state: "ready",
        ready: true,
        reason_code: "model_ready",
        summary: "The exact model is reachable.",
        remediation: "",
      },
    });
    render(ModelsView, { tab: "hosted" });

    const tests = await screen.findAllByRole("button", { name: "Test" });
    await fireEvent.click(tests[0]);
    await waitFor(() =>
      expect(screen.getAllByText("The exact model is reachable.")).toHaveLength(
        1,
      ),
    );
    await fireEvent.click(screen.getAllByRole("button", { name: "Test" })[1]);

    // Testing the second provider does not overwrite the first: two results
    // stand, each attributed to the card whose Test produced it.
    await waitFor(() =>
      expect(screen.getAllByText("The exact model is reachable.")).toHaveLength(
        2,
      ),
    );
    expect(
      screen
        .getAllByText("The exact model is reachable.")
        .map((node) => node.getAttribute("data-test-result"))
        .sort(),
    ).toEqual(["anthropic-hosted", "openrouter-policy-gated"]);
  });

  it("names the provider it could not reach, so a failure is attributable too", async () => {
    stubFetch({
      "GET /api/models": models({ profiles: [anthropic(), openrouter()] }),
    });
    render(ModelsView, { tab: "hosted" });

    const tests = await screen.findAllByRole("button", { name: "Test" });
    await fireEvent.click(tests[0]);
    await waitFor(() =>
      expect(
        screen.getByText("Raiker could not check Anthropic."),
      ).toBeTruthy(),
    );
    expect(screen.queryByText("Raiker could not check OpenRouter.")).toBeNull();
  });

  it("names the provider in an unreachable answer, not only in a successful one", async () => {
    // An anonymous "Provider unreachable" is what let a misplaced result go
    // unnoticed: nothing in the sentence contradicted the card above it.
    stubFetch({
      "GET /api/models": models({ profiles: [ollama(), llamaCpp()] }),
      "GET /api/model-library": { roots: [], models: [] },
      "POST /api/model-readiness/check": {
        state: "runtime_stopped",
        ready: false,
        reason_code: "local_runtime_unreachable",
        summary: "Ollama is not reachable.",
        remediation: "Start or reconnect Ollama, then check again.",
      },
    });
    render(ModelsView, { tab: "local" });

    await fireEvent.click(
      (await screen.findAllByRole("button", { name: "Test" }))[0],
    );
    const result = await screen.findByText(/^Ollama is not reachable\./);
    expect(result).toHaveAttribute(
      "data-test-result",
      "ollama-local-openai-compatible",
    );
    expect(result.closest(".local-row")).not.toBeNull();
  });
});
