// BUG-347 / BUG-358 — Settings → Security → Remote access: rows that read the
// running host, a guided change that the server checks and applies with fresh
// MFA, and a turn-off that is one confirmation away.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import RemoteAccessSettings from "./RemoteAccessSettings.svelte";
import ConfirmDialog from "./ConfirmDialog.svelte";
import { setToken } from "../api";
import { remoteStatus } from "../test-helpers";
import type { RemoteAccessStatusView } from "../generated/apiContract";

afterEach(() => {
  vi.unstubAllGlobals();
  setToken(null);
});

type Handler = (init?: RequestInit) => { status?: number; body: unknown };

function stub(routes: Record<string, Handler>, calls: string[] = []) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      const key = `${(init?.method ?? "GET").toUpperCase()} ${url.split("?")[0]}`;
      calls.push(key);
      const handler = routes[key];
      if (!handler) return { ok: false, status: 404, json: async () => ({ detail: { reason_code: "unrouted" } }) } as Response;
      const answer = handler(init);
      const status = answer.status ?? 200;
      return { ok: status < 400, status, json: async () => answer.body } as Response;
    }),
  );
}

const ON: Partial<RemoteAccessStatusView> = {
  state: "enabled",
  desired: { mode: "proxy", proxy_kind: "port", proxy_port: 8766, proxy_socket: null, private_host: null, private_port: null, tls_cert: null, tls_key: null },
  active: { mode: "proxy", address: "127.0.0.1:8766", source: "settings", https_verified: true, refusing: false },
  https: "verified",
};

