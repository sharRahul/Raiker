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

/**
 * What is working, as counts.
 *
 * **Counted over the same five kinds the inventory is.** It used to read
 * `/api/extensions` alone, which covers connectors and MCP servers and not
 * skills, hooks or plugins — so a workspace with seven installed skills was
 * told *"Nothing is installed yet."* Building the inventory beside it is what
 * made that visible, and leaving the two to disagree on one screen would have
 * been worse than either of them being wrong on its own.
 *
 * `tools` stays over the extension views, because a tool count is something
 * only a connector or an MCP server has. A skill offers no tool; it is
 * instructions.
 */
export function extensionReach(inputs: ExtensionInventoryInputs): ExtensionReach {
  const rows = extensionInventory(inputs);
  const known: readonly ExtensionView[] = Array.isArray(inputs.extensions)
    ? inputs.extensions
    : [];
  return {
    usable: rows.reduce((total, row) => total + row.usable, 0),
    installed: rows.reduce((total, row) => total + row.installed, 0),
    tools: known
      .filter((extension) => extension.usable)
      .reduce((total, extension) => total + (extension.tool_count || 0), 0),
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

/**
 * REM-EXT-01 — what is installed, grouped by kind.
 *
 * The overview said how many extensions were usable and named the ones that
 * were not, which answers "is anything wrong" and leaves "what have I got"
 * to be worked out by opening five tabs in turn. The inventory is the third
 * thing the review asks this page to lead with, beside the exceptions and
 * **Add**, and it is a count per kind rather than a card per extension: a card
 * per working extension is the most expensive possible way to report that
 * nothing is wrong.
 */
export interface ExtensionInventoryRow {
  kind: string;
  label: string;
  installed: number;
  usable: number;
  /** The hub tab that lists this kind. */
  tab: string;
}

/** Which tab lists each kind, and what that kind is called on the row. */
const KIND_TABS: Record<string, { label: string; tab: string }> = {
  connector: { label: "Connectors", tab: "connectors" },
  mcp_server: { label: "MCP servers", tab: "mcp" },
};

/**
 * What the inventory is counted from.
 *
 * Five kinds, from four reads, because that is what the product actually has:
 * `/api/extensions` covers connectors and MCP servers and **not** skills, hooks
 * or plugins, which have their own routes. An inventory built from the first
 * alone would have claimed to say what is installed while silently omitting
 * three of the five kinds, which is a worse answer than the five tabs it
 * replaces.
 */
export interface ExtensionInventoryInputs {
  extensions: readonly ExtensionView[] | null | undefined;
  /** Installed skills, and whether each is switched on. */
  skills: ReadonlyArray<{ active: boolean }> | null | undefined;
  /** Loaded hook rules, and whether hooks are running at all. */
  hooks: { rule_count: number; active: boolean } | null | undefined;
  plugins: ReadonlyArray<{ status: string }> | null | undefined;
}

export function extensionInventory(
  inputs: ExtensionInventoryInputs,
): ExtensionInventoryRow[] {
  const rows = new Map<string, ExtensionInventoryRow>();
  const add = (kind: string, label: string, tab: string, usable: boolean) => {
    const row = rows.get(kind) ?? { kind, label, installed: 0, usable: 0, tab };
    row.installed += 1;
    if (usable) row.usable += 1;
    rows.set(kind, row);
  };

  const known: readonly ExtensionView[] = Array.isArray(inputs.extensions)
    ? inputs.extensions
    : [];
  for (const extension of known) {
    if (!extension.installed) continue;
    // An unknown kind is named as itself rather than hidden: a build that grows
    // a sixth should show it here before anyone remembers to add a row for it.
    const named = KIND_TABS[extension.kind];
    add(
      extension.kind,
      named?.label ?? extension.kind,
      named?.tab ?? "connectors",
      extension.usable,
    );
  }
  for (const skill of inputs.skills ?? []) {
    add("skill", "Skills", "skills", skill.active);
  }
  if (inputs.hooks != null) {
    for (let index = 0; index < inputs.hooks.rule_count; index += 1) {
      // A rule that is loaded while hooks are switched off is installed and not
      // usable, which is exactly the distinction this column is for.
      add("hook", "Hooks", "hooks", inputs.hooks.active);
    }
  }
  for (const plugin of inputs.plugins ?? []) {
    add("plugin", "Plugins", "plugins", plugin.status === "enabled");
  }
  return [...rows.values()].sort((a, b) => a.label.localeCompare(b.label));
}
