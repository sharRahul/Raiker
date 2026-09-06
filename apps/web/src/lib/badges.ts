import type { BadgeVariant } from "./types";

export interface BadgeMeta {
  /** Human-readable, screen-reader-accessible label. */
  label: string;
  /** A non-colour shape/glyph cue (decorative; hidden from assistive tech). */
  symbol: string;
  /** CSS tone class — colour is a secondary cue only. */
  tone: string;
  /** Plain-English meaning, surfaced as a tooltip. */
  description: string;
}

// The security-UX badge set mirrors the governed-runtime status labels; the lifecycle set
// (active/done/stopped/idle) is generic and usually rendered with a raw-status label override.
export const BADGES: Record<BadgeVariant, BadgeMeta> = {
  // VIS-15 — "colour exceptions and actions, not every normal state". A
  // low-risk auto-allowed capability is the resting state of most of the gate
  // table, and painting it green meant Permissions opened as a wall of green
  // reporting that nothing was wrong. The symbol still says it and the label
  // still says it; the colour is spent elsewhere.
  safe: {
    label: "Safe",
    symbol: "✓",
    tone: "tone-muted",
    description: "Low-risk, auto-allowed.",
  },
  "needs-approval": {
    label: "Needs approval",
    symbol: "▲",
    tone: "tone-warn",
    description: "Requires a human approval decision before it can proceed.",
  },
  "approval-required": {
    label: "Approval-required",
    symbol: "▲",
    tone: "tone-warn",
    description: "Capability/action is gated on approval.",
  },
  blocked: {
    label: "Blocked",
    symbol: "✕",
    tone: "tone-danger",
    description: "Denied by policy or authority.",
  },
  disabled: {
    label: "Disabled",
    symbol: "⊘",
    tone: "tone-muted",
    description: "Capability gate is currently disabled.",
  },
  deferred: {
    label: "Deferred",
    symbol: "⋯",
    tone: "tone-muted",
    description: "Future / not-yet-built; cannot be enabled in this build.",
  },
  // VIS-15 — likewise. "This capability works" is the normal case for a
  // shipped build, not an event worth a colour. `done` keeps its green,
  // because finishing is something that *happened*.
  implemented: {
    label: "Implemented",
    symbol: "●",
    tone: "tone-muted",
    description: "Real, working capability.",
  },
  "metadata-only": {
    label: "Metadata-only",
    symbol: "ⓘ",
    tone: "tone-info",
    description: "Records a decision; does not execute the action.",
  },
  "read-only": {
    label: "Read-only",
    symbol: "◍",
    tone: "tone-info",
    description: "View only; no mutation.",
  },
  "risk-acceptance-required": {
    label: "Risk-acceptance required",
    symbol: "‼",
    tone: "tone-danger",
    description: "A one-time/reusable risk acceptance is required first.",
  },
  active: {
    label: "Active",
    symbol: "►",
    tone: "tone-accent",
    description: "In flight.",
  },
  done: {
    label: "Done",
    symbol: "✓",
    tone: "tone-ok",
    description: "Finished successfully.",
  },
  stopped: {
    label: "Stopped",
    symbol: "✕",
    tone: "tone-danger",
    description: "Failed, denied, or cancelled.",
  },
  idle: {
    label: "Idle",
    symbol: "◌",
    tone: "tone-muted",
    description: "No current activity.",
  },
};

export const BADGE_VARIANTS = Object.keys(BADGES) as BadgeVariant[];
