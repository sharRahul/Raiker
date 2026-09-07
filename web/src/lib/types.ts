// Status badge variants. The security-UX set (safe/needs-approval/…) is defined by the
// governed-runtime status labels; the generic lifecycle set (active/done/stopped/idle)
// covers task, turn, and approval statuses. Each variant conveys meaning by text + shape,
// never colour alone (see badges.ts).
export type BadgeVariant =
  | "safe"
  | "needs-approval"
  | "approval-required"
  | "blocked"
  | "disabled"
  | "deferred"
  | "implemented"
  | "metadata-only"
  | "read-only"
  | "risk-acceptance-required"
  | "active"
  | "done"
  | "stopped"
  | "idle";
