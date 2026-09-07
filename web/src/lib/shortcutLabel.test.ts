// VIS2-04 — a shortcut hint is an instruction, so it has to be right on the
// machine reading it. The top bar printed `Ctrl K` to every owner including the
// ones whose keyboard has no Ctrl in that position; the palette's handler has
// always accepted either modifier, so the label was the only part with an
// opinion about the platform, and it was wrong half the time.
//
// The module reads the platform once at load, so each case re-imports it with
// the navigator it is asserting about rather than trying to mutate a constant.
import { afterEach, describe, expect, it, vi } from "vitest";

async function load(platform: string) {
  vi.resetModules();
  vi.stubGlobal("navigator", { platform, userAgent: platform });
  return import("./shortcutLabel");
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("platform shortcut labels", () => {
  it("writes the Apple modifier as a glyph, set tight against the key", async () => {
    const { shortcutLabel, isApplePlatform, primaryModifier } = await load("MacIntel");
    expect(isApplePlatform).toBe(true);
    expect(primaryModifier).toBe("⌘");
    expect(shortcutLabel("mod", "K")).toBe("⌘K");
  });

  it("writes the Windows/Linux modifier as a word, spaced from the key", async () => {
    const { shortcutLabel, isApplePlatform, primaryModifier } = await load("Win32");
    expect(isApplePlatform).toBe(false);
    expect(primaryModifier).toBe("Ctrl");
    expect(shortcutLabel("mod", "K")).toBe("Ctrl K");
  });

  it("falls back to the Windows spelling when the platform cannot be read", async () => {
    // Not a guess dressed as knowledge: the majority spelling, and an owner on
    // a Mac who reads `Ctrl K` can still press Cmd because the handler takes
    // both. The reverse — printing `⌘K` on Windows — names a key that is not
    // on the keyboard at all.
    const { shortcutLabel } = await load("");
    expect(shortcutLabel("mod", "K")).toBe("Ctrl K");
  });

  it("never hands a screen reader a modifier glyph", async () => {
    // `⌘` is announced as "place of interest sign" by some screen readers and
    // as nothing at all by others, so the accessible name gets the word.
    const apple = await load("iPhone");
    expect(apple.shortcutSpoken("mod", "K")).toBe("Command K");
    expect(apple.shortcutSpoken("alt", "Enter")).toBe("Option Enter");

    const windows = await load("Win32");
    expect(windows.shortcutSpoken("mod", "K")).toBe("Control K");
    expect(windows.shortcutSpoken("alt", "Enter")).toBe("Alt Enter");
  });

  it("passes plain keys through unchanged on both platforms", async () => {
    for (const platform of ["MacIntel", "Win32"]) {
      const { shortcutLabel } = await load(platform);
      expect(shortcutLabel("Esc")).toBe("Esc");
      expect(shortcutLabel("Enter")).toBe("Enter");
    }
  });
});
