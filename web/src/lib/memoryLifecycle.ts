/*
 * UX-MEM-02, UX-MEM-03 and UX-MEM-06 — one memory lifecycle, read one way.
 *
 * Forget, archive, expiry and permanent deletion were four controls whose
 * meanings sat close together and were said in four places in four ways. This
 * module is the one statement of them the Memory page, the record drawer and
 * the guide use, and it derives the two overview readings — what is about to
 * lapse, and where every record is in the pipeline — from the same list, so
 * neither can disagree with the records it counts.
 *
 * Nothing here decides recall. The server alone decides what a turn is given;
 * these are words and counts over what it already reported.
 */
import type { MemoryControlView } from "./apiTypes";

/** A lifecycle verb, the consequence it has, and whether it can be undone. */
export interface LifecycleVerb {
  label: string;
  consequence: string;
  reversible: boolean;
}

/**
 * The verbs, in the order an owner meets them. The same words are used on the
 * record drawer, in the guide's *Memory* chapter and in the audit history, so
 * "archive" never means one thing on one screen and another on the next.
 */
export const LIFECYCLE_VERBS = {
  archive: {
    label: "Archive",
    consequence:
      "Raiker stops recalling it and keeps it. Restore brings it back exactly as it was.",
    reversible: true,
  },
  restore: {
    label: "Restore",
    consequence: "Raiker may recall it again, in the scope it had before it was archived.",
    reversible: true,
  },
  expire: {
    label: "Review expiry",
    consequence:
      "On its review date it stops being recalled and waits here for you to extend, archive or remove it. Age alone never deletes anything.",
    reversible: true,
  },
  forget: {
    label: "Forget",
    consequence:
      "Erases the words and keeps a tombstone, so the audit history can still say a memory existed. Cannot be undone.",
    reversible: false,
  },
  purge: {
    label: "Delete permanently",
    consequence:
      "Removes the record and its derived copies after you type its id. Retained backups are not erased at once.",
    reversible: false,
  },
} as const satisfies Record<string, LifecycleVerb>;

/** Where one record stands, in the owner's words. */
export type MemoryState = "current" | "expires_soon" | "stale" | "expired" | "archived";

export const MEMORY_STATE_LABELS: Record<MemoryState, string> = {
  current: "Current",
  expires_soon: "Expires soon",
  stale: "Stale — review",
  expired: "Expired",
  archived: "Archived",
};

const DAY_MS = 86_400_000;
/** A review date this close is "soon". */
export const EXPIRES_SOON_DAYS = 14;
/**
 * Unused, unedited and older than this, a record is put up for review. A
 * prompt to look, never a deletion: old does not mean wrong, and a pinned
 * record ages like any other because a pin is not proof it is still true.
 */
export const STALE_AFTER_DAYS = 90;

function time(value: string | null | undefined): number | null {
  if (!value) return null;
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? null : parsed;
}

/** One state per record, the most pressing first. */
export function memoryState(memory: MemoryControlView, now: number = Date.now()): MemoryState {
  if (memory.archived_at) return "archived";
  const expires = time(memory.expires_at);
  if (expires !== null && expires <= now) return "expired";
  if (expires !== null && expires - now <= EXPIRES_SOON_DAYS * DAY_MS) return "expires_soon";
  const staleBefore = now - STALE_AFTER_DAYS * DAY_MS;
  const lastTouched = Math.max(
    time(memory.created_at) ?? 0,
    time(memory.updated_at) ?? 0,
    time(memory.last_used_at) ?? 0,
  );
  if (lastTouched > 0 && lastTouched < staleBefore) return "stale";
  return "current";
}

/** Whether a turn may still be given this record. Archived and expired may not. */
export function isRecallable(memory: MemoryControlView, now: number = Date.now()): boolean {
  const state = memoryState(memory, now);
  return state !== "archived" && state !== "expired";
}

export interface RetentionSummary {
  /** Recallable, with no review date: kept until the owner changes that. */
  permanent: number;
  expiresSoon: number;
  stale: number;
  expired: number;
  archived: number;
}

/** UX-MEM-03 — the policy-level reading of what the records say one by one. */
export function retentionSummary(
  memories: MemoryControlView[],
  now: number = Date.now(),
): RetentionSummary {
  const summary: RetentionSummary = { permanent: 0, expiresSoon: 0, stale: 0, expired: 0, archived: 0 };
  for (const memory of memories) {
    const state = memoryState(memory, now);
    if (state === "archived") summary.archived += 1;
    else if (state === "expired") summary.expired += 1;
    else if (state === "expires_soon") summary.expiresSoon += 1;
    else {
      if (state === "stale") summary.stale += 1;
      if (!memory.expires_at) summary.permanent += 1;
    }
  }
  return summary;
}

