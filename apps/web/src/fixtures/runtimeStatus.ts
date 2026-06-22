// ─────────────────────────────────────────────────────────────────────────────
// FIXTURE DATA — NOT from any runtime. Used only for M1 layout development.
// The UI must never present fixture data as real runtime state; the banner shows a
// "FIXTURE DATA" indicator while these values are in use. Removed once wired (M2+).
// ─────────────────────────────────────────────────────────────────────────────

export interface RuntimeStatus {
  fixture: true;
  runtimeMode: string;
  scope: string;
  principal: string;
  ready: boolean;
  warnings: string[];
}

export const runtimeStatusFixture: RuntimeStatus = {
  fixture: true,
  runtimeMode: "local_single_user_runtime",
  scope: "local · single-user",
  principal: "owner (fixture)",
  ready: true,
  warnings: ["Tier 2–6 runtimes disabled / deferred"],
};
