import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import ContextMeterPopover from "./ContextMeterPopover.svelte";
import type { ContextUsage } from "../apiTypes";

function usage(overrides: Partial<ContextUsage> = {}): ContextUsage {
  return {
    session_id: "sess_1",
    profile_id: "anthropic-hosted",
    provider: "anthropic",
    model: "claude-haiku-4-5-20251001",
    used_tokens: 2900,
    context_window_tokens: 200_000,
    context_window_source: "provider",
    usage_source: "provider",
    billable: true,
    session_cost: "0.0030",
    provider_total_cost: "0.0059",
    currency: "USD",
    price_source: "config",
    price_as_of: "2026-07",
    session_turns: 1,
    session_input_tokens: 2900,
    session_output_tokens: 12,
    ...overrides,
  };
}

describe("ContextMeterPopover", () => {
  it("prefers provider-reported usage over the browser's estimate", () => {
    render(ContextMeterPopover, { usedTokens: 99, contextWindowTokens: 1000, estimated: true, usage: usage() });
    expect(screen.getByText("2,900 tokens used")).toBeInTheDocument();
    expect(screen.getByText("1.45%")).toBeInTheDocument();
    expect(screen.getByText(/Reported by anthropic/)).toBeInTheDocument();
    expect(screen.getByText(/Capacity reported by runtime/)).toBeInTheDocument();
    expect(screen.queryByText(/Estimated from this chat/)).not.toBeInTheDocument();
  });

  it("shows this chat and the provider all-time total, and names the price source", () => {
    render(ContextMeterPopover, { usage: usage(), locale: "en-GB" });
    expect(screen.getByText("US$0.0030")).toBeInTheDocument();
    expect(screen.getByText("US$0.0059")).toBeInTheDocument();
    expect(screen.getByText(/list price, as of 2026-07/)).toBeInTheDocument();
  });

  it("falls back to the labelled local estimate before any turn has run", () => {
    render(ContextMeterPopover, {
      usedTokens: 400,
      contextWindowTokens: 200_000,
      estimated: true,
      usage: usage({ usage_source: "unavailable", used_tokens: null, session_turns: 0, session_cost: null, provider_total_cost: null }),
    });
    expect(screen.getByText("400 tokens used")).toBeInTheDocument();
    expect(screen.getByText("0.20%")).toBeInTheDocument();
    expect(screen.getByText(/Estimated from this chat/)).toBeInTheDocument();
  });

  it("labels a configured capacity separately from provider pricing", () => {
    render(ContextMeterPopover, {
      usage: usage({ context_window_source: "config" }),
    });
    expect(screen.getByText(/Capacity configured in Raiker/)).toBeInTheDocument();
  });

  it("labels an owner-set capacity as owner control", () => {
    render(ContextMeterPopover, {
      usage: usage({ context_window_source: "owner" }),
    });
    expect(screen.getByText(/Capacity set by owner/)).toBeInTheDocument();
  });

  it("says no API cost for a provider that runs on this machine", () => {
    render(ContextMeterPopover, {
      usage: usage({ billable: false, provider: "llama.cpp", session_cost: null, provider_total_cost: null }),
    });
    expect(screen.getByText(/no API cost/i)).toBeInTheDocument();
    expect(screen.getByText(/Reported by llama\.cpp/)).toBeInTheDocument();
    expect(screen.getByText(/Capacity reported by runtime/)).toBeInTheDocument();
    expect(screen.queryByText("$0.00")).not.toBeInTheDocument();
  });

  it("states that a price is missing rather than rendering a zero cost", () => {
    // The whole point: "$0.00" must mean free, never "we could not price this".
    render(ContextMeterPopover, {
      usage: usage({ session_cost: null, provider_total_cost: null, price_source: null, price_as_of: null }),
    });
    expect(screen.getByText(/No rate is recorded/)).toBeInTheDocument();
    expect(screen.getByText("Unknown")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Configure/ })).toHaveAttribute(
      "href",
      "#/models?tab=pricing",
    );
    expect(screen.queryByText("$0.00")).not.toBeInTheDocument();
  });

  it("says Unknown before the first turn on a billable, unpriced model (BUG-21)", () => {
    // The old rule only spoke up after a turn had run, so a fresh conversation
    // on an unpriced model showed nothing — which reads as "free".
    render(ContextMeterPopover, {
      usage: usage({
        session_turns: 0,
        session_cost: null,
        provider_total_cost: null,
        price_source: null,
        price_unknown: true,
      }),
    });
    expect(screen.getByText("Unknown")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Configure/ })).toBeInTheDocument();
  });

  it("lists each rate component the registry holds, and omits the ones it does not", () => {
    render(ContextMeterPopover, {
      usage: usage({
        price_input_per_mtok: "1.00",
        price_output_per_mtok: "5.00",
        price_cache_read_per_mtok: "0.10",
        price_effective_from: "2026-07-01T00:00:00Z",
      }),
    });
    expect(screen.getByText("Input")).toBeInTheDocument();
    expect(screen.getByText("Cache read")).toBeInTheDocument();
    // No cache-write rate was published, so none is shown — never inferred.
    expect(screen.queryByText("Cache write")).not.toBeInTheDocument();
    expect(screen.getByText(/effective 2026-07-01/)).toBeInTheDocument();
  });

  it("reports an unknown capacity instead of dividing by it", () => {
    render(ContextMeterPopover, {
      usedTokens: 100,
      contextWindowTokens: null,
      usage: usage({ context_window_tokens: null, context_window_source: null }),
    });
    expect(screen.getByText(/Context capacity is not configured/)).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("bounds the meter to 0-100 for an over-full context", () => {
    render(ContextMeterPopover, {
      usage: usage({ used_tokens: 400_000, context_window_tokens: 200_000 }),
    });
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "100");
  });

  it("shows that earlier context was compacted without implying transcript deletion", () => {
    render(ContextMeterPopover, {
      usage: usage({
        latest_compaction: {
          status: "completed",
          created_at: "2026-08-11T12:00:00Z",
          source_turn_count: 8,
          estimated_input_tokens_before: 180_000,
          estimated_summary_tokens: 2_400,
          reason_code: null,
        },
      }),
      locale: "en-GB",
    });
    expect(screen.getByText("Earlier context compacted")).toBeInTheDocument();
    expect(screen.getByText(/180,000.*2,400 tokens/i)).toBeInTheDocument();
    expect(screen.getByText(/Chat transcript is unchanged/)).toBeInTheDocument();
  });

  it("states the safe fallback when automatic compaction was unavailable", () => {
    render(ContextMeterPopover, {
      usage: usage({
        latest_compaction: {
          status: "failed",
          created_at: "2026-08-11T12:00:00Z",
          source_turn_count: 6,
          estimated_input_tokens_before: 182_000,
          estimated_summary_tokens: 0,
          reason_code: "provider_unavailable",
        },
      }),
    });
    expect(screen.getByText("Recent history retained")).toBeInTheDocument();
    expect(screen.getByText(/Compaction was unavailable/)).toBeInTheDocument();
  });
});
