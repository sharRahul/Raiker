import type { IconName } from "./icons";

export type ApprovalMode = "manual" | "auto" | "skip" | "dont_ask";

/**
 * The four postures, ordered from "I am watching" to "I am not here".
 *
 * `dont_ask` is the unattended one (BUG-219): anything not already permitted by
 * a standing rule is **declined** rather than queued. It is the posture for a
 * scheduled run or a background agent, where an interruption is worse than a
 * refusal — parking on a prompt nobody will answer is not the same as declining,
 * and only one of the two lets the rest of the work continue.
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
    mode: "manual",
    label: "Manually approve",
    detail: "Anything that needs a decision waits for you.",
    icon: "hand",
  },
  {
    mode: "auto",
    label: "Automatically approve",
    // BUG-218 — Auto now runs a second check before granting, so the copy says
    // so. The check is deterministic, not a classifier: it asks whether this
    // turn read, listed or was asked about the file, and can only withhold.
    detail:
      "Approvals are granted for you, unless a change lands on a file this turn never looked at — then it waits.",
    icon: "fast-forward",
  },
  {
    mode: "skip",
    label: "Skip",
    menuLabel: "Skip all approvals",
    detail: "No approval is raised at all. Gates and policy still apply.",
    icon: "warning",
  },
  {
    mode: "dont_ask",
    label: "Decline, don't ask",
    menuLabel: "Decline instead of asking",
    detail: "For unattended runs: anything needing approval is refused, not queued.",
    icon: "shield",
  },
];
