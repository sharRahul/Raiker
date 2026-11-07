/**
 * Add to prompt (QUI-C04, 2026-11-07) — an earlier answer, pinned into the
 * next prompt as a context chip instead of copied and pasted.
 *
 * A pin is carried as quoted text at the top of the prompt that is sent, so
 * the transcript shows exactly what the model was given. It grants nothing:
 * the quote is the owner's own conversation, and it rides as their words.
 */
export interface PromptPin {
  /** The answer's turn, so the same answer is not pinned twice. */
  turnId: string;
  /** What the chip says: "Answer 3". */
  label: string;
  text: string;
}

/** The most of one answer a pin carries; a longer one is cut and says so. */
export const MAX_PIN_CHARS = 6000;

export function addPin(pins: readonly PromptPin[], pin: PromptPin): PromptPin[] {
  return pins.some((held) => held.turnId === pin.turnId) ? [...pins] : [...pins, pin];
}

function quoted(text: string): string {
  const bounded = text.length > MAX_PIN_CHARS ? `${text.slice(0, MAX_PIN_CHARS)}\n[…cut at ${MAX_PIN_CHARS} characters]` : text;
  return bounded.split("\n").map((line) => `> ${line}`).join("\n");
}

/** The prompt as sent: each pinned answer quoted above what the owner typed. */
export function withPins(text: string, pins: readonly PromptPin[]): string {
  if (pins.length === 0) return text;
  const context = pins.map((pin) => `Context from ${pin.label.toLowerCase()} in this conversation:\n${quoted(pin.text.trim())}`);
  return `${context.join("\n\n")}\n\n${text}`;
}
