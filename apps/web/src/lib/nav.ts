import type { IconName } from "./icons";

export interface NavItem { id: string; label: string; icon: IconName; hint: string; }
export type NavGroupId = "core" | "knowledge" | "manage" | "observe" | "support";
export interface NavGroup { id: NavGroupId; label: string; collapsible: boolean; items: NavItem[]; }

// Stable workbench navigation: work objects stay together, governance lives in
// one place, and read-first operational evidence is one destination rather than
// three competing pages.
export const NAV_GROUPS: NavGroup[] = [
  { id: "core", label: "Work", collapsible: false, items: [
    // VIS-13 — "Workbench" was a name for a page whose job is to be the place
    // you land. "Home" is what it is, and it costs the owner no vocabulary.
    { id: "home", label: "Home", icon: "home", hint: "Resume governed work and see what needs attention" },
    { id: "new-chat", label: "Chat", icon: "chat", hint: "Start or continue a governed conversation" },
    { id: "build", label: "Build", icon: "code", hint: "Code against a repository with Plan, Edit, and Auto" },
    // Design sits with Chat and Build because it is the same kind of thing: you
    // describe what you want and a model answers. It was last in the group, next
    // to Messaging, which put a making surface among the plumbing.
    { id: "design", label: "Design", icon: "design", hint: "Create and edit images with a connected model" },
    // C18 — this destination stopped being only a search. With an empty box it
    // is the board of everything the owner has going, chats and routine threads
    // alike; with a query it is the search it always was.
    { id: "search-chat", label: "Threads", icon: "search", hint: "Everything you have going, and a search across it" },
    { id: "tasks", label: "Tasks", icon: "tasks", hint: "Agent tasks and progress" },
    { id: "projects", label: "Projects", icon: "projects", hint: "Named scopes for ongoing work" },
    // Approvals sat under Manage with the setup pages, and it is not one: a
    // decision waiting on you is the work, arriving many times a day, while
    // Permissions and Models are configured once and revisited. It moved here
    // when Manage left the sidebar for the gear.
    { id: "approvals", label: "Approvals", icon: "approvals", hint: "Decisions waiting on you" },
    // A channel is a place a person reaches Raiker from, which is a different
    // kind of thing from the connectors, servers and hooks the agent *uses* —
    // it was a tab inside Extensions and is its own destination now.
    { id: "messaging", label: "Messaging", icon: "chat", hint: "Channels that reach Raiker from somewhere else" },
  ] },
  { id: "knowledge", label: "Knowledge", collapsible: true, items: [
    { id: "memory", label: "Memory", icon: "activity", hint: "Approved memories the agent can recall" },
    { id: "brain", label: "Knowledge Map", icon: "map", hint: "Governed workspace relationships and sources" },
  ] },
  { id: "manage", label: "Manage", collapsible: true, items: [
    { id: "capabilities", label: "Permissions", icon: "capabilities", hint: "What the agent may do, and how it must ask" },
    { id: "models", label: "Models", icon: "models", hint: "Model profiles and provider gates" },
    { id: "extensions", label: "Extensions", icon: "connections", hint: "Connectors, MCP servers, skills, hooks and plugins" },
  ] },
  { id: "observe", label: "Observe", collapsible: true, items: [
    { id: "observe", label: "Observability", icon: "diagnostics", hint: "Readiness, audit log, checkpoints, live work, and notifications" },
  ] },
  { id: "support", label: "Support", collapsible: true, items: [
    { id: "guide", label: "Guide", icon: "info", hint: "How Raiker works, in the product" },
    { id: "settings", label: "Settings", icon: "settings", hint: "Runtime, security posture, appearance" },
  ] },
];
export const NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((group) => group.items);
export const DEFAULT_ROUTE = "home";

