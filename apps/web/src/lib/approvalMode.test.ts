import { describe, expect, it } from "vitest";
import { api } from "./api";
import { APPROVAL_MODES } from "./approvalMode";
import { stubFetch } from "./test-helpers";

describe("composer approval modes", () => {
  it("uses the exact operator labels and matching icons", () => {
    expect(APPROVAL_MODES).toEqual([
      { mode: "manual", label: "Manually approve", icon: "hand" },
      { mode: "auto", label: "Automatically approve", icon: "fast-forward" },
      { mode: "skip", label: "Skip", icon: "warning" },
    ]);
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
