import { describe, expect, it } from "vitest";
import { modelBetaStatus, runtimeBetaStatus, taskBetaStatus, withBetaStatus } from "./betaStatus";

describe("beta status vocabulary", () => {
  it("maps task states to the shared words", () => {
    expect(taskBetaStatus("queued")).toBe("Ready");
    expect(taskBetaStatus("running")).toBe("Working");
    expect(taskBetaStatus("waiting_for_approval")).toBe("Needs you");
    expect(taskBetaStatus("failed")).toBe("Failed");
    expect(taskBetaStatus("unknown")).toBe("Unavailable");
  });
  it("maps measured model and runtime states without claiming readiness", () => {
    expect(modelBetaStatus("ready")).toBe("Ready");
    expect(modelBetaStatus("checking")).toBe("Working");
    expect(modelBetaStatus("runtime_missing")).toBe("Unavailable");
    expect(modelBetaStatus("authentication_failed")).toBe("Failed");
    expect(runtimeBetaStatus("active")).toBe("Ready");
    expect(runtimeBetaStatus("suspended")).toBe("Needs you");
  });
  it("keeps a useful measured detail after the shared word", () => {
    expect(withBetaStatus("Unavailable", "Runtime stopped")).toBe("Unavailable · Runtime stopped");
  });
});
