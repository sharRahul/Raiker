import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../api";
import type { UpdateStatusView } from "../../apiTypes";
import Updates from "./Updates.svelte";

afterEach(() => vi.restoreAllMocks());

function status(partial: Partial<UpdateStatusView> = {}): UpdateStatusView {
  return {
    state: "source_checkout",
    message: "This is a source checkout, so there is nothing to update.",
    installation: {
      version: "0.1.0",
      target: null,
      packaged: false,
      signed: false,
      channel: null,
      commit: null,
      built_at: null,
      installer_formats: [],
      install_root: "F:\\GitHub\\Raiker",
      note: "",
    },
    channel: null,
    available: null,
    recovery_points: [],
    checked_at: null,
    targets: [],
    last_check: null,
    ...partial,
  };
}

const signedPackage = status({
  state: "available",
  message: "Version 2.0.0 is available on the stable channel.",
  installation: {
    version: "1.0.0",
    target: "windows-x86_64",
    packaged: true,
    signed: true,
    channel: "stable",
    commit: null,
    built_at: null,
    installer_formats: ["msi"],
    install_root: "C:\\Program Files\\Raiker",
    note: "",
  },
  channel: {
    url: "https://releases.example/stable.json",
    channel: "stable",
    public_key_fingerprint: "ab12",
  },
  available: {
    channel: "stable",
    version: "2.0.0",
    target: "windows-x86_64",
    artifact: "raiker-2.0.0.zip",
    sha256: "a".repeat(64),
    signed: true,
    released_at: "2026-09-01T00:00:00Z",
  },
  recovery_points: [{ version: "1.0.0", path: "C:\\recovery", files: 12, bytes: 4096 }],
});

it("offers no apply path for a source checkout, and does not check on mount", async () => {
  const read = vi.spyOn(api, "hostUpdate").mockResolvedValue(status());
  const check = vi.spyOn(api, "checkHostUpdate");
  render(Updates);

  await screen.findByText(/source checkout/);
  expect(read).toHaveBeenCalledTimes(1);
  // Opening Settings must not reach the release channel. Only the button may.
  expect(check).not.toHaveBeenCalled();
  expect(screen.queryByRole("button", { name: /Update and restart/ })).not.toBeInTheDocument();
});

it("names the version, channel and recovery point a signed package would use", async () => {
  vi.spyOn(api, "hostUpdate").mockResolvedValue(signedPackage);
  render(Updates);

  expect(await screen.findByRole("button", { name: /Update and restart/ })).toBeInTheDocument();
  // Installed version and the recovery point it would leave behind, plus the
  // channel the release is verified against: the three facts the confirmation
  // is about.
  expect(screen.getAllByText("1.0.0", { selector: "dd" })).toHaveLength(2);
  expect(screen.getByText("stable", { selector: "dd" })).toBeInTheDocument();
  // REM-SET-UPDATES — "ready to install" claimed a download and a verification
  // that a channel *check* has not done. What the check establishes is that the
  // release is offered.
  expect(screen.getByText(/Version 2\.0\.0 is offered on the channel/)).toBeInTheDocument();
  expect(screen.queryByText(/ready to install/)).toBeNull();
  // And the state is named as itself, beside when the channel was last asked.
  expect(screen.getByText("A newer release is offered", { selector: "dd" })).toBeInTheDocument();
});

it("requires a second confirmation when an update would interrupt work", async () => {
  vi.spyOn(api, "hostUpdate").mockResolvedValue(signedPackage);
  const apply = vi
    .spyOn(api, "applyHostUpdate")
    .mockResolvedValueOnce({
      ...signedPackage,
      ok: false,
      updating: false,
      reason_code: "waiting_work",
      message: "Work is in flight.",
    })
    .mockResolvedValueOnce({ ...signedPackage, ok: true, updating: true, version: "2.0.0" });
  render(Updates);

  await fireEvent.click(await screen.findByRole("button", { name: /Update and restart/ }));
  expect(await screen.findByText(/would interrupt work in progress/)).toBeInTheDocument();
  expect(apply).toHaveBeenLastCalledWith(false);

  await fireEvent.click(screen.getByRole("button", { name: /Confirm update and restart/ }));
  await waitFor(() => expect(apply).toHaveBeenLastCalledWith(true));
  // REM-SET-UPDATES — the response says a helper started, not that an install
  // happened: it waits for this process to exit before it verifies or replaces
  // anything, and an owner who reads "Installing" and force-quits believes they
  // interrupted an install rather than a handover.
  expect(await screen.findByText(/helper for 2\.0\.0 has started/)).toBeInTheDocument();
  expect(screen.getByText(/Nothing on this installation has changed yet/)).toBeInTheDocument();
});

// ── GCR-16 ───────────────────────────────────────────────────────────────────

it("names the build this is, the commit it came from, and the build of the page", async () => {
  vi.spyOn(api, "hostUpdate").mockResolvedValue(
    status({
      installation: {
        ...signedPackage.installation,
        version: "1.2.3",
        commit: "abc1234def5678",
        built_at: "2026-09-01T10:00:00Z",
      },
    }),
  );
  render(Updates);

  // The version and the commit it was built from, as one identity rather than
  // one of four numbers that disagreed.
  expect(await screen.findByText("1.2.3 (abc1234)", { selector: "dd" })).toBeInTheDocument();
  expect(screen.getByText("Built", { selector: "dt" })).toBeInTheDocument();
  // And the build of the page reading it, which is the half neither the host
  // nor the bundle can report alone.
  expect(screen.getByText("This page", { selector: "dt" })).toBeInTheDocument();
  expect(screen.getByText("Unreleased build", { selector: "dd" })).toBeInTheDocument();
});

it("stays quiet about a mismatch this build cannot have", async () => {
  // Two unreleased builds are two development checkouts. Calling that a
  // mismatch would put a warning on every developer's screen for ever. The
  // released case is proved directly in `buildIdentity.test.ts`, because a test
  // bundle is by definition never a released client.
  vi.spyOn(api, "hostUpdate").mockResolvedValue(
    status({ installation: { ...signedPackage.installation, version: "0.0.0" } }),
  );
  render(Updates);

  await screen.findByText("Installed build", { selector: "dt" });
  expect(screen.queryByText(/older build than the one now running/)).toBeNull();
});
