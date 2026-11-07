import type { ExecutionEnvironment } from "./apiTypes";

/**
 * Beta plan §1 — commands run only where the sandbox was measured, and an
 * owner can see that before pressing anything.
 *
 * Returns the one sentence a composer shows when the selected environment
 * cannot run commands on this computer, or null when it can (or when that is
 * not known yet: an unread environment is not reported as a refusal).
 */
export const COMMANDS_UNAVAILABLE = "Commands unavailable here";

export function commandsUnavailableReason(environment: ExecutionEnvironment | null): string | null {
  if (environment === null || environment.available) return null;
  if (environment.kind === "retired") return "Commands are turned off because the selected environment was removed.";
  if (environment.kind === "native") {
    return "Commands are turned off on this computer because its sandbox could not be confirmed. Plan and Propose still work.";
  }
  return `Commands are turned off because ${environment.name} is not ready.`;
}

/** Where the owner can do something about it. */
export const COMMANDS_SETUP_HREF = "#/settings?tab=advanced&kind=runtime";
