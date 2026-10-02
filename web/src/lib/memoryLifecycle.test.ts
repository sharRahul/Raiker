import { describe, expect, it } from "vitest";
import type { MemoryControlView } from "./apiTypes";
import {
  LIFECYCLE_VERBS,
  isMemoryFilter,
  isRecallable,
  matchesFilter,
  memoryPipeline,
  memoryState,
  retentionRows,
  retentionSummary,
} from "./memoryLifecycle";

const NOW = Date.parse("2026-10-02T12:00:00Z");
const DAY = 86_400_000;

function memory(overrides: Partial<MemoryControlView> = {}): MemoryControlView {
  return {
    memory_id: "mem_1",
    text: "A fact.",
    scope: "project",
    sensitivity: "normal",
    memory_type: "project",
    created_at: new Date(NOW - DAY).toISOString(),
    tags: [],
    source: "agent",
    provenance: {},
    confidence: 0.9,
    trust_score: 0.8,
    retention: "until_forget",
    approval_state: "approved",
    pinned: false,
    search_enabled: true,
    expires_at: null,
    archived_at: null,
    source_event_id: "",
    created_by: "",
    valid_from: null,
    valid_until: null,
    supersedes_memory_id: null,
    remembered_reason: null,
    updated_at: null,
    last_used_at: null,
    recall_turn_count: 0,
    last_recalled_session_id: null,
    last_recalled_turn_id: null,
    last_recalled_origin: null,
    ...overrides,
  };
}

describe("memoryState (UX-MEM-02/03)", () => {
  it("names the most pressing state first", () => {
    expect(memoryState(memory(), NOW)).toBe("current");
    expect(memoryState(memory({ archived_at: "2026-09-01T00:00:00Z", expires_at: "2000-01-01T00:00:00Z" }), NOW)).toBe("archived");
    expect(memoryState(memory({ expires_at: new Date(NOW - 1).toISOString() }), NOW)).toBe("expired");
    expect(memoryState(memory({ expires_at: new Date(NOW + 3 * DAY).toISOString() }), NOW)).toBe("expires_soon");
    expect(memoryState(memory({ expires_at: new Date(NOW + 30 * DAY).toISOString() }), NOW)).toBe("current");
  });

  it("calls a record stale only when nothing has touched it in ninety days", () => {
    const old = new Date(NOW - 120 * DAY).toISOString();
    expect(memoryState(memory({ created_at: old }), NOW)).toBe("stale");
    // Being recalled, or edited, recently is being touched.
    expect(memoryState(memory({ created_at: old, last_used_at: new Date(NOW - DAY).toISOString() }), NOW)).toBe("current");
    expect(memoryState(memory({ created_at: old, updated_at: new Date(NOW - DAY).toISOString() }), NOW)).toBe("current");
    // A pin is not proof a fact is still true; it ages like any other.
    expect(memoryState(memory({ created_at: old, pinned: true }), NOW)).toBe("stale");
  });

  it("treats archived and expired as not recallable, and stale as still recallable", () => {
    expect(isRecallable(memory({ archived_at: "2026-09-01T00:00:00Z" }), NOW)).toBe(false);
    expect(isRecallable(memory({ expires_at: "2000-01-01T00:00:00Z" }), NOW)).toBe(false);
    expect(isRecallable(memory({ created_at: new Date(NOW - 200 * DAY).toISOString() }), NOW)).toBe(true);
  });
});

describe("retentionSummary (UX-MEM-03)", () => {
  it("counts each record once, by policy", () => {
    const summary = retentionSummary(
      [
        memory(),
        memory({ expires_at: new Date(NOW + 2 * DAY).toISOString() }),
        memory({ created_at: new Date(NOW - 100 * DAY).toISOString() }),
        memory({ expires_at: "2000-01-01T00:00:00Z" }),
        memory({ archived_at: "2026-09-01T00:00:00Z" }),
      ],
      NOW,
    );
    expect(summary).toEqual({ permanent: 2, expiresSoon: 1, stale: 1, expired: 1, archived: 1 });
    const rows = retentionRows(summary);
    expect(rows.map((row) => row.filter)).toEqual(["active", "expires-soon", "stale", "expired", "archived"]);
    // No row promises a grace period Raiker does not have.
    expect(rows.some((row) => /pending deletion/i.test(row.label))).toBe(false);
  });

  it("filters the list by the same states", () => {
    const archived = memory({ archived_at: "2026-09-01T00:00:00Z" });
    expect(matchesFilter(archived, "active", NOW)).toBe(false);
    expect(matchesFilter(archived, "archived", NOW)).toBe(true);
    expect(matchesFilter(archived, "all", NOW)).toBe(true);
    expect(isMemoryFilter("stale")).toBe(true);
    expect(isMemoryFilter("approved")).toBe(false);
  });
});

describe("memoryPipeline (UX-MEM-06)", () => {
  it("reads observed, suggested, approved, recalled and lapsed from what the page holds", () => {
    const stages = memoryPipeline(
      {
        observations: 7,
        suggestions: 2,
        memories: [
          memory({ recall_turn_count: 3 }),
          memory(),
          memory({ archived_at: "2026-09-01T00:00:00Z", recall_turn_count: 9 }),
        ],
      },
      NOW,
    );
    expect(stages.map((stage) => [stage.id, stage.count])).toEqual([
      ["observed", 7],
      ["suggested", 2],
      ["approved", 2],
      ["recalled", 1],
      ["lapsed", 1],
    ]);
  });

  it("says it does not know rather than zero when capture could not be asked", () => {
    expect(memoryPipeline({ observations: null, suggestions: 0, memories: [] }, NOW)[0].count).toBeNull();
  });
});

describe("LIFECYCLE_VERBS (UX-MEM-02)", () => {
  it("separates the reversible verbs from the two that are not", () => {
    expect(LIFECYCLE_VERBS.archive.reversible).toBe(true);
    expect(LIFECYCLE_VERBS.restore.reversible).toBe(true);
    expect(LIFECYCLE_VERBS.forget.reversible).toBe(false);
    expect(LIFECYCLE_VERBS.purge.reversible).toBe(false);
    expect(LIFECYCLE_VERBS.purge.label).toBe("Delete permanently");
  });
});
