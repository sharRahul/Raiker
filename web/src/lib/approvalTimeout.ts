/**
 * QUI-P06 — how long an unanswered approval waits before it expires.
 *
 * Kept in step with `raiker.storage.stores.approvals`: the server reads the
 * same setting every time it raises an approval and refuses any value that is
 * not one of these choices, so the page can only offer what will be applied.
 */
export const APPROVAL_TIMEOUT_KEY = "security.approval_timeout_minutes";
export const DEFAULT_APPROVAL_TIMEOUT_MINUTES = 30;

export const APPROVAL_TIMEOUT_CHOICES: ReadonlyArray<{ minutes: number; label: string }> = [
  { minutes: 15, label: "15 minutes" },
  { minutes: 30, label: "30 minutes" },
  { minutes: 60, label: "1 hour" },
  { minutes: 240, label: "4 hours" },
  { minutes: 1440, label: "1 day" },
];

/** The stored time limit, or the default when none (or an unknown one) is stored. */
export function approvalTimeoutMinutes(settings: Record<string, unknown> | null | undefined): number {
  const value = settings?.[APPROVAL_TIMEOUT_KEY];
  return APPROVAL_TIMEOUT_CHOICES.some((choice) => choice.minutes === value)
    ? (value as number)
    : DEFAULT_APPROVAL_TIMEOUT_MINUTES;
}

export function approvalTimeoutLabel(minutes: number): string {
  return APPROVAL_TIMEOUT_CHOICES.find((choice) => choice.minutes === minutes)?.label ?? `${minutes} minutes`;
}

/** Where the setting lives, for the links that name it. */
export const APPROVAL_TIMEOUT_ROUTE = "#/settings?tab=security";
