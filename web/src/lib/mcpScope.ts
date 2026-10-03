/**
 * What an MCP server can reach, and why an owner might trust it — release-
 * readiness review §3.11.
 *
 * UX-MCP-02: an owner could not see the blast radius of a server before
 * connecting it — tools, roots and resources, network, secrets, writable paths
 * and the Permissions it needs. UX-MCP-03: tool names and JSON arguments are no
 * explanation of trust; a card needs a purpose, a risk category, a source, and
 * what happened the last times it ran.
 *
 * The facts come from the server (`McpScope`, read from the launcher and the
 * endpoint policy); this module only words them, so the page cannot promise a
 * boundary the process does not have.
 */
import type { McpServer, McpSession } from "./apiTypes";
import { relativeTime } from "./format";

type Scope = NonNullable<McpServer["scope"]>;

export interface ScopeLine {
  label: string;
  value: string;
  /** A fact an owner should weigh, drawn in the warning tone. */
  caution?: boolean;
}

const PERMISSION_NAMES: Record<string, string> = {
  mcp_connector_runtime: "MCP connections",
  mcp_builder_runtime: "MCP server builder",
};

export function scopeLines(scope: Scope): ScopeLine[] {
  const local = scope.runs_on === "this_machine";
  const lines: ScopeLine[] = [];
  lines.push({
    label: "Runs",
    value: local
      ? "On this machine, as the account Raiker runs as, started in the workspace folder."
      : "On another machine. Raiker sends it requests; nothing of it runs here.",
  });
  lines.push({
    label: "Network",
    caution: scope.network === "unrestricted" || scope.encrypted === false,
    value:
      scope.network === "unrestricted"
        ? "Not confined — the process has this machine's network."
        : scope.network === "loopback"
          ? `This machine only${scope.encrypted ? "" : ", unencrypted"}.`
          : scope.network === "private_network"
            ? `Your own network${scope.encrypted ? " over HTTPS" : ", unencrypted"}.`
            : scope.network === "public"
              ? "A public service over HTTPS."
              : "An address Raiker does not recognise.",
  });
  lines.push({
    label: "Files it can write",
    caution: scope.writable === "account",
    value:
      scope.writable === "account"
        ? "Anything the account Raiker runs as may write — Raiker does not confine it."
        : "None on this machine.",
  });
  lines.push({
    label: "Secrets",
    caution: scope.granted_environment.length > 0 || Boolean(scope.token_reference),
    value: local
      ? scope.granted_environment.length > 0
        ? `Started with ${scope.environment.join(", ")} — including ${scope.granted_environment.join(", ")}, which you granted.`
        : `None. It is started with ${scope.environment.join(", ")} and nothing else — no provider key.`
      : scope.token_reference
        ? `The token in ${scope.token_reference}, sent to this endpoint only. Its value is never stored here.`
        : "None — no token is sent.",
  });
  lines.push({
    label: "Folders and files",
    value:
      !scope.roots_shared && !scope.resources_read
        ? "Raiker tells it no folder and hands it no file; it sees only what a tool call passes."
        : "It is told folders or handed files.",
  });
  lines.push({
    label: "Tools",
    value:
      scope.tool_count === null
        ? "Not known until Test lists them. Every call is then reviewed by Permissions."
        : `${scope.tool_count} listed by the last Test. Every call is reviewed by Permissions.`,
  });
  lines.push({
    label: "Permissions",
    value: scope.required_permissions.map((key) => PERMISSION_NAMES[key] ?? key).join(" and "),
  });
  return lines;
}

/** UX-MCP-03 — one word for the class of risk. */
export function riskLabel(scope: Scope): string {
  if (scope.risk === "local_process") return "Runs code on this machine";
  if (scope.risk === "own_network") return "Reaches your own network";
  return "Sends data to a remote service";
}

export function sourceLabel(server: Pick<McpServer, "source" | "source_plugin">): string {
  if (server.source === "raiker_sample") return "Sample Raiker generated";
  if (server.source === "plugin")
    return `Offered by the plugin ${server.source_plugin ?? "you installed"}`;
  return "Added by you";
}

export function purposeLine(server: Pick<McpServer, "purpose" | "purpose_from">): string {
  if (!server.purpose) return "It has not said what it is for. Run Test to read its tools.";
  if (server.purpose_from === "plugin") return server.purpose;
  // The server's own sentence about a tool — untrusted, and said to be so.
  return `It says: “${server.purpose}”`;
}

/** Last use and the outcomes of recent sessions, in one line. */
export function recentUse(sessions: McpSession[] | undefined): string {
  if (!sessions?.length) return "Never used";
  const latest = sessions.reduce((a, b) => (a.started_at > b.started_at ? a : b));
  const failed = sessions.filter((session) => session.outcome === "error").length;
  const ok = sessions.length - failed;
  const tally = failed ? `${ok} ok, ${failed} failed` : `${ok} ok`;
  return `Last used ${relativeTime(latest.started_at)} · last ${sessions.length}: ${tally}`;
}
