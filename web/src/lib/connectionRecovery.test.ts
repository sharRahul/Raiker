import { describe, expect, it } from "vitest";
import { ApiError } from "./api";
import { connectionFailure } from "./connectionRecovery";

describe("connectionFailure", () => {
  it("retains safe read-back guidance after a lost write response", () => {
    const message = connectionFailure("Could not save", "The saved state is unconfirmed.", "Check the list before saving again.", new TypeError("private payload"));
    expect(message).toContain("Raiker did not answer");
    expect(message).toContain("Check the list before saving again");
    expect(message).not.toMatch(/Nothing was changed|private payload|did not reach/);
  });

  it("keeps HTTP evidence and actionable credential refusal guidance", () => {
    const message = connectionFailure("Could not enable Gmail", "Session access is unconfirmed.", "Refresh connections.", new ApiError(403, "connector_reauth_required", "private payload"));
    expect(message).toContain("HTTP 403, connector_reauth_required");
    expect(message).toContain("Connect the account again");
    expect(message).toContain("Refresh connections");
    expect(message).not.toContain("private payload");
  });
});
