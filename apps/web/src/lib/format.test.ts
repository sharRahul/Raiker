import { describe, expect, it } from "vitest";
import { formatTimestamp, humanize, providerName, relativeTime, shortId } from "./format";

describe("format helpers", () => {
  it("renders compact relative times", () => {
    const now = new Date("2026-07-07T12:00:00Z");
    expect(relativeTime("2026-07-07T11:59:50Z", now)).toBe("just now");
    expect(relativeTime("2026-07-07T11:55:00Z", now)).toBe("5m ago");
    expect(relativeTime("2026-07-07T09:00:00Z", now)).toBe("3h ago");
    expect(relativeTime("2026-07-05T12:00:00Z", now)).toBe("2d ago");
    expect(relativeTime(null, now)).toBe("—");
    expect(relativeTime("not-a-date", now)).toBe("not-a-date");
  });

  it("treats naive timestamps as UTC", () => {
    const now = new Date("2026-07-07T12:10:00Z");
    expect(relativeTime("2026-07-07T12:00:00", now)).toBe("10m ago");
  });

  it("falls back to the raw string for unparseable timestamps", () => {
    expect(formatTimestamp("garbage")).toBe("garbage");
    expect(formatTimestamp(null)).toBe("—");
  });

  it("shortens long ids and leaves short ones alone", () => {
    expect(shortId("sess_abcdefghijklmnop")).toBe("sess_abcde…");
    expect(shortId("sess_1")).toBe("sess_1");
    expect(shortId(null)).toBe("—");
  });

  it("humanizes snake_case names", () => {
    expect(humanize("shell_execution")).toBe("Shell execution");
    expect(humanize("")).toBe("—");
  });

  it("maps providers to brand names and passes unknown ones through", () => {
    expect(providerName("lm-studio")).toBe("LM Studio");
    expect(providerName("vllm")).toBe("vLLM");
    expect(providerName("anthropic")).toBe("Anthropic");
    expect(providerName("llama.cpp")).toBe("llama.cpp");
    expect(providerName("something-else")).toBe("something-else");
    expect(providerName(null)).toBe("—");
  });
});
