import { describe, expect, it } from "vitest";
import { api } from "./api";
import { APPROVAL_MODES } from "./approvalMode";
import { stubFetch } from "./test-helpers";

describe("shared approval postures", () => {
  it("offers confined preparation, asking, and unattended refusal without a bypass", () => {
    expect(APPROVAL_MODES.map((item) => item.mode)).toEqual(["sandbox", "manual", "dont_ask"]);
    expect(APPROVAL_MODES[0].detail).toMatch(/verified task copy/);
    expect(APPROVAL_MODES[0].detail).toMatch(/Ask before changing the real project/);
    expect(APPROVAL_MODES[2].detail).toMatch(/refused, not queued/);
  });

  it("persists the same sandbox posture through the shared settings endpoint", async () => {
    const fetch = stubFetch({
      "GET /api/settings/composer-approval-mode": { approval_mode: "manual" },
      "PUT /api/settings/composer-approval-mode": { approval_mode: "sandbox" },
    });
    await expect(api.composerApprovalMode()).resolves.toEqual({ approval_mode: "manual" });
    await expect(api.setComposerApprovalMode("sandbox")).resolves.toEqual({ approval_mode: "sandbox" });
    expect(fetch).toHaveBeenNthCalledWith(2, "/api/settings/composer-approval-mode",
      expect.objectContaining({ method: "PUT", body: JSON.stringify({ approval_mode: "sandbox" }) }));
  });
});
