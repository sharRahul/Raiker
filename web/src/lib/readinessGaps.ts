/**
 * QUI-Q01 — a readiness gap as a sentence and the one action that fixes it.
 *
 * Home showed every gap as a tile reading "Runtime issues · 1": a large number
 * and a sentence about "readiness evidence" that named neither the problem nor
 * the fix. On a fresh workspace the one gap is that no model is chosen, and the
 * owner had to open Diagnostics to find that out.
 *
 * The runtime already writes each gap as a sentence
 * (`raiker/control/dashboard_parts/models.py`, `_missing_config`). The gaps an
 * owner meets in ordinary use get plainer wording and their own fix; any other
 * gap keeps the runtime's sentence and links to Diagnostics, so nothing the
 * runtime reports is ever hidden. `readinessGaps.test.ts` checks that every
 * sentence matched here still exists in the runtime, so a reworded gap fails a
 * test instead of quietly losing its fix.
 */

export interface GapAction {
  readonly label: string;
  readonly href: string;
}

export interface ReadinessGap {
  readonly id: string;
  readonly title: string;
  readonly action: GapAction;
}

const DIAGNOSTICS: GapAction = { label: "Open diagnostics", href: "#/observe?tab=diagnostics" };

/** The runtime's own sentences this file gives plainer wording and a fix. */
export const KNOWN_GAPS: Readonly<Record<string, { title: string; action: GapAction }>> = {
  // The runtime's gap is the *default* model: the one tasks, goals and a chat
  // with no choice of its own run on. A Chat with its own model still answers,
  // so "no model is set up" was untrue once one was connected (found live,
  // RT-QUI-07). Models is where a default is connected and chosen.
  "No model profile is selected.": {
    title: "No default model is chosen.",
    action: { label: "Choose a model", href: "#/models" },
  },
  "No runtime mode is active.": {
    title: "Raiker is not accepting work right now.",
    action: DIAGNOSTICS,
  },
};

/**
 * The rows Home draws for the runtime's readiness.
 *
 * `missing` is the runtime's list of gaps; `ready` is its overall verdict. A
 * runtime that is not ready but names no gap still gets one row, because "not
 * ready" with nothing to read is exactly the state an owner cannot act on.
 */
export function readinessGaps(missing: readonly string[], ready: boolean): ReadinessGap[] {
  const rows = missing.map((sentence, index): ReadinessGap => {
    const known = KNOWN_GAPS[sentence];
    return {
      id: `gap-${index}`,
      title: known?.title ?? sentence,
      action: known?.action ?? DIAGNOSTICS,
    };
  });
  if (rows.length === 0 && !ready) {
    rows.push({ id: "gap-not-ready", title: "Raiker is not ready to run work.", action: DIAGNOSTICS });
  }
  return rows;
}
