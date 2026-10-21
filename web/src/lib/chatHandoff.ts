/**
 * QUI-H01 — Home's composer hands its message to Chat.
 *
 * Chat listens for `raiker:compose` while it is mounted, but it mounts only on
 * its first visit. An event dispatched before that fires into an empty room, so
 * the message also waits here as a one-shot request Chat takes when it mounts
 * (the same pattern `scheduleHandoff.ts` uses for Tasks). Whichever side takes
 * it first sends it; the other finds nothing. Home never sends a prompt itself:
 * there is one governed send path, Chat's `submit()`.
 */
let pending: string | null = null;

export const COMPOSE_EVENT = "raiker:compose";

/** Give `text` to Chat: to the mounted Chat now, or to the next one that mounts. */
export function handOffToChat(text: string): void {
  const message = text.trim();
  if (message === "") return;
  pending = message;
  window.dispatchEvent(
    new CustomEvent(COMPOSE_EVENT, { detail: { text: message, sessionId: null, fromHandoff: true } }),
  );
}

/** Take the waiting message, if any. Reading it clears it. */
export function takeChatHandoff(): string | null {
  const message = pending;
  pending = null;
  return message;
}
