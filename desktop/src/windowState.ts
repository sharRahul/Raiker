// SPDX-License-Identifier: Apache-2.0
/**
 * Where the window was, so it opens there again.
 *
 * Stored as a small JSON file in the shell's own user-data directory — window
 * geometry only, never anything from the Raiker workspace. A saved position on
 * a monitor that has since been unplugged is discarded rather than opening the
 * window somewhere the owner cannot see it.
 */
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface WindowState {
  bounds: Partial<Rect> & { width: number; height: number };
  maximized: boolean;
}

export const DEFAULT_STATE: WindowState = { bounds: { width: 1280, height: 820 }, maximized: false };
export const MIN_SIZE = { width: 720, height: 520 };

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

/** True when at least a usable corner of `bounds` is inside a work area. */
function visibleOn(bounds: Rect, areas: readonly Rect[]): boolean {
  const grip = 48;
  return areas.some(
    (area) =>
      bounds.x + grip <= area.x + area.width &&
      bounds.x + bounds.width - grip >= area.x &&
      bounds.y >= area.y - grip &&
      bounds.y + grip <= area.y + area.height,
  );
}

/** A state that is safe to open with on the current displays. */
export function sanitizeState(raw: unknown, workAreas: readonly Rect[]): WindowState {
  if (typeof raw !== "object" || raw === null) return DEFAULT_STATE;
  const record = raw as Record<string, unknown>;
  const bounds = (record.bounds ?? {}) as Record<string, unknown>;
  if (!isFiniteNumber(bounds.width) || !isFiniteNumber(bounds.height)) return DEFAULT_STATE;
  const largest = workAreas.reduce(
    (best, area) => ({ width: Math.max(best.width, area.width), height: Math.max(best.height, area.height) }),
    { width: DEFAULT_STATE.bounds.width, height: DEFAULT_STATE.bounds.height },
  );
  const width = Math.round(Math.min(Math.max(bounds.width, MIN_SIZE.width), largest.width));
  const height = Math.round(Math.min(Math.max(bounds.height, MIN_SIZE.height), largest.height));
  const maximized = record.maximized === true;
  if (isFiniteNumber(bounds.x) && isFiniteNumber(bounds.y)) {
    const placed = { x: Math.round(bounds.x), y: Math.round(bounds.y), width, height };
    if (visibleOn(placed, workAreas)) return { bounds: placed, maximized };
  }
  return { bounds: { width, height }, maximized };
}

export function loadState(file: string, workAreas: readonly Rect[]): WindowState {
  try {
    return sanitizeState(JSON.parse(readFileSync(file, "utf-8")), workAreas);
  } catch {
    return DEFAULT_STATE;
  }
}

export function saveState(file: string, state: WindowState): void {
  try {
    mkdirSync(dirname(file), { recursive: true });
    writeFileSync(file, `${JSON.stringify(state)}\n`, "utf-8");
  } catch {
    // Geometry is a convenience. Failing to remember it must never stop a quit.
  }
}
