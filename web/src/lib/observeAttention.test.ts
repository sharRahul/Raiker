import { describe, expect, it } from "vitest";
import { allClearSentence, attentionItems, type AttentionInputs } from "./observeAttention";
import type { ApprovalView, Diagnostics, SecurityHealth } from "./apiTypes";

const HEALTHY_DIAGNOSTICS = {
  runtime_mode: "local_single_user",
  production_ready_local_single_user_runtime: true,
  summary: {},
  disabled_capabilities: [],
  counts: {},
  readiness: {},
  missing_config: [],
  provider_health: [],
  background_workers: [],
  search_indexes: [],
  scheduler_queue: { due: 0, oldest_due_at: null, oldest_wait_seconds: null, host_paused: false },
  model_profile_source: { kind: "packaged", location: "raiker" },
  scope_note: "",
} as unknown as Diagnostics;

function approval(overrides: Partial<ApprovalView>): ApprovalView {
  return { approval_id: "ap_1", is_expired: false, ...overrides } as ApprovalView;
}

function signal(overrides: Partial<SecurityHealth>): SecurityHealth {
  return {
    source: "containment",
    subject_id: "web_fetch",
    code: "rate_exceeded",
    state: "idle",
    finding_id: null,
    updated_at: "2026-09-18T10:00:00Z",
    ...overrides,
  };
}

const EVERYTHING_FINE: AttentionInputs = {
  diagnostics: HEALTHY_DIAGNOSTICS,
  approvals: [],
  security: [],
  unreadNotifications: 0,
};

describe("attentionItems", () => {
  it("has nothing to say about a healthy install", () => {
    expect(attentionItems(EVERYTHING_FINE)).toEqual([]);
  });

  // The rule REM-HOME-02 settled for Home, held here: a running task is
  // progress, and an overview that counts it as attention is permanently red.
  it("does not treat a read it was not given as an exception", () => {
    expect(attentionItems({ ...EVERYTHING_FINE, unreadNotifications: 0 })).toEqual([]);
  });

  it("puts containment first, above everything else that is wrong", () => {
    const items = attentionItems({
      diagnostics: { ...HEALTHY_DIAGNOSTICS, missing_config: ["RAIKER_VAULT_KEY"] },
      approvals: [approval({ is_expired: true })],
      security: [signal({ state: "alerting" })],
      unreadNotifications: 3,
    });
    expect(items[0].tone).toBe("containment");
    expect(items[0].title).toContain("rate exceeded");
  });

  it("separates an expired approval from a live one, because they are different jobs", () => {
    const items = attentionItems({
      ...EVERYTHING_FINE,
      approvals: [approval({ approval_id: "a", is_expired: true }), approval({ approval_id: "b" })],
    });
    const titles = items.map((item) => item.title);
    expect(titles).toContain("1 approval expired");
    expect(titles).toContain("1 decision waiting on you");
  });

  // NEW-HOME-01, from the other side: a failed read must never become zero, and
  // zero must never become an all-clear.
  it("reports a failed read as unknown rather than as healthy", () => {
    const items = attentionItems({
      diagnostics: null,
      approvals: null,
      security: null,
      unreadNotifications: null,
    });
    expect(items.every((item) => item.tone === "unknown")).toBe(true);
    expect(items.map((item) => item.id).sort()).toEqual([
      "unknown:approvals",
      "unknown:diagnostics",
      "unknown:security",
    ]);
  });

  it("names unmet readiness and unset configuration separately", () => {
    const items = attentionItems({
      ...EVERYTHING_FINE,
      diagnostics: {
        ...HEALTHY_DIAGNOSTICS,
        production_ready_local_single_user_runtime: false,
        missing_config: ["RAIKER_VAULT_KEY", "RAIKER_OWNER_TOKEN"],
      },
    });
    const titles = items.map((item) => item.title);
    expect(titles).toContain("Readiness checks are unmet");
    expect(titles).toContain("2 required settings are unset");
  });

  // BUG-322 — a damaged index was named only inside Diagnostics' fold.
  it("names a damaged search index above the fold, with the way to its repair", () => {
    const checked = { checked_at: "2026-10-05T10:00:00Z", first_damaged_at: "2026-10-05T10:00:00Z" };
    const items = attentionItems({
      ...EVERYTHING_FINE,
      diagnostics: {
        ...HEALTHY_DIAGNOSTICS,
        search_indexes: [
          { index_name: "conversation_fts", label: "Conversation search", state: "damaged", damaged_count: 1, ...checked },
          { index_name: "vector_records", label: "Search by meaning", state: "damaged", damaged_count: 3, ...checked },
          { index_name: "approved_memory_fts", label: "Memory search", state: "ok", damaged_count: 0, ...checked, first_damaged_at: null },
        ],
      },
    });
    expect(items.map((item) => item.title)).toEqual([
      "Conversation search is damaged",
      "Search by meaning is damaged",
    ]);
    expect(items.every((item) => item.tone === "blocking")).toBe(true);
    expect(items[0].href).toBe("#/observe?tab=overview&repair=indexes");
    expect(items[0].linkLabel).toBe("Rebuild it");
    expect(items[1].detail).toMatch(/3 stored vectors could not be read/);
    expect(items[1].linkLabel).toBe("Remove damaged vectors");
  });
});

describe("allClearSentence", () => {
  it("names everything the all-clear covers", () => {
    expect(allClearSentence(EVERYTHING_FINE)).toBe(
      "Nothing needs you. Checked: containment, readiness and configuration, " +
        "pending decisions and notifications.",
    );
  });

  it("does not claim to have checked what it could not read", () => {
    const sentence = allClearSentence({ ...EVERYTHING_FINE, security: null });
    expect(sentence).not.toContain("containment");
    expect(sentence).toContain("readiness and configuration");
  });

  it("says plainly when it read nothing at all", () => {
    expect(
      allClearSentence({
        diagnostics: null,
        approvals: null,
        security: null,
        unreadNotifications: null,
      }),
    ).toBe("Nothing could be read, so nothing can be said about it yet.");
  });

  // DEC-24 step 1 — the scheduler's queue depth and age.
  it("names overdue scheduled work on a running host, and waiting work while paused", () => {
    const fresh = attentionItems({
      ...EVERYTHING_FINE,
      diagnostics: { ...HEALTHY_DIAGNOSTICS, scheduler_queue: { due: 2, oldest_due_at: "x", oldest_wait_seconds: 20, host_paused: false } },
    });
    expect(fresh).toEqual([]);
    const stuck = attentionItems({
      ...EVERYTHING_FINE,
      diagnostics: { ...HEALTHY_DIAGNOSTICS, scheduler_queue: { due: 2, oldest_due_at: "x", oldest_wait_seconds: 900, host_paused: false } },
    });
    expect(stuck.map((item) => [item.title, item.tone])).toEqual([["2 scheduled tasks overdue", "blocking"]]);
    expect(stuck[0].detail).toMatch(/due 15 minutes ago/);
    const paused = attentionItems({
      ...EVERYTHING_FINE,
      diagnostics: { ...HEALTHY_DIAGNOSTICS, scheduler_queue: { due: 1, oldest_due_at: "x", oldest_wait_seconds: 900, host_paused: true } },
    });
    expect(paused.map((item) => [item.title, item.tone])).toEqual([["1 scheduled task is waiting while Raiker is paused", "waiting"]]);
  });
});
