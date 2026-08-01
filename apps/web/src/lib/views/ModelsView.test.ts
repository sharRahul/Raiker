// Coverage for the Models view: its action-category tabs (Providers, Routing,
// Pricing, Posture), provider selection and catalogue, and the fallback-sequence
// and advisor editors on the Routing tab. The read is the single GET
// /api/models; writes go to PUT /api/model-fallback, /api/model-selection, and
// /api/model-advisor (human gate-manager only, enforced server-side).
import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
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
      profile({ profile_id: "anthropic-hosted", provider: "anthropic", off_machine: true }),
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
  it("sets the global default from every configured provider/model pair", async () => {
    const anthropic = profile({ profile_id: "anthropic", provider: "anthropic", model: "opus", configured: true });
    const ollama = profile({ profile_id: "ollama", provider: "ollama", model: "gemma4:31b-cloud", configured: true, selected: true });
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

    const select = await screen.findByRole("combobox", { name: "Global model" });
    expect(select).toHaveValue('["ollama","gemma4:31b-cloud"]');
    await fireEvent.change(select, { target: { value: '["anthropic","opus"]' } });

    await waitFor(() => expect(mock).toHaveBeenCalledWith(
      "/api/model-selection",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ profile_id: "anthropic", model: "opus" }),
      }),
    ));
  });

  it("shows the discovered local context capacity and its source", async () => {
    stubFetch({
      "GET /api/models": models({
        profiles: [profile({
          profile_id: "raiker-local-llama-cpp",
          selected: true,
          context_window_tokens: 32768,
          context_window_source: "provider",
        })],
      }),
    });
    render(ModelsView);
    await fireEvent.click(await screen.findByRole("button", { name: "Details" }));
    expect(screen.getByText(/32,768 tokens · Reported by the provider runtime/)).toBeInTheDocument();
  });

  it("shows a route-level loading state while model truth is fetched", async () => {
    stubFetchPending();
    render(ModelsView);
    const statuses = await screen.findAllByRole("status");
    expect(statuses.some((el) => /loading models/i.test(el.textContent ?? ""))).toBe(true);
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
    render(ModelsView);

    expect(await screen.findByText("Not used yet")).toBeTruthy();
    expect(screen.queryByText("No API cost — runs on this machine")).toBeNull();
  });
});