describe("Remote access settings", () => {
  it("shows the state the running host reports, with one action per row", async () => {
    stub({ "GET /api/remote-access": () => ({ body: remoteStatus(ON) }) });
    render(RemoteAccessSettings, { props: { onopenmfa: () => {} } });
    expect(await screen.findByTestId("remote-state")).toHaveTextContent("On");
    expect(screen.getByTestId("remote-connection")).toHaveTextContent("Reverse proxy · 127.0.0.1:8766");
    expect(screen.getByText("Verified")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Turn off" })).toBeInTheDocument();
  });

  it("does not say it is on before the host opens it", async () => {
    stub({
      "GET /api/remote-access": () => ({
        body: remoteStatus({ state: "pending_restart", desired: ON.desired, restart_required: true }),
      }),
    });
    render(RemoteAccessSettings);
    expect(await screen.findByTestId("remote-state")).toHaveTextContent("Waiting for a restart");
    expect(screen.getByTestId("remote-connection")).toHaveTextContent("This device only");
  });

  it("explains what is missing before remote access can be set up", async () => {
    stub({
      "GET /api/remote-access": () => ({
        body: remoteStatus({ mfa: { enrolled: false, ready: false, accounts_without_mfa: 1, reset_pending: false } }),
      }),
    });
    render(RemoteAccessSettings, { props: { onopenmfa: () => {} } });
    await fireEvent.click(await screen.findByRole("button", { name: "Set up" }));
    const dialog = within(screen.getByRole("dialog"));
    await fireEvent.click(dialog.getByRole("radio", { name: /Reverse proxy/ }));
    expect(dialog.getByText("Two-step sign-in must be on for every account.")).toBeInTheDocument();
    expect(dialog.getByRole("button", { name: "Continue" })).toBeDisabled();
  });

  it("checks, reviews, confirms with fresh MFA and saves for the next start", async () => {
    const calls: string[] = [];
    let applied: unknown = null;
    stub(
      {
        "GET /api/remote-access": () => ({ body: remoteStatus() }),
        "POST /api/remote-access/check": () => ({
          body: { ok: true, checks: [{ code: "ok", ok: true, message: "fine", field: null, severity: "info" }] },
        }),
        "POST /api/auth/elevate": () => ({ body: { token: "elevated-token" } }),
        "POST /api/remote-access/apply": (init) => {
          applied = JSON.parse(String(init?.body));
          return { body: remoteStatus({ state: "pending_restart", desired: ON.desired, restart_required: true }) };
        },
      },
      calls,
    );
    render(RemoteAccessSettings);
    await fireEvent.click(await screen.findByRole("button", { name: "Set up" }));
    let dialog = within(screen.getByRole("dialog"));
    await fireEvent.click(dialog.getByRole("radio", { name: /Reverse proxy/ }));
    await fireEvent.click(dialog.getByRole("button", { name: "Continue" }));
    dialog = within(screen.getByRole("dialog"));
    expect(dialog.getByText(/Never point the proxy at 127.0.0.1:8765/)).toBeInTheDocument();
    await fireEvent.click(dialog.getByRole("button", { name: "Check and continue" }));
    await waitFor(() => expect(within(screen.getByRole("dialog")).getByLabelText("Password")).toBeInTheDocument());
    dialog = within(screen.getByRole("dialog"));
    const turnOn = dialog.getByRole("button", { name: "Turn on remote access" });
    await fireEvent.input(dialog.getByLabelText("Password"), { target: { value: "pw" } });
    await fireEvent.input(dialog.getByLabelText("Authenticator code"), { target: { value: "123456" } });
    expect(turnOn).toBeDisabled(); // not confirmed yet
    await fireEvent.click(dialog.getByRole("checkbox"));
    expect(turnOn).toBeEnabled();
    await fireEvent.click(turnOn);
    await waitFor(() => expect(applied).not.toBeNull());
    expect(applied).toEqual({ config: { mode: "proxy", proxy_kind: "port", proxy_port: 8766 }, confirm: true });
    expect(calls.indexOf("POST /api/auth/elevate")).toBeLessThan(calls.indexOf("POST /api/remote-access/apply"));
    expect(await screen.findByText("Saved. Raiker opens it when it restarts.")).toBeInTheDocument();
    expect(screen.getByText(/Quit Raiker and open it again/)).toBeInTheDocument();
  });

  it("shows the server's checks in the owner's words and stays on the form", async () => {
    stub({
      "GET /api/remote-access": () => ({ body: remoteStatus() }),
      "POST /api/remote-access/check": () => ({
        body: {
          ok: false,
          checks: [{ code: "port_conflict_local", ok: false, message: "Port 8765 is Raiker's own listener for this computer. Choose another one.", field: "proxy_port", severity: "error" }],
        },
      }),
    });
    render(RemoteAccessSettings);
    await fireEvent.click(await screen.findByRole("button", { name: "Set up" }));
    const dialog = within(screen.getByRole("dialog"));
    await fireEvent.click(dialog.getByRole("radio", { name: /Reverse proxy/ }));
    await fireEvent.click(dialog.getByRole("button", { name: "Continue" }));
    await fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Check and continue" }));
    expect(await screen.findByText(/Port 8765 is Raiker's own listener/)).toBeInTheDocument();
    expect(within(screen.getByRole("dialog")).queryByLabelText("Password")).toBeNull();
  });

  it("turns off after one confirmation", async () => {
    let disabled = false;
    stub({
      "GET /api/remote-access": () => ({ body: remoteStatus(ON) }),
      "POST /api/remote-access/disable": () => {
        disabled = true;
        return { body: remoteStatus({ active: { ...ON.active!, refusing: true } }) };
      },
    });
    render(ConfirmDialog);
    render(RemoteAccessSettings);
    await fireEvent.click(await screen.findByRole("button", { name: "Turn off" }));
    const confirm = await screen.findByRole("dialog", { name: "Turn off remote access?" });
    expect(confirm).toHaveTextContent("This computer is not affected.");
    await fireEvent.click(within(confirm).getByRole("button", { name: "Turn off" }));
    await waitFor(() => expect(disabled).toBe(true));
    expect(await screen.findByText(/Other devices are refused now/)).toBeInTheDocument();
  });

  it("offers no configuration on another device, only turning it off", async () => {
    stub({ "GET /api/remote-access": () => ({ body: remoteStatus({ ...ON, can_configure: false }) }) });
    render(RemoteAccessSettings);
    await screen.findByTestId("remote-state");
    expect(screen.queryByRole("button", { name: "Change" })).toBeNull();
    expect(screen.getByRole("button", { name: "Turn off" })).toBeInTheDocument();
    expect(screen.getByText(/changed on the computer Raiker runs on/)).toBeInTheDocument();
  });
});
