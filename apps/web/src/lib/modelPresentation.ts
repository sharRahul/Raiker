/** Display labels for provider-owned identifiers; the raw identifier still goes to the API. */
export function modelName(model: string): string {
  // Routed catalogues often prefix the provider (for example
  // `meta-llama/Llama-3.3-70B-Instruct`). The provider has its own mark in the
  // picker, so keep the model portion concise.
  const identifier = model.split("/").at(-1) ?? model;
  const claude = /^claude-(haiku|sonnet|opus)-(\d+)(?:-(\d+))?(?:-\d{8})?$/i.exec(identifier);
  if (claude) {
    const family = claude[1].charAt(0).toUpperCase() + claude[1].slice(1).toLowerCase();
    const version = claude[3] ? `${claude[2]}.${claude[3]}` : claude[2];
    return `${family} ${version}`;
  }

  const datedClaude = /^claude-(\d+)(?:-(\d+))?-(haiku|sonnet|opus)(?:-\d{8})?$/i.exec(identifier);
  if (datedClaude) {
    const version = datedClaude[2] ? `${datedClaude[1]}.${datedClaude[2]}` : datedClaude[1];
    return `${word(datedClaude[3])} ${version}`;
  }

  const gemma = /^gemma(\d+):(\d+)([bm])(?:-(.+))?$/i.exec(identifier);
  if (gemma) {
    const suffix = gemma[4] ? ` ${words(gemma[4])}` : "";
    return `Gemma ${gemma[1]}:${gemma[2]}${gemma[3].toUpperCase()}${suffix}`;
  }

  const gemini = /^gemini-(\d+(?:\.\d+)*)(?:-(flash(?:-lite)?|pro|ultra))?/i.exec(identifier);
  if (gemini) return `Gemini ${gemini[1]}${gemini[2] ? ` ${words(gemini[2])}` : ""}`;

  const gpt = /^gpt-(\d+(?:\.\d+)?[a-z]?)(?:-(.+))?$/i.exec(identifier);
  if (gpt) return `GPT-${gpt[1].toLowerCase()}${gpt[2] ? ` ${words(gpt[2])}` : ""}`;

  const reasoning = /^o(\d+)(?:-(.+))?$/i.exec(identifier);
  if (reasoning) return `o${reasoning[1]}${reasoning[2] ? ` ${words(reasoning[2])}` : ""}`;

  return words(identifier);
}

function words(value: string): string {
  return value
    .replace(/^meta-llama-/i, "")
    .replace(/([a-z]{2,})(\d)/gi, "$1 $2")
    .replace(/[_-]+/g, " ")
    .split(/\s+/)
    .filter(Boolean)
    .map(word)
    .join(" ");
}

function word(value: string): string {
  if (/^\d+(?:\.\d+)?[bm]$/i.test(value)) return value.toUpperCase();
  if (/^[a-z]\d+:\d+[bm]$/i.test(value)) return `${value.charAt(0).toUpperCase()}${value.slice(1, -1)}${value.at(-1)?.toUpperCase()}`;
  if (/^.+:\d+[bm]$/i.test(value)) return value.replace(/[bm]$/i, (size) => size.toUpperCase());

  const known: Record<string, string> = {
    ai: "AI",
    deepseek: "DeepSeek",
    gguf: "GGUF",
    gpt: "GPT",
    llm: "LLM",
  };
  return known[value.toLowerCase()] ?? `${value.charAt(0).toUpperCase()}${value.slice(1).toLowerCase()}`;
}

/**
 * The models in a provider's catalogue that could answer a turn (BUG-258).
 *
 * "Choose where Raiker thinks" listed OpenAI's whole catalogue — 124 entries —
 * and *defaulted* to `text-embedding-ada-002`, because the list arrives in the
 * provider's own order and the first entry wins. An owner who accepted the
 * default pinned a model that cannot answer anything, and found out at their
 * first turn.
 *
 * This is not a capability guess. Every pattern below is the provider's own
 * naming for a different endpoint family — embeddings, speech, images,
 * moderation — none of which serve a chat completion. Anything a provider names
 * outside those families is left in, so a new or unusual chat model is never
 * hidden by a rule written before it existed.
 *
 * When the filter would empty the list, the unfiltered list is returned
 * instead: a picker that offers nothing is worse than one that offers too much,
 * and a provider whose entire catalogue looks like this is a provider this rule
 * does not understand.
 */
const NOT_A_CHAT_MODEL = [
  /(^|[/\-_])text-embedding/i,
  /(^|[/\-_])embed(ding)?([-_.]|$)/i,
  /(^|[/\-_])whisper/i,
  /(^|[/\-_])tts([-_.]|$)/i,
  /(^|[/\-_])dall-e/i,
  /(^|[/\-_])moderation/i,
  /(^|[/\-_])rerank/i,
  /(^|[/\-_])sora/i,
];

export function chatCandidates(models: string[]): string[] {
  const kept = models.filter(
    (model) => !NOT_A_CHAT_MODEL.some((pattern) => pattern.test(model)),
  );
  return kept.length > 0 ? kept : models;
}
