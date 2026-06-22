// Status badge variants — one per label defined in docs/UI-implementation/02_SECURITY_UX.md.
// Each variant must convey meaning by text + shape, never colour alone (see badges.ts).
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
  | "risk-acceptance-required";
