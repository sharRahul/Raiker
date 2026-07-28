import type { IconName } from "./icons";

export type ApprovalMode = "manual" | "auto" | "skip";

export const APPROVAL_MODES: ReadonlyArray<{ mode: ApprovalMode; label: string; icon: IconName }> = [
  { mode: "manual", label: "Manually approve", icon: "hand" },
  { mode: "auto", label: "Automatically approve", icon: "fast-forward" },
  { mode: "skip", label: "Skip", icon: "warning" },
];