/**
 * Which groups the sidebar carries, and which live behind the gear.
 *
 * `NAV_GROUPS` stays the complete route registry — `routeFromHash` resolves
 * against `NAV_ITEMS`, so a destination dropped from that list stops being
 * reachable at all rather than merely moving. These two arrays only decide
 * *where a link to it is drawn*.
 *
 * The split is by how often you go there. Core and Knowledge are the work: you
 * open them many times an hour and they earn a permanent rail. Manage, Observe
 * and Support are the things you set up once and revisit when something needs
 * changing — a standing sidebar row for each was eight rows of furniture for
 * work that happens on a handful of days.
 */
export const SIDEBAR_GROUP_IDS: NavGroupId[] = ["core", "knowledge"];

/**
 * The destinations the permanent rail draws. VIS-01.
 *
 * Grouping and route registration are one thing; what the rail is worth
 * spending a permanent row on is another, and they were the same list. Core
 * held nine peers — Workbench, Chat, Build, Design, Threads, Tasks, Projects,
 * Approvals, Messaging — so before starting work the owner had to learn nine
 * product nouns and decide which of them they were in. A rail is not an index.
 *
 * What comes off it, and where each goes instead:
 *
 * * **Approvals** — a decision waiting on you is not a place you navigate to,
 *   it is a thing that arrives. It is a counted button in the top bar now,
 *   visible from every route, which is strictly more available than a row you
 *   have to be looking at the sidebar to notice.
 * * **Messaging** — a real destination, reached rarely. It keeps its route and
 *   is listed in the gear's window.
 *
 * **VIS2-03 put Design back.** Taking it off the rail was right when Design was
 * a form over a gallery reached a few times a month. It is a Work mode now —
 * Chat, Build and Design are the three ways to give Raiker something to do —
 * and a Work mode whose only discovery path is a window behind a gear reads as
 * a feature the product is unsure about. Its peers are on the rail; so is it.
 *
 * Nothing is unreachable: `NAV_ITEMS` is still the route registry, the gear's
 * window lists everything this array leaves out, and the command palette finds
 * all of them by name.
 */
export const SIDEBAR_ITEM_IDS: string[] = [
  "home",
  "new-chat",
  "build",
  "design",
  "search-chat",
  "tasks",
  "projects",
  "memory",
  "brain",
];

/**
 * The three Work modes, in the order every surface must list them.
 *
 * VIS2-03. Chat, Build and Design are peers: you say what you want and Raiker
 * answers with prose, with a change, or with an image. The top bar's mode
 * switch drew two of them, which told a new owner that Design was a lesser
 * kind of thing reached from somewhere else. One array, so the switch, the
 * rail and the command palette cannot drift into three different answers about
 * what the product is for.
 */
export const WORK_MODES: {
  id: string;
  label: string;
  hash: string;
  icon: IconName;
}[] = [
  { id: "new-chat", label: "Chat", hash: "#/new-chat", icon: "chat" },
  { id: "build", label: "Build", hash: "#/build", icon: "code" },
  { id: "design", label: "Design", hash: "#/design", icon: "design" },
];

/** True when a route is one of the three Work modes. */
export function isWorkMode(route: string): boolean {
  return WORK_MODES.some((mode) => mode.id === route);
}

export const SIDEBAR_GROUPS: NavGroup[] = NAV_GROUPS.filter((g) =>
  SIDEBAR_GROUP_IDS.includes(g.id),
)
  .map((group) => ({
    ...group,
    items: group.items.filter((item) => SIDEBAR_ITEM_IDS.includes(item.id)),
  }))
  .filter((group) => group.items.length > 0);

/**
 * Everything the gear's window lists, in the order it lists them.
 *
 * Every destination that is not on the rail, which now includes the ones taken
 * off it above — a page with no link anywhere is a page that does not exist.
 */
export const HUB_GROUPS: NavGroup[] = NAV_GROUPS.map((group) => ({
  ...group,
  items: group.items.filter((item) => !SIDEBAR_ITEM_IDS.includes(item.id)),
})).filter((group) => group.items.length > 0);

