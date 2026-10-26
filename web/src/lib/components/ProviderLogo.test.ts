import { fireEvent, render } from "@testing-library/svelte";
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

const officialAsset = new Map([
  ["anthropic", "/provider-logos/anthropic.svg"],
  ["ollama", "/provider-logos/ollama.svg"],
  ["ollama-cloud", "/provider-logos/ollama.svg"],
  ["openrouter", "/provider-logos/openrouter.svg"],
  ["huggingface", "/provider-logos/huggingface.svg"],
  ["openai", "/provider-logos/openai.svg"],
  ["gemini", "/provider-logos/google.ico"],
]);

describe("ProviderLogo", () => {
  it("renders a fallback mark when the provider image fails to load", async () => {
    const { getByRole } = render(ProviderLogo, { provider: "anthropic" });
    const logo = getByRole("img", { name: "Anthropic logo" });
    await fireEvent.error(logo.querySelector("img")!);
    expect(logo.querySelector("img")).toBeNull();
    expect(logo.querySelector("svg")).not.toBeNull();
  });
  it.each(configuredProviders)("renders a provider mark for %s", (provider) => {
    const { getByRole } = render(ProviderLogo, { provider });
    const logo = getByRole("img", { name: /logo$/i });
    const source = officialAsset.get(provider);
    if (source) expect(logo.querySelector("img")).toHaveAttribute("src", source);
    else expect(logo.querySelector("svg")).not.toBeNull();
  });
});
