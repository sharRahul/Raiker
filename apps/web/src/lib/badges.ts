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

// Mirrors the badge table in docs/UI-implementation/02_SECURITY_UX.md.
export const BADGES: Record<BadgeVariant, BadgeMeta> = {
  safe: {
    label: "Safe",
    symbol: "✓",
    tone: "tone-safe",
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
  implemented: {
    label: "Implemented",
    symbol: "●",
    tone: "tone-ok",
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
};

export const BADGE_VARIANTS = Object.keys(BADGES) as BadgeVariant[];
