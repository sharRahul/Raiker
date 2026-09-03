import { describe, expect, it } from "vitest";
import {
  formatTimestamp,
  groupByDay,
  humanize,
  isRedacted,
  providerName,
  relativeTime,
  shortId,
} from "./format";

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

  it("groups conversations by their local calendar day", () => {
    const now = new Date("2026-07-07T12:00:00Z");
    const groups = groupByDay([
      { updated_at: "2026-07-07T08:00:00Z", id: "today" },
      { updated_at: "2026-07-06T08:00:00Z", id: "yesterday" },
      { updated_at: "2026-07-01T08:00:00Z", id: "older" },
    ], now);
    // Older days are labelled in the viewer's own locale, so the expected text
    // has to be derived the same way rather than hardcoded: "July 1, 2026" on a
    // en-US runner is "1 July 2026" on a en-GB one, and only the grouping is
    // under test here.
    const older = new Date("2026-07-01T08:00:00Z").toLocaleDateString(undefined, {
      weekday: "long", month: "long", day: "numeric", year: "numeric",
    });
    expect(groups.map((group) => group.label)).toEqual(["Today", "Yesterday", older]);
    expect(groups[0].items.map((item) => item.id)).toEqual(["today"]);
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
    expect(providerName("lm-studio-remote")).toBe("LM Studio (remote)");
    expect(providerName("ollama-cloud")).toBe("Ollama Cloud");
    expect(providerName("huggingface")).toBe("Hugging Face");
    expect(providerName("vllm")).toBe("vLLM");
    expect(providerName("anthropic")).toBe("Anthropic");
    // Named for the file the owner chose, not the server Raiker runs over it.
    expect(providerName("llama.cpp")).toBe("GGUF");
    expect(providerName("something-else")).toBe("something-else");
    expect(providerName(null)).toBe("—");
  });
});

// The API redacts secret-shaped values, and a randomly generated record id can
// be caught by that rule. A redacted id addresses nothing, so views must be
// able to tell the difference before offering a deep link.
describe("isRedacted", () => {
  it("recognises both server redaction markers", () => {
    expect(isRedacted("[REDACTED_SECRET]")).toBe(true);
    expect(isRedacted("***REDACTED***")).toBe(true);
  });

  it("treats a real id and an absent value as not redacted", () => {
    expect(isRedacted("sess_6cb389a696484e6b906ace63c7d5ad6d")).toBe(false);
    expect(isRedacted("")).toBe(false);
    expect(isRedacted(null)).toBe(false);
    expect(isRedacted(undefined)).toBe(false);
  });
});
