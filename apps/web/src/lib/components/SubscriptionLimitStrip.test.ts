import { render, screen } from "@testing-library/svelte";
import { afterEach, expect, it, vi } from "vitest";
import type { SubscriptionLimits } from "../apiTypes";
import SubscriptionLimitStrip from "./SubscriptionLimitStrip.svelte";

afterEach(() => vi.useRealTimers());

function limits(partial: Partial<SubscriptionLimits> = {}): SubscriptionLimits {
  return {
    windows: [
      { label: "5-hour", used_percent: 68.4, window_minutes: 300, resets_at: null },
      { label: "Weekly", used_percent: 12, window_minutes: 10080, resets_at: null },
    ],
    observed_at: "2026-09-03T12:00:00Z",
    stale: false,
    source: "provider_turn",
    ...partial,
  };
}

it("says how much of each window is left, not how much is spent", () => {
  render(SubscriptionLimitStrip, { props: { limits: limits() } });
  // "32% left" is the number a person acts on before starting something long.
  expect(screen.getByText("32% left")).toBeInTheDocument();
  expect(screen.getByText("88% left")).toBeInTheDocument();
  expect(screen.getByText("5-hour")).toBeInTheDocument();
});

it("exposes each window as a meter carrying the provider's own figure", () => {
  render(SubscriptionLimitStrip, { props: { limits: limits() } });
  const meters = screen.getAllByRole("meter");
  expect(meters).toHaveLength(2);
  expect(meters[0]).toHaveAttribute("aria-valuenow", "68");
});

it("says when a reset is coming, in the units a person would use", () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-09-03T12:00:00Z"));
  render(SubscriptionLimitStrip, {
    props: {
      limits: limits({
        windows: [
          { label: "5-hour", used_percent: 90, window_minutes: 300, resets_at: "2026-09-03T14:00:00Z" },
        ],
      }),
    },
  });
  expect(screen.getByText("resets in 2 h")).toBeInTheDocument();
});

it("admits an old reading rather than presenting it as current", () => {
  render(SubscriptionLimitStrip, { props: { limits: limits({ stale: true }) } });
  expect(screen.getByText(/From an earlier turn/)).toBeInTheDocument();
});

it("renders nothing at all for a provider that reported no window", () => {
  const { container } = render(SubscriptionLimitStrip, {
    props: { limits: limits({ windows: [] }), label: null },
  });
  expect(container.querySelectorAll(".limit")).toHaveLength(0);
  expect(screen.queryByRole("meter")).not.toBeInTheDocument();
});
