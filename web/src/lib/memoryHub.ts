/*
 * The Memory hub's own reading of what it holds.
 *
 * Memory had approved records, proposals, relationship proposals,
 * observations, a document library, two recall controls and an import/export
 * drawer at one visual level. Every one of those is a real capability; the
 * fault was that the page made an owner tell administration from content by
 * reading all of it, and the one thing that might need them today — a proposal
 * waiting for a decision — looked exactly like the settings above it.
 *
 * Overview answers the two questions people actually arrive with: *is anything
 * waiting on me*, and *what does Raiker remember*. This module derives both, so
 * the counts on the Overview and the counts on each tab cannot disagree.
 */

export const MEMORY_TABS = ["overview", "memories", "suggestions", "sources", "recall"] as const;
export type MemoryTab = (typeof MEMORY_TABS)[number];

export const MEMORY_TAB_LABELS: Record<MemoryTab, string> = {
  overview: "Overview",
  memories: "Memories",
  suggestions: "Suggestions",
  sources: "Sources",
  recall: "Recall & indexing",
};

export interface MemoryCounts {
  approved: number;
  pinned: number;
  expired: number;
  proposals: number;
  relationshipProposals: number;
  observations: number;
}

export interface MemoryAttention {
  /** What is waiting, in the owner's words. */
  label: string;
  /** How many of them. */
  count: number;
  /** The tab that can act on it. */
  tab: MemoryTab;
}

/**
 * What is waiting on a decision.
 *
 * Only decisions. An expired memory is not waiting on anyone — it has already
 * stopped being recalled — so it is a fact on the Overview rather than a row in
 * the attention list. Nothing here is an exception the owner cannot act on.
 */
export function memoryAttention(counts: MemoryCounts): MemoryAttention[] {
  const waiting: MemoryAttention[] = [];
  if (counts.proposals > 0) {
    waiting.push({
      label: counts.proposals === 1 ? "memory proposed" : "memories proposed",
      count: counts.proposals,
      tab: "suggestions",
    });
  }
  if (counts.relationshipProposals > 0) {
    waiting.push({
      label:
        counts.relationshipProposals === 1
          ? "relationship proposed"
          : "relationships proposed",
      count: counts.relationshipProposals,
      tab: "suggestions",
    });
  }
  return waiting;
}

/**
 * The one sentence at the top: what Raiker remembers, and whether anything
 * needs the owner. Written so that the empty case is a real answer rather than
 * a count of zero.
 */
export function memorySentence(counts: MemoryCounts): string {
  if (counts.approved === 0) {
    return "Raiker remembers nothing yet. Approved memories are the only thing it can recall.";
  }
  const remembers = `Raiker can recall ${counts.approved} approved memor${counts.approved === 1 ? "y" : "ies"}`;
  const pinned = counts.pinned > 0 ? `, ${counts.pinned} pinned` : "";
  const waiting = memoryAttention(counts).reduce((total, entry) => total + entry.count, 0);
  const decisions =
    waiting === 0
      ? ". Nothing is waiting on you."
      : ` — and ${waiting} suggestion${waiting === 1 ? "" : "s"} waiting on your decision.`;
  return `${remembers}${pinned}${decisions}`;
}

/** The tab a memory-shaped thing is administered on. */
export function tabFor(kind: "memory" | "proposal" | "observation" | "document" | "setting"): MemoryTab {
  switch (kind) {
    case "proposal":
    case "observation":
      return "suggestions";
    case "document":
      return "sources";
    case "setting":
      return "recall";
    default:
      return "memories";
  }
}
