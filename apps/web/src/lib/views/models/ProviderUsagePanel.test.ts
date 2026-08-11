import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { stubFetch } from "../../test-helpers";
import ProviderUsagePanel from "./ProviderUsagePanel.svelte";

afterEach(() => vi.unstubAllGlobals());

const weekly = {
  window: "rolling_7_days",
  providers: [
    {
      profile_id: "openrouter-policy-gated",
      provider: "openrouter",
      display_name: "OpenRouter",
      observed: {
        input_tokens: 800,
        output_tokens: 200,
        cache_read_tokens: 0,
        cache_write_tokens: 0,
        total_tokens: 1000,
        requests: 4,
        turns: 3,
        compactions: 1,
        known_cost: "0.0125",
        cost_currency: "USD",
        unpriced_models: [],
        source: "raiker_ledger",
        window: "rolling_7_days",
      },
      owner_budget: 5000,
      native: {
        status: "available",
        reason_code: null,
        checked_at: "2026-08-11T12:00:00Z",
        expires_at: "2026-08-11T12:05:00Z",
        metrics: [
          {
            unit: "USD",
            used: "2.5",
            limit: "10",
            remaining: "7.5",
            reset_interval: "weekly",
            resets_at: null,
            scope: "api_key",
            source: "provider",
          },
        ],
      },
    },
  ],
};

describe("ProviderUsagePanel", () => {
  it("keeps Raiker-observed usage separate from genuine provider data", async () => {
    stubFetch({ "GET /api/models/weekly-usage": weekly });
    render(ProviderUsagePanel);

    expect(await screen.findByText("1,000 tokens")).toBeInTheDocument();
    expect(screen.getByText("Raiker observed")).toBeInTheDocument();
    expect(screen.getByText("Provider reported")).toBeInTheDocument();
    expect(screen.getByText("3 turns · 4 model requests · 1 compaction")).toBeInTheDocument();
    expect(screen.getByText("Advisory Raiker control — not a provider subscription limit.")).toBeInTheDocument();
  });

  it("saves an owner token budget and reloads the rolling view", async () => {
    const mock = stubFetch({
      "GET /api/models/weekly-usage": weekly,
      "PUT /api/models/openrouter-policy-gated/weekly-budget": {
        ok: true,
        profile_id: "openrouter-policy-gated",
      },
    });
    render(ProviderUsagePanel);

    await fireEvent.click(await screen.findByRole("button", { name: "Edit budget" }));
    const input = screen.getByLabelText("Weekly token budget for OpenRouter");
    await fireEvent.input(input, { target: { value: "7500" } });
    await fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(mock).toHaveBeenCalledWith(
        "/api/models/openrouter-policy-gated/weekly-budget",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({ token_budget: 7500 }),
        }),
      ),
    );
  });

  it("labels one local request grammatically and as having no API cost", async () => {
    stubFetch({
      "GET /api/models/weekly-usage": {
        ...weekly,
        providers: [
          {
            ...weekly.providers[0],
            profile_id: "ollama-local-openai-compatible",
            provider: "ollama",
            observed: {
              ...weekly.providers[0].observed,
              turns: 1,
              requests: 1,
              compactions: 0,
              known_cost: null,
              cost_currency: null,
            },
            native: {
              status: "not_supported",
              reason_code: "provider_quota_api_not_supported",
              checked_at: null,
              expires_at: null,
              metrics: [],
            },
          },
        ],
      },
    });
    render(ProviderUsagePanel);

    expect(await screen.findByText("1 turn · 1 model request")).toBeInTheDocument();
    expect(screen.getByText("No API cost — local runtime.")).toBeInTheDocument();
  });
});
