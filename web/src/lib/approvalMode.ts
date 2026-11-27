import type { IconName } from "./icons";

export type ApprovalMode = "manual" | "sandbox" | "dont_ask";

/**
 * One shared preparation default, with explicit asking and unattended refusal.
 *
 * `dont_ask` is the unattended one (BUG-219): anything not already permitted by
 * a standing rule is **declined** rather than queued. It is the posture for a
 * scheduled run or a background agent. Verified preparation may proceed; an
 * effect still needing a decision is refused instead of queued.
 */
export const APPROVAL_MODES: ReadonlyArray<{
  mode: ApprovalMode;
  label: string;
  /** What the menu says, when the label alone would be ambiguous in a list. */
  menuLabel?: string;
  /** One line of plain English, shown under the label in the menu. */
  detail: string;
  icon: IconName;
}> = [
  {
    mode: "sandbox",
    label: "Work in sandbox",
    detail: "Prepare in a verified task copy. Ask before changing the real project or taking consequential actions.",
    icon: "shield",
  },
  {
    mode: "manual",
    label: "Manually approve",
    detail: "Anything that needs a decision waits for you.",
    icon: "hand",
  },
  {
    mode: "dont_ask",
    label: "Decline, don't ask",
    menuLabel: "Decline instead of asking",
    detail: "For unattended runs: anything needing approval is refused, not queued.",
    icon: "shield",
  },
];
