// SPDX-License-Identifier: Apache-2.0
/**
 * Quiet UI 06 — the desktop window's helpers that are plain data: Quick Entry
 * (QUI-F01), the tray (QUI-F11) and a project in its own window (QUI-F13).
 *
 * Kept apart from `main.ts` so each rule can be tested without Electron. None
 * of them can act on the workspace: the page still does every action over HTTP
 * through the host's governance. These only decide what a window shows and
 * where it sits.
 */

/** The global shortcut that opens Quick Entry from anywhere on the computer. */
export const QUICK_ENTRY_SHORTCUT = "CommandOrControl+Shift+Space";

/** The Quick Entry window's size (QUI-F01): one input and a "send to" picker. */
export const QUICK_ENTRY_SIZE = { width: 560, height: 120 } as const;

export interface Area {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** Centred across the display the pointer is on, a quarter of the way down. */
export function quickEntryBounds(workArea: Area): Area {
  const { width, height } = QUICK_ENTRY_SIZE;
  return {
    x: Math.round(workArea.x + (workArea.width - width) / 2),
    y: Math.round(workArea.y + workArea.height / 4),
    width,
    height,
  };
}

/**
 * A page asks for one of Raiker's own places to open in a window of its own
 * (QUI-F13): only an in-app route hash, never a URL, so the window it opens
 * shows the same origin and nothing else.
 */
export function isAppHash(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length <= 512 &&
    /^#\/[A-Za-z0-9/_\-?=&%.]*$/.test(value) &&
    !value.includes("//")
  );
}

/** A count of decisions waiting, as the page reports it; anything else is none. */
export function attentionCount(value: unknown): number {
  return typeof value === "number" && Number.isInteger(value) && value > 0 ? Math.min(value, 999) : 0;
}

/** The tray's tooltip: what is true now, in words (status never by colour alone). */
export function trayTooltip(waiting: number): string {
  if (waiting === 0) return "Raiker";
  return `Raiker — ${waiting} ${waiting === 1 ? "decision is" : "decisions are"} waiting for you`;
}

/**
 * Paint the attention dot onto a copy of the tray icon's bitmap (BGRA or RGBA,
 * four bytes a pixel): a filled circle in the top-right corner, with a light
 * ring so it reads on dark and light trays alike.
 */
export function withDot(bitmap: Uint8Array, width: number, height: number): Uint8Array {
  const out = new Uint8Array(bitmap);
  const radius = Math.max(2, Math.round(width * 0.22));
  const cx = width - radius - 1;
  const cy = radius + 1;
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const distance = Math.hypot(x - cx, y - cy);
      if (distance > radius + 1) continue;
      const i = (y * width + x) * 4;
      // An amber-red that reads as "needs you" in BGRA and close enough in RGBA.
      const ring = distance > radius;
      out[i] = ring ? 255 : 40;
      out[i + 1] = ring ? 255 : 60;
      out[i + 2] = ring ? 255 : 220;
      out[i + 3] = 255;
    }
  }
  return out;
}
