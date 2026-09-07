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
  expect(screen.getByText(/Version 2\.0\.0 is ready to install/)).toBeInTheDocument();
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
  expect(await screen.findByText(/Installing 2.0.0/)).toBeInTheDocument();
});
