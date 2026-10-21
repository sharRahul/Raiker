import { describe, expect, it } from "vitest";
import { backupReminder } from "./backupReminder";

const now = new Date("2026-10-21T12:00:00Z");

describe("backupReminder", () => {
  it("says nothing until the backups have been read", () => {
    expect(backupReminder(null, now)).toBeNull();
  });

  it("recommends a first backup", () => {
    expect(backupReminder([], now)).toMatchObject({ text: "There is no backup of this workspace yet.", label: "Make a backup" });
  });

  it("is quiet while the newest verified backup is less than a week old", () => {
    expect(backupReminder([{ created_at: "2026-10-18T12:00:00Z", state: "verified" }], now)).toBeNull();
  });

  it("names the age of a stale backup, and ignores ones that cannot restore", () => {
    expect(
      backupReminder(
        [
          { created_at: "2026-10-01T12:00:00Z", state: "verified" },
          { created_at: "2026-10-20T12:00:00Z", state: "damaged" },
        ],
        now,
      ),
    ).toMatchObject({ text: "The last backup was 20 days ago." });
  });
});
