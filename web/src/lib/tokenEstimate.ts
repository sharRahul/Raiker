/**
 * A labelled token estimate for the composer (QUI-C04, 2026-11-07).
 *
 * Raiker talks to models with different tokenizers, so a count shown before a
 * turn runs is an estimate and always says so (≈). Four characters per token is
 * the common English rule of thumb and errs a little high for code. A PDF, Word
 * or spreadsheet file is not read until the turn, so it has no estimate here:
 * showing one would be a guess presented as a measurement.
 */
import type { ComposerAttachment } from "./composerAttachments.svelte";

const CHARS_PER_TOKEN = 4;

/** Text media types whose size is their text, so bytes estimate tokens. */
const TEXT_TYPES = new Set(["text/plain", "text/markdown", "text/csv", "application/json"]);

export function estimateTextTokens(text: string): number {
  return text.length === 0 ? 0 : Math.ceil(text.length / CHARS_PER_TOKEN);
}

/** ≈ tokens for one attachment, or null when it cannot be estimated before the turn. */
export function estimateAttachmentTokens(attachment: ComposerAttachment): number | null {
  if (attachment.pastedText !== undefined) return estimateTextTokens(attachment.pastedText);
  if (attachment.kind !== "document" || !attachment.byteSize) return null;
  if (!TEXT_TYPES.has(attachment.mediaType ?? "")) return null;
  return Math.ceil(attachment.byteSize / CHARS_PER_TOKEN);
}

/** The draft plus every attachment that can be estimated. */
export function estimateDraftTokens(text: string, attachments: readonly ComposerAttachment[]): number {
  return attachments.reduce((sum, item) => sum + (estimateAttachmentTokens(item) ?? 0), estimateTextTokens(text));
}

/** "≈ 1.2k tokens", "≈ 640 tokens". */
export function formatTokenEstimate(tokens: number): string {
  const short = tokens < 1000 ? String(tokens) : tokens < 1_000_000 ? `${(tokens / 1000).toFixed(tokens < 10_000 ? 1 : 0)}k` : `${(tokens / 1_000_000).toFixed(1)}M`;
  return `≈ ${short} tokens`;
}

/** The share of a context window above which the composer warns (QUI-C04). */
export const CONTEXT_WARNING_SHARE = 0.8;

/** The warning sentence when `used` passes 80 % of `window`, else null. */
export function contextWarning(used: number, window: number | null | undefined): string | null {
  if (!window || used <= window * CONTEXT_WARNING_SHARE) return null;
  const share = Math.min(100, Math.round((used / window) * 100));
  return share >= 100
    ? "This prompt and conversation are larger than the model's context window. Remove files or start a new chat, or the answer may be cut short."
    : `With what you are adding, this prompt is about ${share}% of the model's context window. The answer may be cut short; remove files you do not need.`;
}
