import { render } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import ProviderLogo from "./ProviderLogo.svelte";

const configuredProviders = [
  "llama.cpp",
  "ollama",
  "ollama-cloud",
  "lm-studio",
  "openai-compatible",
  "openrouter",
  "huggingface",
  "anthropic",
  "openai",
  "gemini",
];

describe("ProviderLogo", () => {
  it.each(configuredProviders)("renders a provider mark for %s", (provider) => {
    const { getByRole } = render(ProviderLogo, { provider });
    expect(getByRole("img", { name: /logo$/i }).querySelector("svg")).not.toBeNull();
  });
});
