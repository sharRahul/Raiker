import { describe, expect, it } from "vitest";
import { approvalBadge, responseBadge, taskBadge } from "./statusMaps";

describe("status → badge maps", () => {
  it("maps task statuses", () => {
    expect(taskBadge("running")).toBe("active");
    expect(taskBadge("queued")).toBe("active");
    expect(taskBadge("completed")).toBe("done");
    expect(taskBadge("cancelled")).toBe("stopped");
    expect(taskBadge("mystery")).toBe("idle");
  });

  it("maps approval statuses", () => {
    expect(approvalBadge("pending")).toBe("needs-approval");
    expect(approvalBadge("approved")).toBe("done");
    expect(approvalBadge("denied")).toBe("stopped");
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
