// Coverage for the Models view: its tabs (Overview, My models, Add model,
// Runtime & routing, Usage — MODEL-03), provider selection and catalogue, and
// the fallback-sequence and advisor editors on Runtime & routing. The read is the single GET
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

/**
 * Press a row action, wherever this row's state put it.
 *
 * MODEL-15 gives a repeated provider row one visible action and one overflow,
 * and *which* action is visible depends on the row: a provider with no model
 * named shows "Select models…" outright, while a connected one keeps it in the
 * menu beside Test connection and Details. Both are the same action to the
 * owner, so they are the same call here — a spec about what a provider row can
 * do should not also be a spec about which of the two places today's state puts
 * it in.
 *
 * `nth` picks among rows when a fixture has more than one provider.
 */
async function rowAction(label: string, nth = 0): Promise<void> {
  // The rows arrive with the first read, so wait for either shape before
  // deciding which one this row is in. Checking synchronously first would
  // always find nothing and always take the overflow path.
  const overflow = /^More actions for /;
  await waitFor(() => {
    const found =
      screen.queryAllByRole("button", { name: label }).length +
      screen.queryAllByRole("button", { name: overflow }).length;
    expect(found).toBeGreaterThan(nth);
  });
  const visible = screen.queryAllByRole("button", { name: label });
  if (visible.length > nth) {
    await fireEvent.click(visible[nth]);
    return;
  }
  await fireEvent.click(screen.getAllByRole("button", { name: overflow })[nth]);
  const menu = screen.getAllByRole("menu")[0];
  await fireEvent.click(within(menu).getByRole("menuitem", { name: label }));
}

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

