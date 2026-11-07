/**
 * Which key sends a prompt (QUI-C04, 2026-11-07).
 *
 * `enter`, the default: Enter sends and Shift + Enter starts a new line.
 * `mod_enter`: Enter starts a new line and Ctrl + Enter (⌘ + Enter on a Mac)
 * sends, for owners who write long, multi-paragraph instructions and do not
 * want a half-written one sent by a stray Enter. Stored per account as
 * `personalisation.send_key`; presentation only, it changes nothing a turn may do.
 */
export type SendKey = "enter" | "mod_enter";

export const SEND_KEY_SETTING = "personalisation.send_key";

export function sendKeyFrom(settings: Record<string, unknown>): SendKey {
  return settings[SEND_KEY_SETTING] === "mod_enter" ? "mod_enter" : "enter";
}

/** True when this keydown should send the prompt under `mode`. Never mid-IME composition. */
export function isSendKeystroke(event: KeyboardEvent, mode: SendKey): boolean {
  if (event.key !== "Enter" || event.isComposing || event.shiftKey) return false;
  if (mode === "mod_enter") return event.ctrlKey || event.metaKey;
  return true;
}

function isMac(): boolean {
  return typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform ?? "");
}

/** The modifier's name on this computer. */
export function modifierName(): string {
  return isMac() ? "⌘" : "Ctrl";
}

/** One line naming the send and new-line keys, for a composer's hint and title. */
export function sendHint(mode: SendKey): string {
  return mode === "mod_enter"
    ? `${modifierName()} + Enter to send · Enter for a new line`
    : "Enter to send · Shift + Enter for a new line";
}
