/** Display labels for provider-owned identifiers; the raw identifier still goes to the API. */
export function modelName(model: string): string {
  const claude = /^claude-(haiku|sonnet|opus)-(\d+)(?:-(\d+))?(?:-\d{8})?$/i.exec(model);
  if (claude) {
    const family = claude[1].charAt(0).toUpperCase() + claude[1].slice(1).toLowerCase();
    const version = claude[3] ? `${claude[2]}.${claude[3]}` : claude[2];
    return `${family} ${version}`;
  }

  const gemma = /^gemma(\d+):(\d+)([bm])(?:-(.+))?$/i.exec(model);
  if (gemma) {
    const suffix = gemma[4] ? ` ${words(gemma[4])}` : "";
    return `Gemma ${gemma[1]}:${gemma[2]}${gemma[3].toUpperCase()}${suffix}`;
  }

  return words(model)
    .replace(/\bGpt\b/g, "GPT")
    .replace(/\bAi\b/g, "AI")
    .replace(/\bLlm\b/g, "LLM");
}

function words(value: string): string {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
