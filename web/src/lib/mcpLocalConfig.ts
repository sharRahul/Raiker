/**
 * MCP-HOST — a local MCP server as Claude Desktop, Cursor and Codex describe one.
 *
 * Claude Desktop and Cursor keep `{"mcpServers": {"name": {"command", "args",
 * "env"}}}`; Codex keeps the same three fields under `[mcp_servers.name]`. An
 * owner who already runs a server there pastes that block, and each server is
 * added as they had it. The form takes the same three fields typed by hand.
 */

export interface LocalServerSpec {
  name: string;
  command: string;
  args: string[];
  env: Record<string, string>;
}

/** Arguments one per line; blank lines dropped, nothing else interpreted. */
export function argsFromLines(text: string): string[] {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line !== "");
}

/** `NAME=value` per line. A line without `=` or with an unusable name is refused by name. */
export function envFromLines(text: string): { env: Record<string, string>; refused: string[] } {
  const env: Record<string, string> = {};
  const refused: string[] = [];
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (line === "") continue;
    const at = line.indexOf("=");
    const name = at > 0 ? line.slice(0, at).trim() : "";
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(name)) {
      refused.push(line.split("=")[0]!.trim() || line);
      continue;
    }
    env[name] = line.slice(at + 1);
  }
  return { env, refused };
}

/**
 * Every stdio server in a pasted Claude Desktop / Cursor block (or a bare map of
 * servers). A remote entry (`url`) is skipped and named, because a remote server
 * is added by its address, not by a command.
 */
export function serversFromConfig(text: string): { servers: LocalServerSpec[]; skipped: string[] } {
  const parsed: unknown = JSON.parse(text);
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new SyntaxError("not an object");
  }
  const root = parsed as Record<string, unknown>;
  const map = (root.mcpServers ?? root.mcp_servers ?? root) as Record<string, unknown>;
  const servers: LocalServerSpec[] = [];
  const skipped: string[] = [];
  for (const [name, value] of Object.entries(map)) {
    if (value === null || typeof value !== "object") {
      skipped.push(name);
      continue;
    }
    const entry = value as Record<string, unknown>;
    if (typeof entry.command !== "string" || entry.command.trim() === "") {
      skipped.push(name);
      continue;
    }
    const args = Array.isArray(entry.args) ? entry.args.map((part) => String(part)) : [];
    const env: Record<string, string> = {};
    if (entry.env && typeof entry.env === "object") {
      for (const [key, val] of Object.entries(entry.env as Record<string, unknown>)) env[key] = String(val);
    }
    servers.push({ name, command: entry.command.trim(), args, env });
  }
  return { servers, skipped };
}
