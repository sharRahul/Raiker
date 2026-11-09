/*
 * QUI-P03 — Allow with limits, as the owner edits and reads it; and the
 * permission broadcast every surface listens to (QUI-P02 acceptance).
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { formFromLimits, formProblem, grantSummary, limitRuleReason, limitsFromForm, splitTargets } from "./limitRules";
import { PERMISSIONS_CHANGED, announcePermissionsChanged, onPermissionsChanged } from "./permissionSync";

const DRAFT = {
  scope: "conversation" as const,
  targets: ["launch", "example.com"],
  max_uses: 10,
  expires_hours: 8,
  attachments: false,
  sensitive_asks: true,
};

describe("Allow with limits — the form", () => {
  it("round-trips the draft and splits targets on commas, semicolons and lines", () => {
    expect(limitsFromForm(formFromLimits(DRAFT))).toEqual(DRAFT);
    expect(splitTargets("a.com, b.com;\n#ops  ,")).toEqual(["a.com", "b.com", "#ops"]);
  });

  it("requires the limits the plan names before asking the server", () => {
    const form = formFromLimits(DRAFT);
    expect(formProblem(form)).toBeNull();
    expect(formProblem({ ...form, maxUses: 0 })).toMatch(/1 to 100/);
    expect(formProblem({ ...form, scope: "future", targets: "" })).toMatch(/name who or where/);
    expect(formProblem({ ...form, scope: "conversation", targets: "" })).toBeNull();
  });

  it("says why the runtime refused, and never pretends a rule was kept", () => {
    expect(limitRuleReason("grant_target_is_critical")).toMatch(/decided by you, every time/);
    expect(limitRuleReason("anything_else")).toMatch(/not kept/);
  });
});

describe("every grant list reads a rule the same way", () => {
  it("prefers a rule's limits in words, and keeps an older grant's pattern", () => {
    const base = { tool_name: "write_file", scope_pattern: "*", risk_ceiling: "medium", use_count: 1 };
    expect(grantSummary({ ...base, limits_words: ["Only in the conversation it was allowed in", "9 of 10 uses left"] })).toBe(
      "Only in the conversation it was allowed in · 9 of 10 uses left",
    );
    expect(grantSummary({ ...base, scope_pattern: "docs/*", limits_words: [] })).toBe(
      "On docs/* · up to medium risk · used 1 time",
    );
  });
});

describe("a permission changed in one place is announced to every surface", () => {
  afterEach(() => vi.restoreAllMocks());

  it("tells listeners on this page what changed, and stops when asked", () => {
    const heard: string[] = [];
    const stop = onPermissionsChanged((kind) => heard.push(kind));
    announcePermissionsChanged("rules");
    announcePermissionsChanged("modes");
    stop();
    announcePermissionsChanged("gates");
    expect(heard).toEqual(["rules", "modes"]);
  });

  it("uses one named event, so a surface can listen without importing a store", () => {
    const listener = vi.fn();
    window.addEventListener(PERMISSIONS_CHANGED, listener);
    announcePermissionsChanged("profile");
    window.removeEventListener(PERMISSIONS_CHANGED, listener);
    expect(listener).toHaveBeenCalledTimes(1);
  });
});
