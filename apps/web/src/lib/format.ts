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

/** Group timestamped items by the viewer's local calendar day. */
export function groupByDay<T extends { updated_at: string }>(
  items: T[],
  now: Date = new Date(),
): Array<{ label: string; items: T[] }> {
  const groups = new Map<string, { label: string; items: T[] }>();
  for (const item of items) {
    const label = dayLabel(item.updated_at, now);
    const group = groups.get(label);
    if (group) group.items.push(item);
    else groups.set(label, { label, items: [item] });
  }
  return [...groups.values()];
}

function dayLabel(iso: string, now: Date): string {
  const then = parseTimestamp(iso);
  if (then === null) return "Unknown date";
  const key = (date: Date) => `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
  if (key(then) === key(now)) return "Today";
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (key(then) === key(yesterday)) return "Yesterday";
  return then.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" });
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

/**
 * True when the server replaced a value with a redaction marker.
 *
 * The API redacts any field whose value looks secret-shaped, which sometimes
 * catches a randomly generated record id. A redacted id cannot address
 * anything, so callers must render it as plain text rather than a link that
 * would take the user nowhere.
 */
export function isRedacted(value: string | null | undefined): boolean {
  if (!value) return false;
  return value.startsWith("[REDACTED") || value.startsWith("***REDACTED");
}

/**
 * Governed events that happened outside any conversation carry a scope name in
 * `session_id` rather than a session — `authz` for an authorization resolution,
 * which is what every CLI and dashboard read performs first.
 *
 * It is a real value, so a redaction check does not catch it, and the audit
 * timeline was rendering it as `#/sessions?session=authz`: a link to a session
 * that does not exist, under the word "session".
 */
const SESSION_SCOPE_MARKERS = new Set(["authz"]);

/** Whether `session_id` addresses a session a reader can actually open. */
export function isAddressableSession(value: string | null | undefined): boolean {
  if (!value) return false;
  return !isRedacted(value) && !SESSION_SCOPE_MARKERS.has(value);
}

/** "shell_execution" → "Shell execution". */
export function humanize(name: string | null | undefined): string {
  if (!name) return "—";
  const spaced = name.replaceAll("_", " ").trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

// Brand names for the model providers Raiker ships profiles for. Unknown
// providers render verbatim rather than guessing.
//
// llama.cpp is named for what the owner has rather than for the server that
// reads it: they chose a GGUF file, and Raiker runs the llama.cpp server over
// it on their behalf. The provider rows and the guide say so; a picker only
// needs the format.
const PROVIDER_NAMES: Record<string, string> = {
  "llama.cpp": "GGUF",
  mlx: "MLX",
  ollama: "Ollama",
  "ollama-cloud": "Ollama Cloud",
  "lm-studio": "LM Studio",
  "lm-studio-remote": "LM Studio (remote)",
  vllm: "vLLM",
  "openai-compatible": "OpenAI-compatible",
  openrouter: "OpenRouter",
  anthropic: "Anthropic",
  openai: "OpenAI",
  "chatgpt-codex": "ChatGPT subscription",
  gemini: "Gemini",
  huggingface: "Hugging Face",
};

/** "lm-studio" → "LM Studio"; unknown providers pass through unchanged. */
export function providerName(provider: string | null | undefined): string {
  if (!provider) return "—";
  return PROVIDER_NAMES[provider] ?? provider;
}
