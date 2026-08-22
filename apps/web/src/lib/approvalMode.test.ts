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
