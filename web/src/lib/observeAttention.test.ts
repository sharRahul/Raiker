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
});
