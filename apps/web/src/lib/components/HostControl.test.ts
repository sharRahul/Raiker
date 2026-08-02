// BUG-44 — the panel's account of what this Raiker is.
//
// The property under test is not "does it render a version": it is that the
// panel never claims provenance the installation cannot support. A checkout says
// checkout, an unsigned build says unsigned, and a status read never causes an
// outbound check.
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import HostControl from "./HostControl.svelte";
import { stubFetch } from "../test-helpers";

afterEach(() => vi.unstubAllGlobals());

const HOST = {
  state: "running",
  detail: "Raiker is running.",
  pid: 1234,
  port: 8765,
  started_at: "2026-08-02T00:00:00Z",
  paused: false,
  paused_since: null,
  paused_reason: null,
  waiting: [],
  service: { supported: true, registered: false, mechanism: "systemd --user", label: "", path: null, note: "" },
  restartable: false,
};

const TARGETS = [
  {
    target_id: "linux-x86_64",
    os: "linux",
    arch: "x86_64",
    runner: "ubuntu-22.04",
    installer_formats: [".AppImage", ".deb"],
    signing: { tool: "gpg", secrets: ["LINUX_PACKAGE_SIGNING_KEY"], note: "" },
  },
];

function update(partial: Record<string, unknown> = {}) {
  return {
    state: "source_checkout",
    message: "Running from a source checkout.",
    installation: {
      version: "0.0.0",
      target: null,
      packaged: false,
      signed: false,
      channel: null,
      commit: null,
      built_at: null,
      installer_formats: [],
      install_root: "/home/owner/raiker",
      note: "Running from a source checkout.",
    },
    channel: null,
    available: null,
    recovery_points: [],
    checked_at: null,
    targets: TARGETS,
    last_check: null,
    ...partial,
  };
}

async function open(routes: Record<string, unknown>) {
  stubFetch({ "GET /api/host": HOST, ...routes });
  render(HostControl);
  await fireEvent.click(await screen.findByRole("button", { name: /host/i }));
}

describe("HostControl install and updates", () => {
  it("says source checkout when there is no installation record", async () => {
    await open({ "GET /api/host/update": update() });
    expect(await screen.findByText("source checkout")).toBeInTheDocument();
    expect(screen.getByText(/Raiker contacts no update service/)).toBeInTheDocument();
  });

  it("calls an unsigned release an unsigned build, never a signed one", async () => {
    await open({
      "GET /api/host/update": update({
        state: "unsigned_build",
        message: "This build was produced without platform signing.",
        installation: {
          ...update().installation,
          version: "1.2.3",
          target: "linux-x86_64",
          packaged: true,
          signed: false,
          channel: "stable",
        },
      }),
    });
    expect(await screen.findByText("unsigned build")).toBeInTheDocument();
    expect(screen.queryByText("signed release")).toBeNull();
    expect(screen.getByText(/1\.2\.3 · linux-x86_64/)).toBeInTheDocument();
  });

  it("names the pinned channel without ever showing its key", async () => {
    await open({
      "GET /api/host/update": update({
        state: "up_to_date",
        message: "This is the newest release on the configured channel.",
        installation: { ...update().installation, packaged: true, signed: true, version: "1.2.3" },
        channel: {
          url: "https://releases.example/stable.json",
          channel: "stable",
          public_key_fingerprint: "0123456789abcdef",
        },
      }),
    });
    expect(await screen.findByText("signed release")).toBeInTheDocument();
    expect(screen.getByText(/stable · https:\/\/releases\.example\/stable\.json/)).toBeInTheDocument();
    expect(screen.queryByText(/0123456789abcdef/)).toBeNull();
  });

  it("points an available update at the command that can apply it", async () => {
    await open({
      "GET /api/host/update": update({
        state: "available",
        message: "Version 2.0.0 is available.",
        installation: { ...update().installation, packaged: true, signed: true, version: "1.2.3" },
        channel: { url: "https://releases.example/stable.json", channel: "stable", public_key_fingerprint: "a" },
        available: {
          channel: "stable",
          version: "2.0.0",
          target: "linux-x86_64",
          artifact: "raiker-2.0.0-linux-x86_64.zip",
          sha256: "0".repeat(64),
          signed: true,
          released_at: "2026-08-02T00:00:00Z",
        },
        recovery_points: [{ version: "1.1.0", path: "/x/1.1.0", files: 12, bytes: 1024 }],
      }),
    });
    // The message line and the "how to apply it" callout both name the
    // version; what matters is that both are present and agree.
    expect((await screen.findAllByText(/Version 2\.0\.0 is available/)).length).toBeGreaterThan(0);
    // Applying is not offered in-app: it replaces what this host runs from.
    expect(screen.getByText("raiker-app update --apply")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /install|apply/i })).toBeNull();
    expect(screen.getByText("1.1.0")).toBeInTheDocument();
  });

  it("does not check for updates until asked to", async () => {
    const mock = stubFetch({
      "GET /api/host": HOST,
      "GET /api/host/update": update(),
      "POST /api/host/update/check": { ok: true, ...update({ message: "Nothing newer." }) },
    });
    render(HostControl);
    await fireEvent.click(await screen.findByRole("button", { name: /host/i }));
    await screen.findByText("source checkout");

    const checks = () =>
      mock.mock.calls.filter((call) => String(call[0]).includes("/api/host/update/check"));
    expect(checks()).toHaveLength(0);

    await fireEvent.click(screen.getByRole("button", { name: /Check for updates/ }));
    await waitFor(() => expect(checks()).toHaveLength(1));
    // Once as the panel's build message, once as the action's notice.
    await waitFor(() => expect(screen.getAllByText("Nothing newer.")).toHaveLength(2));
  });
});
