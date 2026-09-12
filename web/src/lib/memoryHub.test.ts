import { describe, expect, it } from "vitest";
import {
  MEMORY_TAB_LABELS,
  MEMORY_TABS,
  memoryAttention,
  memorySentence,
  tabFor,
  type MemoryCounts,
} from "./memoryHub";

function counts(partial: Partial<MemoryCounts> = {}): MemoryCounts {
  return {
    approved: 0,
    pinned: 0,
    expired: 0,
    proposals: 0,
    relationshipProposals: 0,
    observations: 0,
    ...partial,
  };
}

describe("what the Memory hub says it holds", () => {
  it("names a panel for every tab it declares", () => {
    for (const tab of MEMORY_TABS) {
      expect(MEMORY_TAB_LABELS[tab], `${tab} has no label`).toBeTruthy();
    }
    expect(MEMORY_TABS[0]).toBe("overview");
  });

  it("counts only what an owner can decide as waiting on them", () => {
    // An expired memory has already stopped being recalled; nobody is blocked
    // on it. Calling it attention would make the list say "act on this" about
    // something with nothing to act on.
    expect(memoryAttention(counts({ expired: 9, observations: 20 }))).toEqual([]);
    const waiting = memoryAttention(counts({ proposals: 2, relationshipProposals: 1 }));
    expect(waiting.map((entry) => entry.count)).toEqual([2, 1]);
    expect(new Set(waiting.map((entry) => entry.tab))).toEqual(new Set(["suggestions"]));
  });

  it("says a real sentence when there is nothing to remember", () => {
    expect(memorySentence(counts())).toMatch(/remembers nothing yet/i);
  });

  it("says what is recallable and whether anything is waiting", () => {
    expect(memorySentence(counts({ approved: 1 }))).toBe(
      "Raiker can recall 1 approved memory. Nothing is waiting on you.",
    );
    expect(memorySentence(counts({ approved: 4, pinned: 2, proposals: 3 }))).toBe(
      "Raiker can recall 4 approved memories, 2 pinned — and 3 suggestions waiting on your decision.",
    );
  });

  it("sends each kind of thing to the tab that administers it", () => {
    expect(tabFor("memory")).toBe("memories");
    expect(tabFor("proposal")).toBe("suggestions");
    expect(tabFor("observation")).toBe("suggestions");
    expect(tabFor("document")).toBe("sources");
    expect(tabFor("setting")).toBe("recall");
  });
});