/**
 * Tabs inside a consolidated destination. The hub owns the tab list so a deep
 * link, the sidebar, and the hub's own tab strip all resolve to the same panel.
 */
export const HUB_TABS: Record<string, string[]> = {
  // MODEL-03 — organised by the questions an owner actually arrives with, not
  // by which table the data lives in.
  //
  // The six tabs it replaces — Local, Hosted, Hugging Face, Activity, Routing,
  // Pricing — were a filing system: three of them named *where a model is
  // stored*, which is an attribute of the answer rather than a choice anyone
  // makes, and none of them answered "what is running my work". Overview does,
  // first; My models is the inventory; Add model is the one errand that used to
  // be split three ways; Runtime & routing is what is serving and what happens
  // when it cannot; Usage is the bill and the rates that produce it, which were
  // two tabs asking the owner to do the multiplication.
  models: [
    "overview",
    "models",
    "add",
    "runtime",
    "usage",
  ],
  extensions: ["connectors", "mcp", "skills", "hooks", "plugins"],
  observe: ["overview", "sessions", "activity", "checkpoints", "work", "notifications"],
  // Every section the settings rail renders, in rail order. The two lists have
  // to agree: a section the rail shows but this list omits is a deep link that
  // silently opens General instead, which reads as a working link to the wrong
  // page. `web-access` and `git-credential` were in exactly that state before
  // `privacy` joined them, and `updates` still was until BUG-256's sweep checked
  // the whole list against the rail rather than the one entry it was adding.
  settings: [
    "general",
    "notification",
    "personalisation",
    "security",
    "privacy",
    "account",
    "web-access",
    "git-credential",
    "runtime",
    "updates",
  ],
};

/**
 * Routes that were their own destination before the hubs existed. Existing
 * deep links (and the cross-links session detail already emits) must keep
 * working, so each one resolves to its hub and opens the matching tab rather
 * than silently falling back to the Workbench.
 */
const ROUTE_ALIASES: Record<string, { route: string; tab: string }> = {
  connections: { route: "extensions", tab: "connectors" },
  mcp: { route: "extensions", tab: "mcp" },
  activity: { route: "observe", tab: "activity" },
  checkpoints: { route: "observe", tab: "checkpoints" },
  diagnostics: { route: "observe", tab: "overview" },
  work: { route: "observe", tab: "work" },
  notifications: { route: "observe", tab: "notifications" },
  sessions: { route: "observe", tab: "sessions" },
  // Channels left Extensions for their own page.
  channels: { route: "messaging", tab: "" },
};

/**
 * Tab ids a hub used to have, mapped to the panel that now owns their content.
 *
 * A tab id travels: it sits in bookmarks, in links other views emit, and in
 * e2e specs. Renaming one without a mapping does not fail loudly — the request
 * simply misses `HUB_TABS` and falls through to the hub's first panel, which
 * looks like a working link to the wrong place.
 */
const HUB_TAB_ALIASES: Record<string, Record<string, string>> = {
  // The single "Providers" scroll became Local and Hosted; "Library" was the
  // local GGUF index, now part of Local; "Discover" was the Hub search.
  models: {
    // The pre-MODEL-03 six, each pointing at whichever panel took over its
    // content. `local` and `hosted` land on the inventory rather than on Add:
    // a link named for where a model lives was almost always followed to look
    // at models the owner already had.
    local: "models",
    hosted: "models",
    huggingface: "add",
    activity: "runtime",
    routing: "runtime",
    pricing: "usage",
    providers: "models",
    library: "runtime",
    discover: "add",
    downloads: "runtime",
    // "Posture" was a tab holding four read-only facts and a paragraph. The
    // facts moved onto the provider cards, where they explain what is under
    // them; the paragraph moved to the guide. The alias keeps every link that
    // named the tab working, which is what this map is for.
    posture: "add",
  },
  // "Diagnostics" read the same `diagnostics` object Overview reads and restated
  // four of its six cards from it. What was unique — runtime health transitions,
  // memory integrity and its repair, and a failed readiness check's remediation —
  // is a section of Overview now.
  observe: {
    diagnostics: "overview",
  },
};