describe("BUG-270 — a card never claims a runtime that is not here", () => {
  it("says a local runtime is not installed and offers to look again", async () => {
    const mock = stubFetch({
      "GET /api/models": models({
        profiles: [
          profile({
            profile_id: "ollama-local-openai-compatible",
            provider: "ollama",
            model: "gemma4:31b-cloud",
            configured: false,
            provider_detected: false,
          }),
        ],
        usable_provider_count: 0,
      }),
      "POST /api/local-runtimes/detect": { runtimes: [] },
    });
    render(ModelsView, { tab: "add" });

    // The line carries a warning icon and an inline action, so it is matched on
    // the element that holds all three rather than on a bare text node.
    expect(
      await screen.findByText(/Not installed on this machine/),
    ).toBeTruthy();
    await fireEvent.click(await screen.findByRole("button", { name: "Look again" }));
    await waitFor(() =>
      expect(mock).toHaveBeenCalledWith(
        "/api/local-runtimes/detect",
        expect.objectContaining({ method: "POST" }),
      ),
    );
  });

  it("offers to set the runtime up, not just to look again", async () => {
    // Reporting the absence was half an answer: the owner then had to find the
    // install panel further up the page and match its cards to the row that
    // told them.
    const mock = stubFetch({
      "GET /api/models": models({
        profiles: [
          profile({
            profile_id: "ollama-local-openai-compatible",
            provider: "ollama",
            model: "gemma4:31b-cloud",
            configured: false,
            provider_detected: false,
          }),
        ],
        usable_provider_count: 0,
      }),
      "POST /api/model-operations/preview": {
        runtime: "ollama",
        action: "download_official_installer",
        source_url: "https://ollama.com/download",
        argv: [],
        requires_elevation: false,
        terms_url: "https://github.com/ollama/ollama/blob/main/LICENSE",
        redistribution: false,
      },
    });
    const open = vi.fn();
    vi.stubGlobal("open", open);
    render(ModelsView, { tab: "add" });

    await fireEvent.click(await screen.findByRole("button", { name: "Set up Ollama" }));

    await waitFor(() =>
      expect(mock).toHaveBeenCalledWith(
        "/api/model-operations/preview",
        expect.objectContaining({ method: "POST" }),
      ),
    );
    // The vendor's own download, in a new tab, with the opener severed.
    await waitFor(() =>
      expect(open).toHaveBeenCalledWith(
        "https://ollama.com/download",
        "_blank",
        "noopener,noreferrer",
      ),
    );
    // Not "installed": Raiker opened a download, and whether it was run is the
    // owner's to say.
    expect(await screen.findByText(/Install it, then choose Look again/)).toBeTruthy();
  });

  it("refuses a plan that does not name an https source", async () => {
    stubFetch({
      "GET /api/models": models({
        profiles: [
          profile({
            profile_id: "ollama-local-openai-compatible",
            provider: "ollama",
            model: "gemma4:31b-cloud",
            configured: false,
            provider_detected: false,
          }),
        ],
      }),
      "POST /api/model-operations/preview": {
        runtime: "ollama",
        action: "download_official_installer",
        source_url: "http://ollama.com/download",
        argv: [],
        requires_elevation: false,
        terms_url: "",
        redistribution: false,
      },
    });
    const open = vi.fn();
    vi.stubGlobal("open", open);
    render(ModelsView, { tab: "add" });

    await fireEvent.click(await screen.findByRole("button", { name: "Set up Ollama" }));

    expect(await screen.findByText(/Could not open the Ollama download/)).toBeTruthy();
    expect(open).not.toHaveBeenCalled();
  });

  it("offers no setup for a runtime with no reviewed vendor source", async () => {
    // vLLM is a Python package and MLX ships with its own toolchain, so
    // Raiker has no reviewed vendor download for either. A button here would
    // be one that cannot work.
    stubFetch({
      "GET /api/models": models({
        profiles: [
          profile({
            profile_id: "vllm-local",
            provider: "vllm",
            model: "served-model",
            configured: false,
            provider_detected: false,
          }),
        ],
      }),
    });
    render(ModelsView, { tab: "add" });

    expect(await screen.findByText(/Not installed on this machine/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^Set up / })).toBeNull();
  });

  it("says nothing about a machine nothing has looked at", async () => {
    // `provider_detected` absent means either no detector ran or the profile
    // does not depend on a local runtime. Neither licenses claiming an absence.
    stubFetch({
      "GET /api/models": models({
        profiles: [
          profile({
            profile_id: "ollama-local-openai-compatible",
            provider: "ollama",
            model: "gemma4:31b-cloud",
          }),
        ],
      }),
    });
    render(ModelsView, { tab: "add" });

    await waitFor(() =>
      expect(screen.getAllByRole("heading", { name: "Ollama" }).length).toBeGreaterThan(0),
    );
    expect(screen.queryByText(/Not installed on this machine/)).toBeNull();
  });

  it("counts models set up from the server rather than from the model string", async () => {
    // Four empty llama.cpp slots carry `local-gguf…` aliases, which is what the
    // browser used to count. The server knows which of them serve anything.
    stubFetch({
      "GET /api/models": models({
        profiles: [
          profile({ profile_id: "raiker-local-llama-cpp", model: "local-gguf" }),
          profile({ profile_id: "raiker-local-llama-cpp-2", model: "local-gguf-2" }),
        ],
        usable_provider_count: 0,
        ready_provider_count: 0,
      }),
    });
    render(ModelsView, { tab: "add" });

    expect(await screen.findByText("No model ready")).toBeTruthy();
  });
});

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
    render(ModelsView, { tab: "add" });

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

  it("offers ChatGPT subscription sign-in in Models without an API-key dialog", async () => {
    const mock = stubFetch({
      "GET /api/models": models({
        profiles: [
          profile({
            profile_id: "chatgpt-codex-subscription",
            provider: "chatgpt-codex",
            model: "<model>",
            local_only: false,
            requires_network: true,
            endpoint_kind: "remote_hosted",
            off_machine: true,
          }),
        ],
      }),
      "GET /api/models/chatgpt-codex/status": { connection_status: "signed_out", plan_type: null },
      "POST /api/models/chatgpt-codex/login": { connection_status: "login_pending", plan_type: null },
    });
    render(ModelsView, { tab: "add" });

    await fireEvent.click(await screen.findByRole("button", { name: "Sign in with ChatGPT" }));
    await waitFor(() =>
      expect(mock).toHaveBeenCalledWith(
        "/api/models/chatgpt-codex/login",
        expect.objectContaining({ method: "POST" }),
      ),
    );
    expect(await screen.findByText(/Finish sign-in in the browser/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/API key/i)).not.toBeInTheDocument();
  });

  it("names the connected ChatGPT plan and keeps sign-in reachable", async () => {
    stubFetch({
      "GET /api/models": models({
        profiles: [
          profile({
            profile_id: "chatgpt-codex-subscription", provider: "chatgpt-codex", model: "<model>",
            local_only: false, requires_network: true, endpoint_kind: "remote_hosted", off_machine: true,
          }),
        ],
      }),
      "GET /api/models/chatgpt-codex/status": { connection_status: "connected", plan_type: "plus" },
    });
    render(ModelsView, { tab: "add" });

    expect(await screen.findByText("ChatGPT Plus connected")).toBeInTheDocument();
    expect(screen.queryByText("Connection saved")).not.toBeInTheDocument();
    // An owner with more than one ChatGPT plan must be able to move Raiker
    // between them, so neither control disappears once one is connected.
    expect(screen.getByRole("button", { name: "Switch account" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });

  it("says Codex is missing rather than reporting a failed status read", async () => {
    stubFetch({
      "GET /api/models": models({
        profiles: [
          profile({
            profile_id: "chatgpt-codex-subscription", provider: "chatgpt-codex", model: "<model>",
            local_only: false, requires_network: true, endpoint_kind: "remote_hosted", off_machine: true,
          }),
        ],
      }),
      "GET /api/models/chatgpt-codex/status": { connection_status: "codex_missing", plan_type: null },
    });
    render(ModelsView, { tab: "add" });

    expect(await screen.findByText(/Codex not installed/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in with ChatGPT" })).toBeInTheDocument();
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

    render(ModelsView, { tab: "runtime" });

    const gguf = await screen.findByRole("group", { name: "GGUF" });
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

    // A saved key is still not a proven model, so the line never says "ready".
    // It says what is true instead of zero, which on an instance with models
    // connected and selected read as "nothing here works".
    expect(await screen.findByText("1 model set up")).toBeInTheDocument();
    expect(screen.queryByText(/models? ready/)).not.toBeInTheDocument();
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

  // MODEL-03/MODEL-07 — Local and Hosted were peers because that is how the
  // profiles are stored, not because it is a choice anyone makes: an owner
  // arrives wanting *a model*, and where it runs is an attribute of the answer.
  // Both sections live under Add model, each keeping its own heading and its own
  // controls, so nothing was merged except the errand.
  it("gathers local and hosted under one add-a-model errand", async () => {
    stubFetch({
      "GET /api/models": models({
        profiles: [localProfile(), hostedProfile()],
        chat_profiles: [localProfile(), hostedProfile()],
      }),
      "GET /api/model-library": { roots: [], models: [] },
    });
    render(ModelsView, { tab: "add" });

    expect(await screen.findByText("On this device")).toBeInTheDocument();
    // Building a local model lives here: install a runtime, pull, and index.
    expect(screen.getByText("Install, connect, or pull")).toBeInTheDocument();
  });

  it("still separates hosted accounts from local runtimes by section", async () => {
    // One tab, two headings. The distinction that mattered — sign in to
    // somebody else's account, or run something here — is a section boundary
    // rather than a navigation choice made before you know which you want.
    stubFetch({
      "GET /api/models": models({
        profiles: [localProfile(), hostedProfile()],
        chat_profiles: [localProfile(), hostedProfile()],
      }),
    });
    render(ModelsView, { tab: "add" });

    expect(await screen.findByText("Your hosted providers")).toBeInTheDocument();
    expect(screen.getByText("On this device")).toBeInTheDocument();
  });

  // A card's model line is a fact about the owner's provider or it is nothing.
  //
  // Every hosted card with no model named printed "no model pinned" and every
  // local row "model chosen at selection" — on a fresh workspace that was eight
  // identical lines, the largest block of text on the page, and none of it about
  // the providers it sat on. "Not connected" and "Select models…" already say
  // that nothing has been chosen; the placeholder only taught Raiker's own
  // pinning vocabulary to somebody who had not asked to learn it.
  it("names a card's model when there is one, and says nothing when there is not", async () => {
    stubFetch({
      "GET /api/models": models({
        profiles: [hostedProfile(), profile({
          profile_id: "openai-hosted",
          provider: "openai",
          model: "<model>",
          local_only: false,
          requires_network: true,
          off_machine: true,
          endpoint_kind: "hosted",
        })],
        chat_profiles: [hostedProfile()],
      }),
    });
    render(ModelsView, { tab: "add" });

    expect(await screen.findByText("Your hosted providers")).toBeInTheDocument();
    expect(screen.queryByText(/no model pinned/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/model chosen at selection/i)).not.toBeInTheDocument();
    // The fact itself stays: a connected provider still says which model answers.
    expect(screen.getByText("Haiku 4.5")).toBeInTheDocument();
    // …and only the card that has one carries the line at all.
    expect(document.querySelectorAll(".pc-model")).toHaveLength(1);
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
    render(ModelsView, { tab: "usage" });

    // Hosted, with no credential saved: nothing here is set up either.
    expect(await screen.findByText("No model ready")).toBeInTheDocument();
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
    render(ModelsView, { tab: "add" });

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
    render(ModelsView, { tab: "add" });
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
    render(ModelsView, { tab: "runtime" });
    await fireEvent.click(await screen.findByRole("button", { name: "Details" }));
    expect(
      screen.getByText(/32,768 tokens · Reported by the provider runtime/),
    ).toBeInTheDocument();
  });

  it("shows a route-level loading state while model truth is fetched", async () => {
    stubFetchPending();
    render(ModelsView, { tab: "add" });
    const statuses = await screen.findAllByRole("status");
    expect(
      statuses.some((el) => /loading models/i.test(el.textContent ?? "")),
    ).toBe(true);
  });

  it("shows a route-level error state when model truth cannot load", async () => {
    stubFetch({});
    render(ModelsView, { tab: "add" });
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
    render(ModelsView, { tab: "add" });

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
    render(ModelsView, { props: { tab: "runtime" } });
    await waitFor(() =>
      expect(screen.getByText("Model fallback sequence")).toBeTruthy(),
    );
    const list = screen.getByRole("list");
    expect(list.textContent).toContain("Anthropic");
    expect(list.textContent).toContain("GGUF");
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
    render(ModelsView, { tab: "add" });
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
    render(ModelsView, { props: { tab: "add" } });

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
            workspace_id: null,
          }),
        }),
      ),
    );
  });

  it("shows the empty state when no fallback is configured", async () => {
    stubFetch({ "GET /api/models": models({ fallback_sequence: [] }) });
    render(ModelsView, { props: { tab: "runtime" } });
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
    render(ModelsView, { props: { tab: "runtime" } });
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
    render(ModelsView, { tab: "runtime" });
    const llamaRow = await screen.findByRole("group", { name: "GGUF" });
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
    render(ModelsView, { props: { onchanged, tab: "runtime" } });
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
    render(ModelsView, { tab: "add" });
    await rowAction("Test connection");

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

  // BUG-274 — an identity-linked key acts inside one workspace. The old answer
  // sent the owner to fetch a different key, which is a dead end for an owner
  // who has only this one. The connection now carries the workspace itself.
  describe("an identity-linked key", () => {
    const identityLinked = () =>
      profile({
        profile_id: "anthropic-hosted",
        provider: "anthropic",
        model: "claude-haiku-4-5-20251001",
        configured: true,
        local_only: false,
        requires_network: true,
        off_machine: true,
        endpoint_kind: "hosted",
      });

    it("sends the workspace alongside the key", async () => {
      const mock = stubFetch({
        "GET /api/models": models({
          profiles: [identityLinked()],
          chat_profiles: [identityLinked()],
        }),
        "PUT /api/models/anthropic-hosted/connection": {
          ok: true,
          connection_configured: true,
        },
      });
      render(ModelsView, { props: { tab: "add" } });

      await fireEvent.click(await screen.findByRole("button", { name: "Connect" }));
      await fireEvent.input(screen.getByLabelText(/API key/i), {
        target: { value: "sk-ant-test" },
      });
      // Behind Advanced: most keys need nothing here, and a box asking for a
      // "workspace ID" on the default view is a question most owners cannot
      // answer.
      await fireEvent.click(screen.getByRole("button", { name: "Advanced" }));
      await fireEvent.input(screen.getByLabelText(/Workspace ID/i), {
        target: { value: "wrkspc_01" },
      });
      await fireEvent.click(document.querySelector(".signin-connect") as HTMLElement);

      await waitFor(() =>
        expect(mock).toHaveBeenCalledWith(
          "/api/models/anthropic-hosted/connection",
          expect.objectContaining({
            method: "PUT",
            body: JSON.stringify({
              endpoint: null,
              api_key: "sk-ant-test",
              admin_api_key: null,
              workspace_id: "wrkspc_01",
            }),
          }),
        ),
      );
    });

    // Found while proving BUG-274 against a live provider: Reconnect is reached
    // through Details, and saving left that modal over the card it had just
    // changed, so the next click hit an overlay.
    it("closes Model details after saving from Reconnect", async () => {
      const connected = profile({ ...identityLinked(), connection_configured: true });
      stubFetch({
        "GET /api/models": models({ profiles: [connected], chat_profiles: [connected] }),
        "PUT /api/models/anthropic-hosted/connection": {
          ok: true,
          connection_configured: true,
        },
      });
      render(ModelsView, { props: { tab: "add" } });

      await rowAction("Details");
      await fireEvent.click(await screen.findByRole("button", { name: "Reconnect" }));
      await fireEvent.input(screen.getByLabelText(/API key/i), {
        target: { value: "sk-ant-test" },
      });
      await fireEvent.click(document.querySelector(".signin-connect") as HTMLElement);

      await waitFor(() =>
        expect(screen.queryByRole("button", { name: "Close model details" })).toBeNull(),
      );
    });

    // Found by the live run against a real identity-linked key: **Test** has
    // two paths, and on a fresh connection with no model pinned it reads the
    // catalogue rather than the readiness row — which is exactly where an owner
    // first meets this refusal.
    it("offers the field from where the refusal is read, with no model pinned", async () => {
      // No model pinned — a fresh connection, which is where an owner first
      // meets this refusal, and the path that reads the catalogue.
      const unpinned = profile({
        ...identityLinked(),
        model: "<model>",
        connection_configured: true,
      });
      stubFetch({
        "GET /api/models": models({ profiles: [unpinned], chat_profiles: [unpinned] }),
        "GET /api/models/anthropic-hosted/provider-models": {
          profile_id: "anthropic-hosted",
          provider: "anthropic",
          status: "unavailable",
          reason_code: "provider_workspace_required:http_400",
          models: [],
        },
      });
      render(ModelsView, { props: { tab: "add" } });

      await rowAction("Test connection");
      await fireEvent.click(
        await screen.findByRole("button", { name: "Add workspace ID" }),
      );

      // Opened on the section that holds it, so the sentence points at
      // something the owner can see rather than at a folded-away box.
      expect(await screen.findByLabelText(/Workspace ID/i)).toBeVisible();
    });

    it("reports that a workspace is named, never which one", async () => {
      const connected = profile({
        ...identityLinked(),
        connection_configured: true,
        workspace_configured: true,
      });
      stubFetch({
        "GET /api/models": models({
          profiles: [connected],
          chat_profiles: [connected],
        }),
      });
      render(ModelsView, { props: { tab: "add" } });

      // In Details, where credential management lives — the card carries
      // readiness and nothing else by design.
      await rowAction("Details");
      expect(
        await screen.findByText(/workspace named/i),
      ).toBeInTheDocument();
      expect(document.body.textContent).not.toContain("wrkspc_");
    });
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
    render(ModelsView, { props: { tab: "add" } });

    // BUG-208 slice E moved credential management into Details: it is not the
    // thing an owner came to the card to do, and the card had five controls.
    await rowAction("Details");
    await fireEvent.click(await screen.findByRole("button", { name: "Disconnect Anthropic" }));

    await waitFor(() =>
      expect(mock).toHaveBeenCalledWith(
        "/api/models/anthropic-hosted/connection",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({
            endpoint: null,
            api_key: null,
            admin_api_key: null,
            workspace_id: null,
          }),
        }),
      ),
    );
  });

  // A live run against an identity-linked Anthropic key found the FIXED-355 /
  // FIXED-370 defect alive in the *other* control on this page. The provider
  // answered in full, naming the workspace id it wanted; `testNote` reads that
  // classification and the picker did not, so the one control on the path an
  // owner actually walks — connect, then choose a model — said "Provider
  // unreachable" about a provider that had just replied.
  it("says why the catalogue failed in the picker, not only under Test", async () => {
    stubFetch({
      "GET /api/models": models({
        profiles: [
          profile({
            profile_id: "anthropic-claude",
            provider: "anthropic",
            model: "<model>",
          }),
        ],
      }),
      "GET /api/models/anthropic-claude/provider-models": {
        profile_id: "anthropic-claude",
        provider: "anthropic",
        status: "unavailable",
        reason_code: "provider_workspace_required",
        models: [],
      },
    });
    render(ModelsView, { tab: "add" });
    await rowAction("Select models…");

    expect(await screen.findByText(/identity-linked, so it acts inside one workspace/i)).toBeTruthy();
    expect(screen.queryByText(/Provider unreachable/i)).toBeNull();
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
      "PUT /api/models/ollama-local-openai-compatible/available-models": {
        ok: true,
        profile_id: "ollama-local-openai-compatible",
        models: ["qwen2.5"],
      },
    });
    render(ModelsView, { tab: "add" });
    await rowAction("Select models…");
    // One switch per model the provider published, and the switch is the whole
    // decision — there is no second "Use model" step.
    const qwen = await screen.findByRole("checkbox", { name: "Qwen 2.5" });
    expect(screen.getByRole("checkbox", { name: "Llama 3.2" })).toBeTruthy();
    await fireEvent.click(qwen);

    await waitFor(() => {
      const put = mock.mock.calls.find(
        (c) =>
          (c[1]?.method ?? "GET").toUpperCase() === "PUT" &&
          String(c[0]).includes("/available-models"),
      );
      expect(put).toBeTruthy();
      expect(JSON.parse(put![1]!.body as string)).toEqual({ models: ["qwen2.5"] });
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
    render(ModelsView, { tab: "add" });
    await rowAction("Select models…");
    expect(
      await screen.findAllByRole("checkbox", { name: "GPT-4o Mini" }),
    ).toHaveLength(1);
    expect(screen.getByRole("checkbox", { name: "Llama 3.1 8B Instruct" })).toBeTruthy();
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
    render(ModelsView, { tab: "add" });
    await rowAction("Select models…");
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
    render(ModelsView, { props: { tab: "runtime" } });
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
    render(ModelsView, { props: { tab: "runtime" } });
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
    render(ModelsView, { props: { tab: "runtime" } });
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
        // MODEL-05/MODEL-06 put the local library on this tab, and a mock
        // that answers every GET with the models payload hands it a body with
        // no `roots`, which fails the whole panel render rather than only the
        // panel that asked. Route by path.
        const path = String(_input).split("?")[0];
        return {
          ok: true,
          status: 200,
          json: async () =>
            path.endsWith("/api/model-library")
              ? { roots: [], models: [] }
              : models({ fallback_sequence: ["raiker-local-llama-cpp"] }),
        } as Response;
      },
    );
    vi.stubGlobal("fetch", mock);

    render(ModelsView, { props: { tab: "runtime" } });
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
  // MODEL-03 — the six tabs this replaces named where a model was *stored*
  // (Local, Hosted, Hugging Face) or which table a fact came out of (Activity,
  // Routing, Pricing). None of them answered the question every owner arrives
  // with, which is what is running their work.
  it("offers one tab per question an owner arrives with", async () => {
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
      "Overview",
      "My models",
      "Add model",
      "Runtime & routing",
      "Usage",
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

  // MODEL-12 — what you spent and what it costs were two top-level tabs, so an
  // owner checking a bill read the rate on one page and the usage on another
  // and did the multiplication themselves.
  it("puts pricing and usage on one tab", async () => {
    stubFetch({
      "GET /api/models": models({}),
      "GET /api/models/pricing": { entries: [], sync: [], can_override: false },
    });
    render(ModelsView, { props: { tab: "usage" } });
    expect(
      await screen.findByRole("heading", { name: "Pricing" }),
    ).toBeInTheDocument();
    // Provider cards belong to Add model. The readiness summary is page-level
    // on purpose and stays visible here.
    expect(screen.queryByText("On this device")).toBeNull();
    expect(screen.queryByText("Your hosted providers")).toBeNull();
  });

  // Posture was a top-level tab holding four read-only facts and a paragraph.
  // The facts belong above the cards whose refusals they explain, and the
  // paragraph belongs in the guide; a whole destination for seven words of state
  // put the answer one click away from the question.
  it("reads the off-machine posture above the hosted cards it explains", async () => {
    stubFetch({ "GET /api/models": models({}) });
    render(ModelsView, { props: { tab: "add" } });
    const posture = await screen.findByLabelText("Off-machine provider posture");
    expect(within(posture).getByText("Hosted model gate")).toBeInTheDocument();
    expect(within(posture).getByText("Private-network gate")).toBeInTheDocument();
    expect(within(posture).getByText("Egress allowlist")).toBeInTheDocument();
    expect(within(posture).getByText("Off-machine profiles")).toBeInTheDocument();
    // On the tab it is about, not on one of its own.
    expect(screen.getByRole("tab", { name: "Add model" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  // Found live, 2026-09-06: with Anthropic connected and a model pinned, this
  // panel printed "Off" for the hosted gate directly above the connected card.
  // Connecting a provider *is* consent to use it, so the enforcing path had
  // said yes and the panel was reporting the gate row alone — FIXED-322's
  // defect on a second surface.
  it("says a gate is on by connection when the enforcing path allows it", async () => {
    stubFetch({
      "GET /api/models": models({
        hosted_model_gate_state: "disabled",
        hosted_model_gate_enforced: true,
      }),
    });
    render(ModelsView, { props: { tab: "add" } });
    const posture = await screen.findByLabelText("Off-machine provider posture");
    expect(within(posture).getByText("On (by connection)")).toBeInTheDocument();
  });

  // The case that must never be softened: an explicit revocation outranks a
  // saved connection, so a gate the owner turned off reads Off whatever is
  // connected.
  it("still reads Off for a gate the enforcing path refuses", async () => {
    stubFetch({
      "GET /api/models": models({
        hosted_model_gate_state: "disabled",
        hosted_model_gate_enforced: false,
      }),
    });
    render(ModelsView, { props: { tab: "add" } });
    const posture = await screen.findByLabelText("Off-machine provider posture");
    expect(within(posture).queryByText("On (by connection)")).toBeNull();
    expect(within(posture).getAllByText("Off").length).toBeGreaterThan(0);
  });

  // The other direction, and the worse one. On an instance with nothing
  // connected the row resolves to `enabled_runtime` from the shipped default
  // table while the enforcing path refuses every hosted provider, so the panel
  // read "On" above providers that answer
  // `hosted_provider_requires_explicit_policy` at the first turn.
  it("does not read On for a gate that would refuse the turn", async () => {
    stubFetch({
      "GET /api/models": models({
        hosted_model_gate_state: "enabled_runtime",
        hosted_model_gate_enforced: false,
      }),
    });
    render(ModelsView, { props: { tab: "add" } });
    const posture = await screen.findByLabelText("Off-machine provider posture");
    expect(within(posture).getByText("Off until connected")).toBeInTheDocument();
  });

  // Its predecessor asserted the posture stayed off the Local tab. With Local
  // and Hosted merged into one add-a-model errand there is no such tab, and the
  // facts are stated *before* a provider is connected rather than after it
  // refuses — "the hosted gate is off" is exactly what an owner about to
  // connect one needs. What must not happen is the posture appearing on a tab
  // that is not about connecting anything.
  it("does not read the off-machine posture where nothing connects", async () => {
    stubFetch({ "GET /api/models": models({}) });
    render(ModelsView, { props: { tab: "runtime" } });
    expect(screen.queryByLabelText("Off-machine provider posture")).toBeNull();
  });

  it("marks the selected tab and links each panel back to it", async () => {
    stubFetch({ "GET /api/models": models({}) });
    render(ModelsView, { props: { tab: "runtime" } });
    await waitFor(() =>
      expect(screen.getByText("Model fallback sequence")).toBeTruthy(),
    );
    expect(screen.getByRole("tab", { name: "Runtime & routing" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tabpanel")).toHaveAttribute(
      "aria-labelledby",
      "tab-runtime",
    );
  });

  it("selecting a tab writes it into the hash, so a panel is shareable", async () => {
    stubFetch({ "GET /api/models": models({}) });
    render(ModelsView);
    await fireEvent.click(await screen.findByRole("tab", { name: "Usage" }));
    expect(window.location.hash).toBe("#/models?tab=usage");
    expect(screen.getByRole("tab", { name: "Usage" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(await screen.findByRole("tabpanel")).toHaveAttribute(
      "aria-labelledby",
      "tab-usage",
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
  const lmStudio = () =>
    profile({
      profile_id: "lm-studio-local",
      provider: "lm-studio",
      model: "local-lmstudio",
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

  // The second provider is LM Studio rather than llama.cpp: MODEL-05 moved the
  // framework slot rows to Runtime & routing, and the claim under test is about
  // two ordinary local rows on one tab, not about which two.
  it("shows one provider's result only under that provider", async () => {
    stubFetch({
      "GET /api/models": models({ profiles: [ollama(), lmStudio()] }),
      "GET /api/model-library": { roots: [], models: [] },
      "POST /api/model-readiness/check": {
        state: "ready",
        ready: true,
        reason_code: "model_ready",
        summary: "Ollama can reach gemma4:31b-cloud.",
        remediation: "",
      },
    });
    render(ModelsView, { tab: "add" });

    // MODEL-15 — Test is troubleshooting, so it is inside each row's overflow
    // rather than a standing invitation to re-prove a working connection. Two
    // rows, two overflows, and the one that ran the check is still the one that
    // shows the answer, which is the whole claim here.
    await waitFor(async () =>
      expect(
        (await screen.findAllByRole("button", { name: /^More actions for / })).length,
      ).toBe(2),
    );
    await rowAction("Test connection", 0);

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
    render(ModelsView, { tab: "add" });

    await rowAction("Test connection", 0);
    await waitFor(() =>
      expect(screen.getAllByText("The exact model is reachable.")).toHaveLength(
        1,
      ),
    );
    await rowAction("Test connection", 1);

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
    render(ModelsView, { tab: "add" });

    await rowAction("Test connection", 0);
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
      "GET /api/models": models({ profiles: [ollama(), lmStudio()] }),
      "GET /api/model-library": { roots: [], models: [] },
      "POST /api/model-readiness/check": {
        state: "runtime_stopped",
        ready: false,
        reason_code: "local_runtime_unreachable",
        summary: "Ollama is not reachable.",
        remediation: "Start or reconnect Ollama, then check again.",
      },
    });
    render(ModelsView, { tab: "add" });

    await rowAction("Test connection", 0);
    const result = await screen.findByText(/^Ollama is not reachable\./);
    expect(result).toHaveAttribute(
      "data-test-result",
      "ollama-local-openai-compatible",
    );
    expect(result.closest(".local-row")).not.toBeNull();
  });
});

// Found live, 2026-09-07. The model picker could be dismissed by clicking its
// backdrop or its Done button and by nothing else, so an owner who opened a
// provider's catalogue and reached for the key every other dialog in the
// product answers to was left holding a modal that would not go. VIS2-17 asks
// for one overlay vocabulary, and this is the part of it a keyboard user
// actually depends on.
describe("Models modals answer to Escape", () => {
  it("closes the provider catalogue", async () => {
    stubFetch({
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
        models: ["qwen2.5"],
      },
    });
    render(ModelsView, { tab: "add" });
    await rowAction("Select models…");
    expect(await screen.findByRole("dialog", { name: /models/i })).toBeInTheDocument();

    await fireEvent.keyDown(window, { key: "Escape" });

    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: /models/i })).not.toBeInTheDocument(),
    );
  });

  it("closes the details panel", async () => {
    stubFetch({ "GET /api/models": models({}) });
    render(ModelsView, { tab: "add" });
    await rowAction("Details");
    expect(await screen.findByRole("dialog")).toBeInTheDocument();

    await fireEvent.keyDown(window, { key: "Escape" });

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});
