/**
 * What the Extensions page should say before it says anything else.
 *
 * The page opened on five equal tabs — Connectors, MCP servers, Skills, Hooks,
 * Plugins — which is a filing system by *kind of thing*, not an answer to why
 * anyone came. Nobody arrives at this page thinking "I would like to look at
 * the MCP category". They arrive asking one of three questions:
 *
 *   1. What can Raiker reach right now?
 *   2. Is anything I installed not working?
 *   3. What is the one thing that fixes it?
 *
 * The tabs answer none of those without being chosen first, and the second
 * question is the expensive one: a connector that is installed and blocked
 * looks exactly like one that is installed and fine until you open its
 * category and read the row.
 *
 * This module derives the answers from the readiness the page already loads, so
 * the overview cannot disagree with the tab underneath it. It is deliberately
 * *exception-led* (the exception-led rule): a working extension gets a count, not a card. A
 * wall of green cards reports "nothing is wrong" in the most expensive way
 * available, and it trains the owner to skim past the one card that is not
 * green.
 */
import type { ExtensionView } from "./apiTypes";

/** One thing that is not working, and the one action that addresses it. */
export interface ExtensionException {
  extensionId: string;
  name: string;
  kind: string;
  /** Why it cannot be used, in the runtime's own words. */
  reason: string;
  /** The tab that owns the fix, so a remedy is never a dead end. */
  tab: string;
}

/** What the owner can reach, counted rather than listed. */
export interface ExtensionReach {
  usable: number;
  installed: number;
  /** Tools the usable extensions actually offer. Zero is worth saying. */
  tools: number;
}

/** Which tab owns each kind, so an exception can point at its own fix. */
const TAB_FOR_KIND: Record<string, string> = {
  connector: "connectors",
  connectors: "connectors",
  mcp_server: "mcp",
  mcp_servers: "mcp",
  mcp: "mcp",
  skill: "skills",
  skills: "skills",
  hook: "hooks",
  hooks: "hooks",
  plugin: "plugins",
  plugins: "plugins",
  panels: "plugins",
};

export function tabForKind(kind: string): string {
  return TAB_FOR_KIND[kind] ?? "connectors";
}

/**
 * Everything installed that cannot currently be used, newest problem first.
 *
 * "Installed but not usable" is the only state worth a card. Not installed is
 * not a problem — it is a thing the owner has not done — and usable is the
 * ordinary case.
 */
export function extensionExceptions(
  extensions: readonly ExtensionView[] | null | undefined,
): ExtensionException[] {
  const known: readonly ExtensionView[] = Array.isArray(extensions) ? extensions : [];
  return known
    .filter((extension) => extension.installed && !extension.usable)
    .map((extension) => ({
      extensionId: extension.extension_id,
      name: extension.display_name,
      kind: extension.kind,
      // The runtime's own reason, never a paraphrase: a page that rewords a
      // refusal can reword it into something the runtime did not say.
      reason: (extension.blocked_reason ?? extension.detail ?? "").trim() || "Not usable yet.",
      tab: tabForKind(extension.kind),
    }));
}

/** What is working, as counts. */
export function extensionReach(
  extensions: readonly ExtensionView[] | null | undefined,
): ExtensionReach {
  const known: readonly ExtensionView[] = Array.isArray(extensions) ? extensions : [];
  const usable = known.filter((extension) => extension.usable);
  return {
    usable: usable.length,
    installed: known.filter((extension) => extension.installed).length,
    tools: usable.reduce((total, extension) => total + (extension.tool_count || 0), 0),
  };
}

/** The lead sentence: what Raiker can reach, in words rather than a stat grid. */
export function reachSentence(reach: ExtensionReach): string {
  if (reach.installed === 0) {
    return "Nothing is installed yet. Connect an account, add an MCP server, or install a skill.";
  }
  if (reach.usable === 0) {
    return `${reach.installed} installed, and none of them can be used yet.`;
  }
  const tools =
    reach.tools === 0
      ? ""
      : reach.tools === 1
        ? ", offering 1 tool"
        : `, offering ${reach.tools} tools`;
  return `${reach.usable} of ${reach.installed} installed extensions can be used${tools}.`;
}
