import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { setToken } from "../api";
import { stubFetch } from "../test-helpers";
import WorkspaceKeySettings from "./WorkspaceKeySettings.svelte";

/** BUG-354 — the workspace key is rotated in place, on a step-up, and old backups keep their key. */
const CURRENT = "a".repeat(16);
const RETIRED = "b".repeat(16);

function backupOn(fingerprint: string, id: string) {
  return { backup_id: id, key_fingerprint: fingerprint, created_at: "2026-11-14T10:00:00Z", state: "verified" };
}

afterEach(() => {
  setToken(null);
  vi.unstubAllGlobals();
});

describe("WorkspaceKeySettings", () => {
  it("shows the key in use and each retired key with the backups that need it", async () => {
    setToken("t");
    stubFetch({
      "GET /api/backups": {
        backups: [backupOn(CURRENT, "bkp_1"), backupOn(RETIRED, "bkp_2"), backupOn(RETIRED, "bkp_3")],
        key_fingerprint: CURRENT,
        retired_key_fingerprints: [RETIRED],
      },
    });
    render(WorkspaceKeySettings);
    await waitFor(() => expect(screen.getByTestId("workspace-key-fingerprint")).toHaveTextContent(CURRENT));
    expect(await screen.findByText(`${RETIRED} · kept for 2 backups`)).toBeInTheDocument();
  });

  it("rotates on an elevated session and reports the new key", async () => {
    setToken("control");
    const mock = stubFetch({
      "GET /api/backups": { backups: [backupOn(CURRENT, "bkp_1")], key_fingerprint: CURRENT, retired_key_fingerprints: [] },
      "POST /api/auth/elevate": { token: "elevated", expires_at: "2026-11-14T10:05:00Z" },
      "POST /api/security/workspace-key/rotate": {
        ok: true,
        old_fingerprint: CURRENT,
        new_fingerprint: "c".repeat(16),
        backup_id: "bkp_9",
        resealed: 2,
        backups_on_retired_key: ["bkp_1", "bkp_9"],
      },
    });
    render(WorkspaceKeySettings, { mfaEnrolled: true });
    await fireEvent.click(await screen.findByRole("button", { name: "Rotate" }));
    expect(screen.getByTestId("workspace-key-backups-note")).toHaveTextContent("1 existing backup will need the current key");
    const go = screen.getByRole("button", { name: "Back up and rotate" });
    expect(go).toBeDisabled();
    await fireEvent.input(screen.getByLabelText("Password"), { target: { value: "pw" } });
    await fireEvent.input(screen.getByLabelText("Authenticator code"), { target: { value: "123456" } });
    await fireEvent.click(go);
    const done = await screen.findByTestId("workspace-key-rotated");
    expect(done).toHaveTextContent(`now ${"c".repeat(16)}`);
    expect(done).toHaveTextContent("2 sealed secrets were re-sealed");
    expect(done).toHaveTextContent("2 backups made before now still need the old key");
    const rotate = mock.mock.calls.find(([url]) => String(url).includes("/workspace-key/rotate"));
    expect(new Headers(rotate?.[1]?.headers).get("authorization")).toBe("Bearer elevated");
  });

  it("says the key was not changed when the password is refused", async () => {
    setToken("control");
    stubFetch({
      "GET /api/backups": { backups: [], key_fingerprint: CURRENT, retired_key_fingerprints: [] },
      "POST /api/auth/elevate": { __status: 401, detail: "bad" },
    });
    render(WorkspaceKeySettings);
    await fireEvent.click(await screen.findByRole("button", { name: "Rotate" }));
    await fireEvent.input(screen.getByLabelText("Password"), { target: { value: "wrong" } });
    await fireEvent.click(screen.getByRole("button", { name: "Back up and rotate" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("The key was not changed"));
  });
});
