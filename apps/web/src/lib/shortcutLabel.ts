/**
 * VIS2-04 — how a key combination is spelled on the machine reading it.
 *
 * The top bar printed `Ctrl K` to every owner, including the ones whose
 * keyboard has no Ctrl in that position. That is not a cosmetic mismatch: a
 * shortcut hint is an instruction, and on macOS the instruction was wrong. The
 * palette's own handler has always accepted either modifier, so the label was
 * the only part that had an opinion about the platform.
 *
 * One module, so a second surface cannot arrive at a fourth spelling. The
 * platform is read once at module load — a keyboard does not change under a
 * running page, and reading it per render would make every hint a reactive
 * dependency on nothing.
 */

/**
 * True on Apple platforms.
 *
 * `navigator.platform` is deprecated and `userAgentData` is not everywhere, so
 * both are consulted and neither is required: a host that answers with nothing
 * gets the Windows/Linux spelling, which is the majority and the safe default —
 * an owner on a Mac who sees `Ctrl` can still press `Cmd`, because the handler
 * accepts both.
 */
function detectApple(): boolean {
  if (typeof navigator === "undefined") return false;
  const data = (navigator as { userAgentData?: { platform?: string } }).userAgentData;
  const platform = data?.platform ?? navigator.platform ?? navigator.userAgent ?? "";
  return /mac|iphone|ipad|ipod/i.test(platform);
}

export const isApplePlatform = detectApple();

/** The modifier Raiker's global shortcuts use, spelled for this platform. */
export const primaryModifier = isApplePlatform ? "⌘" : "Ctrl";

/** The secondary modifier, for the few bindings that need one. */
export const altModifier = isApplePlatform ? "⌥" : "Alt";

/**
 * A key combination, written the way this platform writes it.
 *
 * `shortcutLabel("mod", "K")` is `⌘K` on macOS and `Ctrl K` elsewhere. The
 * separator differs on purpose: Apple's own conventions set the modifier
 * glyphs tight against the key, and a space between `⌘` and `K` reads as two
 * separate things to press.
 */
export function shortcutLabel(...parts: string[]): string {
  const spelled = parts.map((part) =>
    part === "mod" ? primaryModifier : part === "alt" ? altModifier : part,
  );
  return spelled.join(isApplePlatform ? "" : " ");
}

/**
 * The same combination for a screen reader, which must not be handed a glyph.
 *
 * `⌘` is announced as "place of interest sign" by some screen readers and as
 * nothing at all by others, so an `aria-label` gets the word.
 */
export function shortcutSpoken(...parts: string[]): string {
  const spelled = parts.map((part) =>
    part === "mod"
      ? isApplePlatform
        ? "Command"
        : "Control"
      : part === "alt"
        ? isApplePlatform
          ? "Option"
          : "Alt"
        : part,
  );
  return spelled.join(" ");
}
