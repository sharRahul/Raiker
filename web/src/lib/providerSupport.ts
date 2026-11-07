/**
 * Beta plan MD-1 — which model providers the beta supports.
 *
 * The six with a recorded live check per release: three hosted (Anthropic,
 * OpenAI, OpenRouter) and three local (Ollama, LM Studio, the managed
 * llama.cpp engine). Every other provider still works through its connector,
 * but is labelled *Experimental* in the Add list so a listing never reads as
 * a support commitment.
 */
export const BETA_SUPPORTED_PROVIDERS: ReadonlySet<string> = new Set([
  "anthropic",
  "openai",
  "openrouter",
  "ollama",
  "lm-studio",
  "llama.cpp",
]);

export function isBetaSupportedProvider(provider: string): boolean {
  return BETA_SUPPORTED_PROVIDERS.has(provider);
}

export const EXPERIMENTAL_PROVIDER_NOTE =
  "Experimental: not part of the beta's live-checked providers. It may work, but it is not verified for this release.";
