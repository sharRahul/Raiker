import { describe, expect, it } from "vitest";
import type { TurnMemoryDisclosure } from "./apiTypes";
import {
  RECALL_MODE_OPTIONS,
  disclosureDetail,
  disclosureShort,
  disclosureSummary,
  quietDisclosure,
  recallModeLabel,
  retrievalBackendLabel,
} from "./memoryRecallMode";

function disclosure(overrides: Partial<TurnMemoryDisclosure> = {}): TurnMemoryDisclosure {
  return {
    turn_id: "turn_1",
    recall_mode: "search_when_relevant",
    effective_mode: "search_when_relevant",
    incognito: false,
    retrieval_backend: "memory-brief-v1 + sqlite-fts5 + raiker-local-hash-v1",
    brief_version: "memory-brief-v1",
    brief_count: 2,
    brief_omitted: 0,
    recall_count: 1,
    ...overrides,
  };
}

describe("memory recall mode", () => {
  it("offers the three modes in order", () => {
    expect(RECALL_MODE_OPTIONS.map((option) => option.value)).toEqual([
      "off",
      "brief",
      "search_when_relevant",
    ]);
    expect(recallModeLabel("brief")).toBe("Brief only");
    expect(recallModeLabel("unknown")).toBe("Off");
  });

  it("names only the search parts of the backend", () => {
    expect(retrievalBackendLabel("memory-brief-v1 + sqlite-fts5 + raiker-local-hash-v1")).toBe(
      "sqlite-fts5 + raiker-local-hash-v1",
    );
    expect(retrievalBackendLabel("memory-brief-v1")).toBe("the memory brief");
    expect(retrievalBackendLabel("none")).toBe("nothing");
  });

  it("says what ran, and that Incognito overrode the setting", () => {
    expect(disclosureSummary(disclosure())).toBe("Memory: Brief + search");
    expect(disclosureSummary(disclosure({ effective_mode: "brief", recall_mode: "brief" }))).toBe(
      "Memory: Brief only",
    );
    expect(disclosureSummary(disclosure({ effective_mode: "off", recall_mode: "off" }))).toBe(
      "Memory off for this answer",
    );
    const incognito = disclosure({ effective_mode: "off", incognito: true, retrieval_backend: "none" });
    expect(disclosureSummary(incognito)).toBe("Memory not used: Incognito is on");
    expect(disclosureDetail(incognito)).toBe(
      "Recall mode: Search when relevant · Incognito on, so nothing was recalled",
    );
  });

  it("has a two-word form for beside the count", () => {
    expect(disclosureShort(disclosure())).toBe("Brief + search");
    expect(disclosureShort(disclosure({ effective_mode: "off", incognito: true }))).toBe("Incognito");
  });

  it("reports what the brief's budget left out", () => {
    expect(disclosureDetail(disclosure({ brief_omitted: 3 }))).toContain(
      "3 approved memories left out of the brief by its budget",
    );
    expect(disclosureDetail(disclosure({ brief_omitted: 1 }))).toContain("1 approved memory left out");
  });

  it("words an answer that recalled nothing", () => {
    expect(quietDisclosure(disclosure())).toBe(
      "Memory: Brief + search · nothing recalled · searched sqlite-fts5 + raiker-local-hash-v1",
    );
    expect(quietDisclosure(disclosure({ effective_mode: "brief", recall_mode: "brief", retrieval_backend: "memory-brief-v1" }))).toBe(
      "Memory: Brief only · nothing recalled",
    );
    expect(quietDisclosure(disclosure({ effective_mode: "off", recall_mode: "off" }))).toBe(
      "Memory off for this answer",
    );
  });
});