/** The Memories tab's list filters, and the ones a summary row links to. */
export const MEMORY_FILTERS = ["active", "expires-soon", "stale", "expired", "archived", "all"] as const;
export type MemoryFilter = (typeof MEMORY_FILTERS)[number];

export const MEMORY_FILTER_LABELS: Record<MemoryFilter, string> = {
  active: "Recallable",
  "expires-soon": "Expires soon",
  stale: "Stale — review",
  expired: "Expired",
  archived: "Archived",
  all: "All records",
};

export function isMemoryFilter(value: string | null | undefined): value is MemoryFilter {
  return (MEMORY_FILTERS as readonly string[]).includes(value ?? "");
}

export function matchesFilter(
  memory: MemoryControlView,
  filter: MemoryFilter,
  now: number = Date.now(),
): boolean {
  const state = memoryState(memory, now);
  switch (filter) {
    case "all":
      return true;
    case "active":
      return state !== "archived" && state !== "expired";
    case "expires-soon":
      return state === "expires_soon";
    case "stale":
      return state === "stale";
    case "expired":
      return state === "expired";
    case "archived":
      return state === "archived";
  }
}

/** One row of the retention summary, with the filter that lists its records. */
export interface RetentionRow {
  label: string;
  count: number;
  filter: MemoryFilter;
  note: string;
}

export function retentionRows(summary: RetentionSummary): RetentionRow[] {
  return [
    {
      label: "Kept until you change it",
      count: summary.permanent,
      filter: "active",
      note: "No review date. Raiker recalls these whenever they are relevant.",
    },
    {
      label: "Expires soon",
      count: summary.expiresSoon,
      filter: "expires-soon",
      note: `Review date within ${EXPIRES_SOON_DAYS} days. Extend, archive or let it lapse.`,
    },
    {
      label: "Stale — worth a look",
      count: summary.stale,
      filter: "stale",
      note: `Not recalled or edited in ${STALE_AFTER_DAYS} days. Still recalled; nothing is removed for being old.`,
    },
    {
      label: "Expired",
      count: summary.expired,
      filter: "expired",
      note: "Past their review date, so no longer recalled. Extend one to bring it back.",
    },
    {
      label: "Archived",
      count: summary.archived,
      filter: "archived",
      note: "Kept and not recalled. Restore brings one back.",
    },
  ];
}

/** UX-MEM-06 — one stage of the pipeline every memory passes through. */
export interface PipelineStage {
  id: "observed" | "suggested" | "approved" | "recalled" | "lapsed";
  label: string;
  count: number | null;
  meaning: string;
  /** Where the records at this stage are administered. */
  href: string;
}

export interface PipelineInputs {
  /** `null` when capture could not be asked — not the same as none. */
  observations: number | null;
  suggestions: number;
  memories: MemoryControlView[];
}

/**
 * Observed → suggested → approved → recalled → expired or archived.
 *
 * The pipeline is the answer to "how did this get here and why is Raiker using
 * it". Each count is a different set, so the stages are not a funnel: a record
 * observed once may be suggested never, and an approved record you wrote
 * yourself was never observed at all.
 */
export function memoryPipeline(inputs: PipelineInputs, now: number = Date.now()): PipelineStage[] {
  const recallable = inputs.memories.filter((memory) => isRecallable(memory, now));
  const recalled = recallable.filter(
    (memory) => (memory.recall_turn_count ?? 0) > 0 || Boolean(memory.last_used_at),
  );
  const lapsed = inputs.memories.length - recallable.length;
  return [
    {
      id: "observed",
      label: "Observed",
      count: inputs.observations,
      meaning: "What Raiker noted while it worked — a checksum and where it came from, never the material.",
      href: "#/memory?tab=suggestions",
    },
    {
      id: "suggested",
      label: "Suggested",
      count: inputs.suggestions,
      meaning: "Sentences Raiker proposed remembering. Nothing here is recalled until you approve it.",
      href: "#/memory?tab=suggestions",
    },
    {
      id: "approved",
      label: "Approved",
      count: recallable.length,
      meaning: "What Raiker may recall: what you approved, wrote, corrected or imported.",
      href: "#/memory?tab=memories&filter=active",
    },
    {
      id: "recalled",
      label: "Recalled",
      count: recalled.length,
      meaning: "Approved records a turn has been given. Being given one is not proof the answer used it.",
      href: "#/memory?tab=memories&filter=active",
    },
    {
      id: "lapsed",
      label: "Expired or archived",
      count: lapsed,
      meaning: "Kept, and no longer recalled. Restore or extend one to bring it back.",
      href: "#/memory?tab=memories&filter=all",
    },
  ];
}
