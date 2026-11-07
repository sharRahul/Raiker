import { describe, expect, it } from "vitest";
import { isBetaSupportedProvider } from "./providerSupport";

describe("beta provider support (MD-1)", () => {
  it("supports the six live-checked providers", () => {
    for (const id of ["anthropic", "openai", "openrouter", "ollama", "lm-studio", "llama.cpp"]) {
      expect(isBetaSupportedProvider(id)).toBe(true);
    }
  });

  it("labels everything else experimental", () => {
    for (const id of ["gemini", "groq", "mistral", "vllm", "openai-compatible", "ollama-cloud"]) {
      expect(isBetaSupportedProvider(id)).toBe(false);
    }
  });
});
