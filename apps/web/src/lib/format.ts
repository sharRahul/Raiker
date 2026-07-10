// Small display formatters. Pure functions, no side effects.

/** Compact relative time ("just now", "4m ago", "2h ago", "3d ago"), else a local date. */
export function relativeTime(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return "—";
  const then = parseTimestamp(iso);
  if (then === null) return iso;
  const seconds = Math.floor((now.getTime() - then.getTime()) / 1000);
  if (seconds < 0) return formatTimestamp(iso);
  if (seconds < 45) return "just now";
  if (seconds < 3600) return `${Math.max(1, Math.floor(seconds / 60))}m ago`;
  if (seconds < 86_400) return `${Math.floor(seconds / 3600)}h ago`;
  if (seconds < 7 * 86_400) return `${Math.floor(seconds / 86_400)}d ago`;
  return then.toLocaleDateString();
}

/** Full local timestamp for detail rows; falls back to the raw string. */
export function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return "—";
  const then = parseTimestamp(iso);
  return then === null ? iso : then.toLocaleString();
}

function parseTimestamp(iso: string): Date | null {
  const value = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`);
  return Number.isNaN(value.getTime()) ? null : value;
}

/** Shorten machine ids for display: "sess_a1b2c3d4e5" → "sess_a1b2…". */
export function shortId(id: string | null | undefined, keep = 10): string {
  if (!id) return "—";
  return id.length <= keep + 1 ? id : `${id.slice(0, keep)}…`;
}

/** "shell_execution" → "Shell execution". */
export function humanize(name: string | null | undefined): string {
  if (!name) return "—";
  const spaced = name.replaceAll("_", " ").trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

// Brand names for the model providers Raiker ships profiles for. Unknown
// providers render verbatim rather than guessing.
const PROVIDER_NAMES: Record<string, string> = {
  "llama.cpp": "llama.cpp",
  ollama: "Ollama",
  "lm-studio": "LM Studio",
  vllm: "vLLM",
  "openai-compatible": "OpenAI-compatible",
  openrouter: "OpenRouter",
  anthropic: "Anthropic",
  openai: "OpenAI",
  gemini: "Gemini",
};

/** "lm-studio" → "LM Studio"; unknown providers pass through unchanged. */
export function providerName(provider: string | null | undefined): string {
  if (!provider) return "—";
  return PROVIDER_NAMES[provider] ?? provider;
}
