import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import ModelPricingPanel from "./ModelPricingPanel.svelte";
import { stubFetch } from "../test-helpers";

afterEach(() => vi.unstubAllGlobals());

const ENTRY = {
  provider: "anthropic",
  model: "claude-haiku-4-5-20251001",
  profile_id: "anthropic-hosted",
  source: "config",
  currency: "USD",
  input_per_mtok: "1.00",
  output_per_mtok: "5.00",
  cache_write_per_mtok: null,
  cache_read_per_mtok: "0.10",
  effective_from: "2026-07-01T00:00:00Z",
  as_of: "2026-07",
  reviewed_at: "2026-08-01",
  review_due_at: "2026-11-01",
  review_status: "current",
  recorded_at: "2026-07-01T00:00:00Z",
  recorded_by: null,
  reason: "Shipped list price, reviewed documentation adapter",
  has_owner_override: false,
  history: [
    {
      provider: "anthropic",
      model: "claude-haiku-4-5-20251001",
      source: "config",
      effective_from: "2026-07-01T00:00:00Z",
      recorded_at: "2026-07-01T00:00:00Z",
      as_of: "2026-07",
      recorded_by: null,
      reason: "Shipped list price, reviewed documentation adapter",
      currency: "USD",
      input_per_mtok: "1.00",
      output_per_mtok: "5.00",
      cache_write_per_mtok: null,
      cache_read_per_mtok: "0.10",
    },
  ],
};

function pricing(overrides: Record<string, unknown> = {}) {
  return {
    "GET /api/models/pricing": {
      entries: [ENTRY],
      sync: [
        {
          provider: "anthropic",
          interval_hours: 12,
          last_attempt_at: "2026-07-31T00:00:00Z",
          last_success_at: "2026-07-31T00:00:00Z",
          next_refresh_at: "2026-07-31T12:00:00Z",
          last_error: null,
          models_recorded: 1,
          has_last_good: true,
          due: false,
          stale: false,
        },
      ],
      can_override: true,
      ...overrides,
    },
  };
}

describe("ModelPricingPanel — BUG-21", () => {
  it("states the exact model, its source, and every rate component it has", async () => {
    stubFetch(pricing());
    render(ModelPricingPanel);
    expect(await screen.findByText("claude-haiku-4-5-20251001")).toBeInTheDocument();
    expect(screen.getByText("Reviewed documentation")).toBeInTheDocument();
    expect(screen.getByText("USD 1.00")).toBeInTheDocument();
    expect(screen.getByText("USD 0.10")).toBeInTheDocument();
    // No published cache-write rate, so an em dash rather than an invented one.
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("states when a provider was last refreshed and when it is next due", async () => {
    stubFetch(pricing());
    render(ModelPricingPanel);
    expect(await screen.findByText("Current")).toBeInTheDocument();
    expect(screen.getByText(/Last refresh/)).toBeInTheDocument();
    expect(screen.getByText(/Next due/)).toBeInTheDocument();
    expect(screen.getByText(/every 12h/)).toBeInTheDocument();
  });

  it("distinguishes a human price review from provider synchronisation", async () => {
    stubFetch(pricing());
    render(ModelPricingPanel);
    expect(await screen.findByText("Reviewed 2026-08-01")).toBeInTheDocument();
    expect(screen.getByText("Review due 2026-11-01")).toBeInTheDocument();
    expect(screen.getByText("Review current")).toBeInTheDocument();
  });

  it("flags a documented rate whose human review is overdue", async () => {
    stubFetch(pricing({ entries: [{ ...ENTRY, review_status: "overdue" }] }));
    render(ModelPricingPanel);
    expect(await screen.findByText("Review overdue")).toBeInTheDocument();
  });

  it("shows a failed refresh as stale while keeping the last good rate visible", async () => {
    stubFetch(
      pricing({
        sync: [
          {
            provider: "anthropic",
            interval_hours: 12,
            last_attempt_at: "2026-07-31T10:00:00Z",
            last_success_at: "2026-07-30T00:00:00Z",
            next_refresh_at: "2026-07-30T12:00:00Z",
            last_error: "provider_unreachable",
            models_recorded: 1,
            has_last_good: true,
            due: true,
            stale: true,
          },
        ],
      }),
    );
    render(ModelPricingPanel);
    expect(await screen.findByText("Stale")).toBeInTheDocument();
    expect(screen.getByText(/provider_unreachable/)).toBeInTheDocument();
    expect(screen.getByText(/previous rates are still in effect/)).toBeInTheDocument();
    // The rate itself is still shown — a failed refresh must not blank it.
    expect(screen.getByText("USD 1.00")).toBeInTheDocument();
  });

  it("opens the full price history for one model", async () => {
    stubFetch(pricing());
    render(ModelPricingPanel);
    await fireEvent.click(await screen.findByRole("button", { name: "History (1)" }));
    expect(
      // The heading names the model the way the table does.
      screen.getByRole("heading", { name: /Price history — Haiku 4.5/ }),
    ).toBeInTheDocument();
    expect(screen.getByText(/in USD 1.00 · out USD 5.00/)).toBeInTheDocument();
  });

  it("refuses an override with no reason, because it is recorded against you", async () => {
    const fetchMock = stubFetch(pricing());
    render(ModelPricingPanel);
    await fireEvent.click(await screen.findByRole("button", { name: "Override" }));
    await fireEvent.click(screen.getByRole("button", { name: "Record override" }));
    expect(await screen.findByText(/A reason is required/)).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, init]) => (init as RequestInit)?.method === "PUT")).toBe(
      false,
    );
  });

  it("sends every rate component and the reason when an override is recorded", async () => {
    const fetchMock = stubFetch({
      ...pricing(),
      "PUT /api/models/anthropic-hosted/price": { ok: true },
    });
    render(ModelPricingPanel);
    await fireEvent.click(await screen.findByRole("button", { name: "Override" }));
    await fireEvent.input(screen.getByLabelText("Input / Mtok"), { target: { value: "2.5" } });
    await fireEvent.input(screen.getByLabelText("Output / Mtok"), { target: { value: "9" } });
    await fireEvent.input(screen.getByLabelText("Cache read / Mtok"), { target: { value: "0.25" } });
    await fireEvent.input(screen.getByLabelText("Reason"), {
      target: { value: "Enterprise agreement" },
    });
    await fireEvent.click(screen.getByRole("button", { name: "Record override" }));

    await waitFor(() => {
      const put = fetchMock.mock.calls.find(([, init]) => (init as RequestInit)?.method === "PUT");
      expect(put).toBeDefined();
      expect(JSON.parse(String((put![1] as RequestInit).body))).toMatchObject({
        model: "claude-haiku-4-5-20251001",
        input_per_mtok: "2.5",
        output_per_mtok: "9",
        cache_read_per_mtok: "0.25",
        reason: "Enterprise agreement",
      });
    });
  });

  it("does not offer an override to someone who cannot record one", async () => {
    stubFetch(pricing({ can_override: false }));
    render(ModelPricingPanel);
    expect(await screen.findByText(/needs the runtime gate-manager role/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Override" })).not.toBeInTheDocument();
  });

  it("degrades to a readable error rather than crashing on a malformed payload", async () => {
    stubFetch({ "GET /api/models/pricing": { unexpected: true } });
    render(ModelPricingPanel);
    expect(await screen.findByText(/No model has a recorded rate yet/)).toBeInTheDocument();
  });
});
