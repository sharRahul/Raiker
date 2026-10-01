import { afterEach, describe, expect, it } from "vitest";
import type { ModelsView } from "./apiTypes";
import { chatProfiles, modelsKnown, resetModels, setModels } from "./models.svelte";

afterEach(() => resetModels());

describe("modelsKnown", () => {
  // Found live 2026-10-01: before the first read landed, every composer said
  // "No model is set up" on an instance with a model pinned. Not knowing is not
  // an answer, and the composers ask this before they give one.
  it("is false until the first read lands, and true after, even when it is empty", () => {
    expect(modelsKnown()).toBe(false);
    expect(chatProfiles()).toEqual([]);
    setModels({ profiles: [], chat_profiles: [] } as unknown as ModelsView);
    expect(modelsKnown()).toBe(true);
    resetModels();
    expect(modelsKnown()).toBe(false);
  });
});
