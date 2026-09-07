import { describe, expect, it } from "vitest";
import { approvalBadge, responseBadge, taskBadge, taskStatusLabel } from "./statusMaps";

describe("status → badge maps", () => {
  it("maps task statuses", () => {
    expect(taskBadge("running")).toBe("active");
    expect(taskBadge("queued")).toBe("active");
    expect(taskBadge("completed")).toBe("done");
    expect(taskBadge("cancelled")).toBe("stopped");
    expect(taskBadge("mystery")).toBe("idle");
    // A run parked on a decision has not failed; it must not wear a stopped badge.
    expect(taskBadge("waiting_for_approval")).toBe("needs-approval");
  });

  it("reads task statuses as English and never hides an unknown one", () => {
    expect(taskStatusLabel("waiting_for_approval")).toBe("waiting for approval");
    expect(taskStatusLabel("cancelling")).toBe("stopping");
    expect(taskStatusLabel("running")).toBe("running");
    expect(taskStatusLabel("mystery")).toBe("mystery");
  });

  it("maps approval statuses", () => {
    expect(approvalBadge("pending")).toBe("needs-approval");
    expect(approvalBadge("approved")).toBe("done");
    expect(approvalBadge("denied")).toBe("stopped");
    expect(approvalBadge("expired")).toBe("stopped");
    expect(approvalBadge("weird")).toBe("idle");
  });

  it("maps agent response statuses", () => {
    expect(responseBadge("completed")).toBe("done");
    expect(responseBadge("needs_approval")).toBe("needs-approval");
    expect(responseBadge("denied")).toBe("stopped");
    expect(responseBadge("failed")).toBe("stopped");
    expect(responseBadge("running")).toBe("active");
  });
});