// The Models page is split by action category: Providers, Routing, Pricing,
// and Posture. Tests that exercise the fallback sequence or the advisor render
// the Routing tab; everything else stays on the default Providers tab.
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
          profile({ profile_id: "anthropic-hosted", provider: "anthropic", prompt_cache_ttl: "5m" }),
        ],
      }),
    });
    render(ModelsView);
    await waitFor(() => expect(screen.getByText("Cache 5m")).toBeTruthy());
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
      "PUT /api/model-fallback": { ok: true, fallback_sequence: ["raiker-local-llama-cpp"] },
    });
    render(ModelsView, { props: { tab: "routing" } });
    await waitFor(() => expect(screen.getByText("Model fallback sequence")).toBeTruthy());

    const select = screen.getByLabelText("Add a fallback backend") as HTMLSelectElement;
    await fireEvent.change(select, { target: { value: "raiker-local-llama-cpp" } });
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
    await waitFor(() => expect(screen.getAllByText("Select").length).toBeGreaterThan(0));

    await fireEvent.click(screen.getAllByText("Select")[0]);

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
    await waitFor(() => expect(screen.getAllByText("Select").length).toBeGreaterThan(0));

    await fireEvent.click(screen.getAllByText("Select")[0]);

    await waitFor(() => expect(onchanged).toHaveBeenCalled());
  });

  it("lists the provider's models on demand and selects one", async () => {
    const mock = stubFetch({
      "GET /api/models": models({
        profiles: [
          profile({ profile_id: "ollama-local-openai-compatible", provider: "ollama", model: "<model>" }),
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
    await waitFor(() => expect(screen.getByLabelText("Available models")).toBeTruthy());

    const select = screen.getByLabelText("Available models") as HTMLSelectElement;
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
          profile({ profile_id: "openrouter-policy-gated", provider: "openrouter", model: "<model>", off_machine: true }),
        ],
      }),
      "GET /api/models/openrouter-policy-gated/provider-models": {
        profile_id: "openrouter-policy-gated",
        provider: "openrouter",
        status: "available",
        reason_code: null,
        models: ["openai/gpt-4o-mini", "openai/gpt-4o-mini", "meta-llama/llama-3.1-8b-instruct"],
      },
    });
    render(ModelsView);
    const chooseModel = await screen.findByRole("button", { name: /choose model/i });
    await fireEvent.click(chooseModel);
    const select = await screen.findByLabelText("Available models") as HTMLSelectElement;
    expect(Array.from(select.options).filter((option) => option.value === "openai/gpt-4o-mini")).toHaveLength(1);
    expect(select.textContent).toContain("Llama 3.1 8B Instruct");
  });

  it("falls back to manual model entry when the provider list is unavailable", async () => {
    stubFetch({
      "GET /api/models": models({
        profiles: [
          profile({ profile_id: "openai-hosted", provider: "openai", model: "<model>", off_machine: true }),
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
      "PUT /api/model-advisor": { ok: true, advisor_profile_id: "anthropic-hosted" },
    });
    render(ModelsView, { props: { tab: "routing" } });
    await waitFor(() => expect(screen.getByText("Advisor model")).toBeTruthy());

    const select = screen.getByLabelText("Advisor model profile") as HTMLSelectElement;
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
      expect(JSON.parse(put![1]!.body as string)).toEqual({ profile_id: "anthropic-hosted" });
    });
  });

  it("clears the advisor by saving 'No advisor'", async () => {
    const mock = stubFetch({
      "GET /api/models": models({ advisor_profile_id: "anthropic-hosted" }),
      "PUT /api/model-advisor": { ok: true, advisor_profile_id: null },
    });
    render(ModelsView, { props: { tab: "routing" } });
    await waitFor(() => expect(screen.getByText("Advisor model")).toBeTruthy());

    const select = screen.getByLabelText("Advisor model profile") as HTMLSelectElement;
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
          profile({ profile_id: "ollama-local-openai-compatible", provider: "ollama", model: "<model>" }),
        ],
      }),
    });
    render(ModelsView, { props: { tab: "routing" } });
    await waitFor(() => expect(screen.getByText("Advisor model")).toBeTruthy());
    const select = screen.getByLabelText("Advisor model profile") as HTMLSelectElement;
    expect(select.textContent).toContain("Anthropic");
    expect(select.textContent).not.toContain("Ollama");
  });

  it("surfaces a server rejection reason", async () => {
    const mock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      const method = (init?.method ?? "GET").toUpperCase();
      if (method === "PUT") {
        return {
          ok: false,
          status: 403,
          json: async () => ({ detail: { reason_code: "not_authorized_gate_manager" } }),
        } as Response;
      }
      return {
        ok: true,
        status: 200,
        json: async () => models({ fallback_sequence: ["raiker-local-llama-cpp"] }),
      } as Response;
    });
    vi.stubGlobal("fetch", mock);

    render(ModelsView, { props: { tab: "routing" } });
    await waitFor(() => expect(screen.getByText("Model fallback sequence")).toBeTruthy());
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
    const strip = await screen.findByRole("tablist", { name: "Model settings" });
    expect(within(strip).getAllByRole("tab").map((tab) => tab.textContent?.trim())).toEqual([
      "Providers",
      "Routing",
      "Pricing",
      "Posture",
    ]);
  });

  it("shows only the selected category, so one errand is one screen", async () => {
    stubFetch({ "GET /api/models": models({}) });
    render(ModelsView);
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Global model" })).toBeTruthy(),
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
    expect(await screen.findByRole("heading", { name: "Pricing" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Global model" })).toBeNull();
  });

  it("puts the read-only posture on its own tab", async () => {
    stubFetch({ "GET /api/models": models({}) });
    render(ModelsView, { props: { tab: "posture" } });
    expect(await screen.findByText("Off-machine provider posture")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Global model" })).toBeNull();
  });

  it("marks the selected tab and links each panel back to it", async () => {
    stubFetch({ "GET /api/models": models({}) });
    render(ModelsView, { props: { tab: "routing" } });
    await waitFor(() => expect(screen.getByText("Model fallback sequence")).toBeTruthy());
    expect(screen.getByRole("tab", { name: "Routing" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveAttribute("aria-labelledby", "tab-routing");
  });

  it("selecting a tab writes it into the hash, so a panel is shareable", async () => {
    stubFetch({ "GET /api/models": models({}) });
    render(ModelsView);
    await fireEvent.click(await screen.findByRole("tab", { name: "Pricing" }));
    expect(window.location.hash).toBe("#/models?tab=pricing");
  });
});
