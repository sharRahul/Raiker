import { describe, expect, it } from "vitest";
import { api } from "./api";
import { APPROVAL_MODES } from "./approvalMode";
import { stubFetch } from "./test-helpers";

describe("composer approval modes", () => {
  it("uses the exact operator labels and matching icons", () => {
    expect(
      APPROVAL_MODES.map(({ mode, label, menuLabel, icon }) => ({ mode, label, menuLabel, icon })),
    ).toEqual([
      { mode: "manual", label: "Manually approve", menuLabel: undefined, icon: "hand" },
      { mode: "auto", label: "Automatically approve", menuLabel: undefined, icon: "fast-forward" },
      { mode: "skip", label: "Skip", menuLabel: "Skip all approvals", icon: "warning" },
      {
        mode: "dont_ask",
        label: "Decline, don't ask",
        menuLabel: "Decline instead of asking",
        icon: "shield",
      },
    ]);
  });

  // BUG-219 — "Skip" and "Decline, don't ask" both mean "stop asking me" and do
  // opposite things: one runs the action without a decision, the other refuses
  // it. A label alone cannot carry that, so every mode owes the menu one line.
  it("gives every mode a detail line, and distinguishes skip from decline", () => {
    for (const option of APPROVAL_MODES) {
      expect(option.detail.length, option.mode).toBeGreaterThan(0);
    }
    const skip = APPROVAL_MODES.find((option) => option.mode === "skip");
    const decline = APPROVAL_MODES.find((option) => option.mode === "dont_ask");
    expect(skip?.detail).toMatch(/no approval is raised/i);
    expect(decline?.detail).toMatch(/refused, not queued/i);
  });

  it("reads and persists the approval mode at the dedicated settings endpoint", async () => {
    const fetch = stubFetch({
      "GET /api/settings/composer-approval-mode": { approval_mode: "manual" },
      "PUT /api/settings/composer-approval-mode": { approval_mode: "skip" },
    });

    await expect(api.composerApprovalMode()).resolves.toEqual({ approval_mode: "manual" });
    await expect(api.setComposerApprovalMode("skip")).resolves.toEqual({ approval_mode: "skip" });

    expect(fetch).toHaveBeenNthCalledWith(
      2,
      "/api/settings/composer-approval-mode",
      expect.objectContaining({ method: "PUT", body: JSON.stringify({ approval_mode: "skip" }) }),
    );
  });
});

// BUG-218 — Auto gained a deterministic second check, and the copy has to say
// so. An owner arriving from a product whose Auto reviews each action will read
// Raiker's the same way, and the promise the label makes has to be the one the
// runtime keeps.
describe("Auto's stated promise", () => {
  it("says a change to an unlooked-at file waits, rather than promising a review", () => {
    const auto = APPROVAL_MODES.find((m) => m.mode === "auto");
    expect(auto).toBeDefined();
    expect(auto?.detail).toMatch(/never looked at/i);
    expect(auto?.detail).toMatch(/waits/i);
    // Deliberately not "reviews each action for safety": the check is set
    // membership over the turn's own record, not a judgement about safety, and
    // copy that overclaims is the defect this closed.
    expect(auto?.detail).not.toMatch(/safety/i);
  });

  it("leaves Skip's promise exactly as it was", () => {
    // Skip is not alignment-checked. Its label says no approval is raised at
    // all, and attaching a silent second check would make that untrue.
    const skip = APPROVAL_MODES.find((m) => m.mode === "skip");
    expect(skip?.detail).toBe("No approval is raised at all. Gates and policy still apply.");
  });
});
