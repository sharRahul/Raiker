/**
 * QUI-H05 — Home recommends a backup only when there is none, or the newest
 * one is stale.
 *
 * A healthy backup says nothing on Home: it is visible in Settings › Account
 * where backups are made. Seven days is the line, matching "This week": a
 * workspace an owner has used all week and never backed up is the case worth
 * one sentence.
 */
import type { BackupView } from "./generated/apiContract";

export const BACKUP_STALE_DAYS = 7;
const DAY_MS = 24 * 60 * 60 * 1000;

export interface BackupReminder {
  readonly text: string;
  readonly href: string;
  readonly label: string;
}

const WHERE = "#/settings?tab=account";

export function backupReminder(
  backups: readonly Pick<BackupView, "created_at" | "state">[] | null,
  now: Date,
): BackupReminder | null {
  if (backups === null) return null;
  const times = backups
    // Only a backup that verified can restore anything; a damaged or
    // unreadable one is not a backup to rely on (`raiker/storage/backup.py`).
    .filter((backup) => backup.state === "verified")
    .map((backup) => Date.parse(backup.created_at))
    .filter((at) => Number.isFinite(at));
  if (times.length === 0) {
    return { text: "There is no backup of this workspace yet.", href: WHERE, label: "Make a backup" };
  }
  const days = Math.floor((now.getTime() - Math.max(...times)) / DAY_MS);
  if (days < BACKUP_STALE_DAYS) return null;
  return { text: `The last backup was ${days} days ago.`, href: WHERE, label: "Make a backup" };
}
