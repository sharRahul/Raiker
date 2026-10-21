/**
 * QUI-L07 — how a connection's state is put into words on Connections ›
 * Services. Moved from the Extensions hub's Connectors tab unchanged in
 * meaning: installed, connected, enabled and usable stay four separate facts,
 * and a connection that is not usable says which one is missing.
 */
import type { ExtensionView, StoreConnector } from "./apiTypes";

/** One step of `LifecycleTrack`. */
export interface LifecycleStep {
  label: string;
  met: boolean;
  note: string;
}

/** One status for a service row, in words, never colour alone. */
export function connectionStatus(connector: StoreConnector): string {
  if (connector.activity_status === "processing") return "Working now";
  if (!connector.installed) return "Not connected";
  if (connector.auth_status === "reauth_required") return "Needs you to sign in again";
  if (connector.auth_status !== "connected") return "Needs its account";
  if (!connector.enabled) return "Off for this session";
  return "Connected";
}

/** The four readiness facts the server reports, as steps. */
export function connectionSteps(extension: ExtensionView): LifecycleStep[] {
  return [
    {
      label: "Installed",
      met: extension.installed,
      note: extension.installed ? "Present in this workspace" : "Not added yet",
    },
    {
      label: "Account connected",
      met: extension.connected,
      note: extension.connected
        ? "A credential is stored in the vault"
        : "No stored credential — the value is never shown here either way",
    },
    {
      label: "Enabled for the session",
      met: extension.enabled,
      note: extension.enabled ? "Turned on for this session" : "Turned off",
    },
    {
      label: "Usable now",
      met: extension.usable,
      note: extension.usable
        ? "Raiker will accept a governed call"
        : "Raiker still refuses calls",
    },
  ];
}

/** What stops a connection, and where it is fixed. */
export function connectionBlockedCopy(extension: ExtensionView): string {
  switch (extension.blocked_reason) {
    case "not_installed":
      return "Not added yet. Add it with Add connection.";
    case "reauthentication_required":
      return "The stored credential expired. Connect the account again to continue.";
    case "account_not_connected":
      return "Added, but no account credential is stored for it.";
    case "not_enabled_for_session":
      return "Connected, but not enabled for this session.";
    case "capability_gate_closed":
      return "Its permission is turned off, so every call is refused. Turn it on in Permissions.";
    // BUG-11 — enabled is not the same as enabled at runtime level, and the
    // two need different actions from the owner.
    case "capability_below_runtime_level":
      return "Its permission is on, but below the level that lets Raiker use it. Raise it in Permissions.";
    case "capability_decision_mode_deny":
      return "Its permission is set to Never, so every proposed call is refused. Change it in Permissions.";
    case "egress_host_not_allowlisted":
      return "Its host is not on the connector egress allowlist.";
    case "connection_killed":
      return "The connection was stopped and will not restart on its own.";
    case "circuit_breaker_paused":
      return "The monitor paused this connection after an anomaly.";
    case "not_connected":
      return "No successful handshake yet, so no tools are available.";
    default:
      return "Ready to use in a governed turn.";
  }
}