/**
 * The path part of a hash, without the leading `#/` and without a `?query`.
 *
 * A hub tab may be addressed two ways — `#/extensions?tab=mcp` and
 * `#/extensions/mcp` — so this returns the segments, and the two readers below
 * decide what each means.
 */
function rawSegments(hash: string): string[] {
  return hash
    .replace(/^#\/?/, "")
    .split("?")[0]
    .split("/")
    .filter((part) => part !== "");
}

function rawRoute(hash: string): string {
  return rawSegments(hash)[0] ?? "";
}

export function routeFromHash(hash: string): string {
  const raw = rawRoute(hash);
  if (raw === "model-setup") return raw;
  if (NAV_ITEMS.some((item) => item.id === raw)) return raw;
  return ROUTE_ALIASES[raw]?.route ?? DEFAULT_ROUTE;
}

/**
 * The tab a hash selects, or null when the route has no tabs or the request
 * names a tab the hub does not have. An unknown tab falls back to the hub's
 * first panel rather than rendering nothing.
 */
/**
 * The `?section=` a guide deep link names, or null.
 *
 * Guide pages are not hub tabs — the set is whatever the install shipped, so it
 * cannot be validated against a constant here. The view resolves it against the
 * sections the API actually returned and falls back to the first one.
 */
export function sectionFromHash(hash: string): string | null {
  const requested = new URLSearchParams(hash.split("?", 2)[1] ?? "").get("section");
  return requested !== null && /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(requested) ? requested : null;
}

export function tabFromHash(hash: string): string | null {
  const segments = rawSegments(hash);
  const raw = segments[0] ?? "";
  const route = routeFromHash(hash);
  const tabs = HUB_TABS[route];
  if (tabs === undefined) return null;
  // `?tab=` is the form this app writes. `#/extensions/mcp` is the form a person
  // guesses, and every other product they use addresses a tab that way — so it
  // was a link that looked like it worked and opened the Workbench instead,
  // which is the exact failure `HUB_TAB_ALIASES` above exists to prevent, one
  // level up. The query wins where both are present, because that is the one
  // this app emits.
  // `?section=` is the guide's parameter and reads naturally for a Settings
  // section, so a link written by hand — or by a surface that had it wrong for
  // real, which is how this was found — resolves rather than silently opening
  // the first panel. Same reasoning as the path form above: three spellings, one
  // destination, and none of them a link that looks like it works.
  const query = new URLSearchParams(hash.split("?", 2)[1] ?? "");
  const requested = query.get("tab") ?? query.get("section") ?? segments[1] ?? null;
  if (requested !== null && tabs.includes(requested)) return requested;
  const supersededBy = requested === null ? undefined : HUB_TAB_ALIASES[route]?.[requested];
  if (supersededBy !== undefined && tabs.includes(supersededBy)) return supersededBy;
  const aliased = ROUTE_ALIASES[raw];
  if (aliased !== undefined && aliased.route === route) return aliased.tab;
  return tabs[0];
}

// Routes that own a page but deliberately have no sidebar entry. Without them
// `navItem` falls back to the first nav item for anything it does not know, so
// the first-run model setup screen was titled "Workbench" and carried the
// Workbench hint — the other half of FIXED-144.
const OFF_NAV_ITEMS: NavItem[] = [
  {
    id: "model-setup",
    label: "Finish setup",
    icon: "models",
    hint: "Confirm model, privacy and backup choices before your first turn",
  },
];

export function navItem(id: string): NavItem {
  return (
    NAV_ITEMS.find((item) => item.id === id) ??
    OFF_NAV_ITEMS.find((item) => item.id === id) ??
    NAV_ITEMS[0]
  );
}
