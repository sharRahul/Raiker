/**
 * DW-11 — a Design handoff waiting for Build's composer.
 *
 * Design makes the handoff document server-side (an ordinary owner attachment);
 * this holds it until Build is opened, which then carries it like any other
 * attached document. Taking it empties the slot, so it is attached once. It is
 * context for the next Build turn and nothing more: Build's modes and
 * approvals still decide every change.
 */
import type { ComposerAttachment } from "./composerAttachments.svelte";

let waiting = $state<ComposerAttachment | null>(null);

export function offerDesignHandoff(attachment: ComposerAttachment): void {
  waiting = attachment;
}

export function pendingDesignHandoff(): ComposerAttachment | null {
  return waiting;
}

export function takeDesignHandoff(): ComposerAttachment | null {
  const taken = waiting;
  waiting = null;
  return taken;
}
