// BUG-347 / BUG-358 — Settings → Security → Remote access, in words.
//
// The server decides everything: what is open, what is allowed, what a change
// needs. This module only names what it says, so the rows, the Host menu and
// Diagnostics describe the same state the same way. Nothing here is a status of
// its own: every line reads a field the running host reported.
import { auth } from "./api/auth";
import { getToken, setToken } from "./api/core";
import type {
  RemoteAccessConfigBody,
  RemoteAccessConfigView,
  RemoteAccessStatusView,
} from "./generated/apiContract";

export type RemoteMode = "local" | "private" | "proxy";
export type RemoteState = RemoteAccessStatusView["state"];

export const MODE_CHOICES: { mode: RemoteMode; label: string; detail: string }[] = [
  {
    mode: "local",
    label: "This device only",
    detail: "Raiker answers this computer and nothing else. The default.",
  },
  {
    mode: "private",
    label: "Private network",
    detail: "Your other devices reach Raiker over your home network or a VPN such as Tailscale, over HTTPS with your certificate.",
  },
  {
    mode: "proxy",
    label: "Reverse proxy",
    detail: "A proxy on this computer, such as Caddy or nginx, serves Raiker at an https:// address and passes requests to a listener Raiker opens for it.",
  },
];

export function modeLabel(mode: RemoteMode): string {
  return MODE_CHOICES.find((choice) => choice.mode === mode)?.label ?? mode;
}

/** The row's value: whether other devices can reach Raiker, as the running host says. */
export function stateLabel(status: Pick<RemoteAccessStatusView, "state" | "desired">): string {
  switch (status.state) {
    case "enabled":
      return "On";
    case "suspended":
      return "Suspended";
    case "pending_restart":
      return status.desired.mode === "local" ? "Turning off at restart" : "Waiting for a restart";
    case "error":
      return "Not working";
    default:
      return "Off — this device only";
  }
}

export function stateTone(state: RemoteState): "ok" | "warn" | "danger" | "neutral" {
  if (state === "enabled") return "ok";
  if (state === "suspended" || state === "error") return "danger";
  if (state === "pending_restart") return "warn";
  return "neutral";
}

/** How the active connection is described: method, then where. */
export function connectionLabel(status: RemoteAccessStatusView): string {
  const active = status.active;
  if (active.address === null) return "This device only";
  const method = modeLabel(active.mode);
  return `${method} · ${active.address}`;
}

export function mfaReadiness(status: RemoteAccessStatusView): { label: string; tone: "ok" | "warn" | "danger" } {
  if (status.mfa.reset_pending) return { label: "Verification needed", tone: "warn" };
  if (status.mfa.ready) return { label: "Enrolled", tone: "ok" };
  return { label: "Required", tone: "danger" };
}

export function httpsLabel(https: RemoteAccessStatusView["https"]): string {
  if (https === "verified") return "Verified";
  if (https === "not_verified") return "Not verified yet";
  return "Not in use";
}

const EVENT_LABELS: Record<string, string> = {
  configured: "Remote access was changed",
  disabled: "Remote access was turned off",
  rolled_back: "Went back to the previous setting",
  started: "The remote listener opened",
  start_failed: "The remote listener did not open",
  suspended: "Remote access was suspended",
  remote_signed_in: "A device signed in remotely",
  remote_sign_in_failed: "A remote sign-in failed",
  remote_mfa_failed: "A remote code was wrong",
  remote_sign_in_refused: "A remote sign-in was refused",
  sessions_revoked: "Other devices were signed out",
};

export function eventLabel(kind: string): string {
  return EVENT_LABELS[kind] ?? kind.replaceAll("_", " ");
}

/** The form the dialog edits, from a stored configuration. */
export interface RemoteForm {
  mode: RemoteMode;
  proxyKind: "port" | "socket";
  proxyPort: string;
  proxySocket: string;
  privateHost: string;
  privatePort: string;
  tlsCert: string;
  tlsKey: string;
}

export function formFrom(config: RemoteAccessConfigView): RemoteForm {
  return {
    mode: config.mode,
    proxyKind: config.proxy_kind,
    proxyPort: config.proxy_port === null ? "8766" : String(config.proxy_port),
    proxySocket: config.proxy_socket ?? "",
    privateHost: config.private_host ?? "",
    privatePort: config.private_port === null ? "8443" : String(config.private_port),
    tlsCert: config.tls_cert ?? "",
    tlsKey: config.tls_key ?? "",
  };
}

function port(text: string): number | null {
  const trimmed = text.trim();
  if (!/^\d+$/.test(trimmed)) return null;
  return Number(trimmed);
}

/** What the server is sent. Only the chosen mode's fields; it checks the rest. */
export function configFrom(form: RemoteForm): RemoteAccessConfigBody {
  if (form.mode === "proxy") {
    return form.proxyKind === "socket"
      ? { mode: "proxy", proxy_kind: "socket", proxy_socket: form.proxySocket.trim() || null }
      : { mode: "proxy", proxy_kind: "port", proxy_port: port(form.proxyPort) };
  }
  if (form.mode === "private") {
    return {
      mode: "private",
      private_host: form.privateHost.trim() || null,
      private_port: port(form.privatePort),
      tls_cert: form.tlsCert.trim() || null,
      tls_key: form.tlsKey.trim() || null,
    };
  }
  return { mode: "local" };
}

/** What other devices will open, said before the owner confirms it. */
export function exposureSentence(form: RemoteForm): string {
  if (form.mode === "private") {
    const host = form.privateHost.trim() || "this computer's private address";
    return `Devices on your private network or VPN will be able to open Raiker at https://${host}:${form.privatePort.trim() || "8443"}.`;
  }
  if (form.mode === "proxy") {
    const where = form.proxyKind === "socket" ? form.proxySocket.trim() || "the socket" : `127.0.0.1:${form.proxyPort.trim() || "8766"}`;
    return `Anyone who can reach your proxy's https:// address will see Raiker's sign-in page, served through ${where}.`;
  }
  return "Raiker will answer this computer only.";
}

/**
 * Run one sensitive call on a five-minute elevated session granted on the
 * password and a fresh code, then go back to the session the page was using.
 * The server refuses the call unless that code was checked (BUG-358).
 */
export async function withFreshMfa<T>(password: string, code: string, run: () => Promise<T>): Promise<T> {
  const control = getToken();
  const { token } = await auth.elevate(password, code);
  setToken(token);
  try {
    return await run();
  } finally {
    setToken(control);
  }
}

/** The proxy example the dialog shows, for the listener being set up. */
export function proxyExample(form: RemoteForm): string {
  const upstream =
    form.proxyKind === "socket"
      ? `unix/${form.proxySocket.trim() || "/run/raiker/proxy.sock"}`
      : `127.0.0.1:${form.proxyPort.trim() || "8766"}`;
  return `raiker.example.com {\n    reverse_proxy ${upstream}\n}`;
}
