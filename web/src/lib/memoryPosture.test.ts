import { describe, expect, it } from "vitest";
import { memoryWritePosture } from "./memoryPosture";

describe("memory writing permissions", () => {
  it("distinguishes memory tools from lessons kept by the memory controls", () => {
    const posture = memoryWritePosture([{
      capability: "memory_write_execution", state: "disabled", decision_mode: "ask",
    }]);
    expect(posture.headline).toContain("Memory tools are off");
    expect(posture.headline).toContain("lessons");
    expect(posture.headline).not.toContain("cannot propose memories");
  });
});
