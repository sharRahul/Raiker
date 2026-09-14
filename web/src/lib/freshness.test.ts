/*
 * NEW-HOME-01 and NEW-MAP-01 — the four states `null` was standing in for.
 *
 * The defect both pages had was a single value carrying "not read yet", "the
 * read failed" and "nothing to report" at once, so each page picked whichever
 * reading suited its own rendering. These assert that the four are four.
 */
import { describe, expect, it } from "vitest";

import {
  failed,
  freshnessLabel,
  hasValue,
  isCurrent,
  loading,
  received,
  valueOf,
} from "./freshness";

const MINUTE = 60_000;

describe("what a surface knows", () => {
  it("has nothing to show and nothing to claim before the first read", () => {
    const state = loading<number>();
    expect(valueOf(state)).toBeNull();
    expect(hasValue(state)).toBe(false);
    expect(isCurrent(state)).toBe(false);
  });

  it("has both once a read answers", () => {
    const state = received(3, 1_000);
    expect(valueOf(state)).toBe(3);
    expect(isCurrent(state)).toBe(true);
  });

  it("keeps the last answer when a refresh fails, and stops claiming it", () => {
    const state = failed(received(3, 1_000), "HTTP 500");
    // Worth showing — throwing away the only answer anyone has is its own kind
    // of lie — and not worth asserting, which is the distinction both defects
    // collapsed.
    expect(valueOf(state)).toBe(3);
    expect(hasValue(state)).toBe(true);
    expect(isCurrent(state)).toBe(false);
  });

  it("says unavailable when nothing has ever been read", () => {
    const state = failed(loading<number>(), "unreachable");
    expect(state.kind).toBe("unavailable");
    expect(valueOf(state)).toBeNull();
    expect(isCurrent(state)).toBe(false);
  });

  it("keeps the original timestamp across repeated failures", () => {
    // Otherwise a page that retries every fifteen seconds reports its last
    // *attempt* as its last success, which is the staleness defect again with
    // a fresher-looking timestamp.
    const once = failed(received(3, 1_000), "HTTP 500");
    const twice = failed(once, "HTTP 500");
    expect(twice.kind).toBe("stale");
    expect(twice.kind === "stale" && twice.at).toBe(1_000);
  });
});

describe("what the reader is told", () => {
  it("names the thing and when it was true", () => {
    expect(freshnessLabel(received(3, 0), "Runtime health", 5 * MINUTE)).toBe(
      "Runtime health · updated 5 minutes ago",
    );
  });

  it("carries both halves of a stale line", () => {
    const line = freshnessLabel(
      failed(received(3, 0), "HTTP 500"),
      "Workspace graph",
      2 * MINUTE,
    );
    // When it was true, and that renewing it failed. Either alone misleads.
    expect(line).toContain("last updated 2 minutes ago");
    expect(line).toContain("refresh failed (HTTP 500)");
  });

  it("says unavailable rather than inventing an age", () => {
    const line = freshnessLabel(failed(loading<number>(), "HTTP 503"), "Runtime health");
    expect(line).toBe("Runtime health · unavailable (HTTP 503)");
  });

  it("reads naturally at every age", () => {
    expect(freshnessLabel(received(3, 0), "X", 10_000)).toContain("just now");
    expect(freshnessLabel(received(3, 0), "X", 60 * MINUTE)).toContain("1 hour ago");
    expect(freshnessLabel(received(3, 0), "X", 48 * 60 * MINUTE)).toContain("2 days ago");
  });
});
