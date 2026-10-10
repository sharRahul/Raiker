import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { setToken } from "../api";
import type { BackupView } from "../generated/apiContract";
import { stubFetch } from "../test-helpers";
import BackupsCard from "./BackupsCard.svelte";

/** DEC-24 step 5 — backups, what they hold, which key opens them, and a restore that replaces nothing. */
function backup(partial: Partial<BackupView> = {}): BackupView {
  return {
    backup_id: "bkp_1",
    reason: "owner",
    created_at: "2026-10-05T10:00:00Z",
    size_bytes: 2_400_000,
    sha256: "a".repeat(64),
    schema_migrations: 190,
    latest_migration: "RAIKER-2091-task-run-limit",
    counts: { sessions: 4, approved_memory: 2 },
    key_fingerprint: "f".repeat(16),
    included: ["database", "memory_files", "checkpoints", "artifacts"],
    not_included: ["event_log", "attached_folders"],
    state: "verified",
    verified_at: "2026-10-05T10:00:00Z",
    detail: "",
    schema_generation: 197,
    opens_here: true,
    trees: {
      checkpoints: { files: 12, bytes: 4096, sha256: "c".repeat(64) },
      artifacts: { files: 1, bytes: 512, sha256: "d".repeat(64) },
    },
    ...partial,
  };
}

afterEach(() => {
  setToken(null);
  vi.unstubAllGlobals();
});

describe("BackupsCard", () => {
  it("says what a backup holds, what it does not, and which key opens it", async () => {
    setToken("t");
    stubFetch({ "GET /api/backups": { backups: [backup(), backup({ backup_id: "bkp_2", reason: "pre_migration", state: "damaged", detail: "It no longer matches its checksum." })], key_fingerprint: "f".repeat(16) } });
    render(BackupsCard);
    const card = await screen.findByTestId("backups-card");
    expect(card).toHaveTextContent("Not included: the audit log, folders you attached to projects");
    expect(card).toHaveTextContent(".raiker/app.key");
    expect(await screen.findByText("Before an update")).toBeInTheDocument();
    // DEC-24 step 5 — the files the database points at travel with it, and say so.
    expect(card).toHaveTextContent("12 checkpoint files · 1 upload");
    const states = screen.getAllByTestId("backup-state").map((node) => node.textContent);
    expect(states[0]).toBe("Verified");
    expect(states[1]).toMatch(/^Damaged — It no longer matches/);
    // A damaged backup offers no restore.
    expect(screen.getAllByRole("button", { name: "Restore to a new folder" })[1]).toBeDisabled();
  });

  it("restores to a separate folder and says the running workspace was not changed", async () => {
    setToken("t");
    stubFetch({
      "GET /api/backups": { backups: [backup()], key_fingerprint: "f".repeat(16) },
      "POST /api/backups/bkp_1/restore": {
        backup_id: "bkp_1",
        path: "/w/.raiker/restores/bkp_1",
        counts: { sessions: 4, approved_memory: 2 },
        command: 'raiker-web --workspace "/w/.raiker/restores/bkp_1" --port 8766',
      },
    });
    render(BackupsCard);
    await fireEvent.click(await screen.findByRole("button", { name: "Restore to a new folder" }));
    const restored = await screen.findByTestId("backup-restored");
    expect(restored).toHaveTextContent("Your running workspace was not changed");
    expect(restored).toHaveTextContent("--workspace");
  });

  it("backs up now and reports it verified", async () => {
    setToken("t");
    const fetchMock = stubFetch({
      "GET /api/backups": { backups: [], key_fingerprint: "f".repeat(16) },
      "POST /api/backups": backup(),
    });
    render(BackupsCard);
    expect(await screen.findByText("No backups yet.")).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Back up now" }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([, init]) => (init as RequestInit | undefined)?.method === "POST")).toBe(true));
    expect(await screen.findByText(/Backed up and verified — 2\.3 MB/)).toBeInTheDocument();
  });
});
