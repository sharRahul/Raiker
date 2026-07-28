import { describe, expect, it } from "vitest";
import { modelName } from "./modelPresentation";

describe("modelName", () => {
  it("turns provider model identifiers into concise product names", () => {
    expect(modelName("gemma4:31b-cloud")).toBe("Gemma 4:31B Cloud");
    expect(modelName("claude-haiku-4-5-20251001")).toBe("Haiku 4.5");
    expect(modelName("claude-opus-4-1-20250805")).toBe("Opus 4.1");
  });

  it("keeps unrecognised identifiers readable without changing them at the API boundary", () => {
    expect(modelName("reasoning-model")).toBe("Reasoning Model");
  });
});
