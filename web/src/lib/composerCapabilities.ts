/**
 * COMPOSER-19 — what the composer can offer, declared once and typed.
 *
 * The composer's bar had grown by accretion: every capability Raiker gained
 * arrived as one more permanent control, because a permanent control is the
 * cheapest thing to add and nothing said not to. Chat carried four, Build six,
 * and the review's count of what *could* have been there by the same logic runs
 * to twenty. That is not a styling problem — it is a missing contract. Without
 * one, "should this be visible?" is answered separately, by hand, in each view.
 *
 * So a capability is a record rather than a button:
 *
 *   id                what it is
 *   label / hint      what the owner reads
 *   group             `add` (bring something into this turn) or
 *                     `tools` (ask Raiker to do a kind of thing)
 *   surfaces          the Work surfaces it means anything on
 *   gate              the runtime capability it answers to, when it has one
 *   run               what pressing it does
 *
 * Two rules the type exists to enforce.
 *
 * **Visibility is not authority.** A menu entry reflects a capability the
 * runtime *may* still allow, ask about, or deny when it is invoked. Nothing
 * here grants anything, and the entry for a disabled capability is rendered
 * with the reason rather than hidden — an owner who cannot find "Run command"
 * concludes Raiker cannot run commands, which is a worse answer than "this is
 * off, here is where it is turned on".
 *
 * **A menu entry has to reach something real.** Every `run` here is either a
 * function the view supplies or a link to a page that exists. A composer that
 * lists capability it cannot invoke is the same lie as a toolbar of buttons
 * that do nothing, only tidier.
 */
import type { CapabilityGate, ToolReadiness } from "./apiTypes";
import { isDisabled, isDeferred } from "./capabilityModel";
import type { IconName } from "./icons";

/** The Work surfaces a composer capability can belong to. */
export type ComposerSurface = "chat" | "build" | "design" | "tasks";

/** Which of the composer's two entry points an item hangs from. */
export type ComposerGroup = "add" | "tools";

export interface ComposerCapability {
  id: string;
  label: string;
  /** One line, shown under the label. Says what it does, not that it is safe. */
  hint: string;
  icon: IconName;
  group: ComposerGroup;
  /** Where it means something. An item absent here is absent from that menu. */
  surfaces: readonly ComposerSurface[];
  /**
   * The runtime capability this answers to, when it has one. Attaching files
   * and picking a project are composer state rather than governed actions, so
   * they carry none and are always offered.
   */
  gate?: string;
  /**
   * A route the owner goes to when the capability is off. Without one, a
   * disabled entry says why and stops, which is a dead end.
   */
  enableHref?: string;
  /**
   * The runtime tool whose readiness this entry reports, when it has
   * one. Readiness is a *different question* from the gate above: a search tool
   * the owner has permitted and has not configured a provider for is `Ready` by
   * the gate and `Needs provider` in fact, and a menu that shows one grey row
   * for both sends the owner to the wrong screen.
   */
  readinessTool?: string;
  /** Presentation order within its group. Lower is earlier. */
  priority: number;
}

/**
 * Everything the composer may offer, in one list.
 *
 * `run` is deliberately *not* on the record. What "attach a file" does is
 * different in Chat and Build — different stores, different upload paths — and
 * baking a callback into a module-level constant would either close over view
 * state or invent a global. The view supplies the handlers by id; anything it
 * has no handler for is not shown, which is what keeps the second rule above
 * true by construction rather than by review.
 */
export const COMPOSER_CAPABILITIES: readonly ComposerCapability[] = [
  // ── Add: bring something into this turn ──────────────────────────────────
  {
    id: "attach-file",
    label: "Upload a file",
    hint: "Text, code, images, PDFs. It is stored in this workspace.",
    icon: "file",
    group: "add",
    surfaces: ["chat", "build", "design", "tasks"],
    priority: 10,
  },
  {
    id: "project-files",
    label: "Choose from the project",
    hint: "Files this project already reaches.",
    icon: "folder",
    group: "add",
    surfaces: ["chat", "build", "design"],
    priority: 20,
  },
  {
    id: "mention-file",
    label: "Mention a file from the code map",
    hint: "The same list @ opens, without typing it.",
    icon: "code",
    group: "add",
    surfaces: ["build"],
    gate: "code_map_indexing",
    enableHref: "#/capabilities",
    priority: 30,
  },
  {
    id: "set-project",
    label: "Work in a project",
    hint: "Sets the boundary this turn runs inside.",
    icon: "projects",
    group: "add",
    surfaces: ["chat", "build", "design", "tasks"],
    priority: 40,
  },
  {
    id: "dictate",
    label: "Dictate",
    hint: "Speak instead of typing. Transcribed by the runtime you chose.",
    icon: "mic",
    group: "add",
    surfaces: ["chat", "build", "design", "tasks"],
    priority: 50,
  },
  {
    id: "reference-image",
    label: "Use a reference image",
    hint: "Guides the model towards an existing picture.",
    icon: "design",
    group: "add",
    surfaces: ["design"],
    gate: "image_generation",
    enableHref: "#/capabilities",
    priority: 60,
  },

  // ── Tools: ask Raiker to do a kind of thing ──────────────────────────────
  // WEB-DECISION-04/05 — research is three reads, not one button. They are
  // listed rather than collapsed because they fail differently: search needs a
  // provider, a URL read needs a reachable public address, and extraction needs
  // a page that is not built in the browser. One "Web" row could only report
  // the state of whichever it happened to check.
  {
    id: "web-search",
    label: "Search the web",
    hint: "Finds pages this turn needs. The request leaves this machine.",
    icon: "globe",
    group: "tools",
    surfaces: ["chat", "build", "design", "tasks"],
    gate: "web_fetch",
    readinessTool: "web_search",
    enableHref: "#/capabilities",
    priority: 10,
  },
  {
    id: "web-read",
    label: "Read a URL",
    hint: "Fetches one page as text. HTTPS only, and every redirect is re-checked.",
    icon: "globe",
    group: "tools",
    surfaces: ["chat", "build", "design", "tasks"],
    gate: "web_fetch",
    readinessTool: "web_fetch",
    enableHref: "#/capabilities",
    priority: 11,
  },
  {
    id: "web-extract",
    label: "Extract page content",
    hint: "Pulls the main text, links, tables or metadata out of one page.",
    icon: "file",
    group: "tools",
    surfaces: ["chat", "build", "design", "tasks"],
    gate: "web_fetch",
    readinessTool: "web_extract",
    enableHref: "#/capabilities",
    priority: 12,
  },
  {
    id: "weather",
    label: "Check the weather",
    hint: "Structured conditions and forecast, with the source and its age stated.",
    icon: "globe",
    group: "tools",
    surfaces: ["chat", "build", "design", "tasks"],
    gate: "web_fetch",
    readinessTool: "weather_lookup",
    enableHref: "#/capabilities",
    priority: 13,
  },
  {
    id: "run-command",
    label: "Run a command",
    hint: "In the governed terminal, inside the project boundary.",
    icon: "terminal",
    group: "tools",
    surfaces: ["build"],
    gate: "shell_execution",
    enableHref: "#/capabilities",
    priority: 20,
  },
  {
    id: "use-mcp",
    label: "Use an MCP tool",
    hint: "Tools from the servers you have connected.",
    icon: "tool",
    group: "tools",
    surfaces: ["chat", "build", "tasks"],
    gate: "mcp_connector_runtime",
    enableHref: "#/extensions?tab=mcp",
    priority: 30,
  },
  {
    id: "use-connector",
    label: "Use a connected app",
    hint: "The accounts you have connected under Extensions.",
    icon: "connections",
    group: "tools",
    surfaces: ["chat", "build", "tasks"],
    enableHref: "#/extensions?tab=connectors",
    priority: 40,
  },
  {
    id: "generate-image",
    label: "Generate an image",
    hint: "Opens Design, which is where an image is made and edited.",
    icon: "design",
    group: "tools",
    surfaces: ["chat"],
    gate: "image_generation",
    enableHref: "#/capabilities",
    priority: 50,
  },
  {
    id: "create-task",
    label: "Create a task",
    hint: "Hands this instruction to an agent task instead of answering now.",
    icon: "tasks",
    group: "tools",
    surfaces: ["chat", "build"],
    gate: "task_management_runtime",
    enableHref: "#/capabilities",
    priority: 60,
  },
  {
    id: "schedule",
    label: "Schedule it",
    hint: "Runs on a cadence, with the model chosen now.",
    icon: "clock",
    group: "tools",
    surfaces: ["chat", "build"],
    gate: "scheduled_routines",
    enableHref: "#/capabilities",
    priority: 70,
  },
  {
    id: "use-memory",
    label: "Recall from memory",
    hint: "Approved memories this turn may draw on.",
    icon: "memory",
    group: "tools",
    surfaces: ["chat", "build"],
    enableHref: "#/memory",
    priority: 80,
  },
];

/** Why an entry cannot be invoked right now, or null when it can. */
export interface CapabilityBlock {
  reason: string;
  /** Where the owner goes to change it. */
  href: string | null;
}

/** The short words a menu row prints beside a capability that has readiness. */
export const READINESS_LABELS: Record<ToolReadiness["state"], string> = {
  ready: "Ready",
  needs_provider: "Needs provider",
  blocked: "Blocked by policy",
  unavailable: "Unavailable",
  transient_failure: "Temporarily failed",
};

/**
 * An entry as the menu will draw it: the record, plus whether it is available
 * and why not.
 */
export interface ComposerMenuItem extends ComposerCapability {
  blocked: CapabilityBlock | null;
  /**
   * The operational state, when the entry names a runtime tool. Kept
   * beside `blocked` rather than folded into it: an entry can be permitted and
   * not ready, and the row has to be able to say so without claiming the owner
   * turned something off.
   */
  readiness: ToolReadiness | null;
}

/**
 * The items one menu shows on one surface.
 *
 * `handled` is the set of ids the view has a handler for. Anything else is
 * omitted — not greyed out, omitted — because an entry with nothing behind it
 * is a promise the composer cannot keep, and the review's own acceptance test
 * is that every exposed action reaches a real path or is not exposed.
 *
 * A capability that is *governed off* is a different case and stays: the owner
 * asked what Raiker can do, and "this exists and is currently off" is the true
 * answer. It carries the reason and the route that changes it.
 */
export function composerMenu(
  group: ComposerGroup,
  surface: ComposerSurface,
  gates: readonly CapabilityGate[],
  handled: ReadonlySet<string>,
  readiness: readonly ToolReadiness[] = [],
): ComposerMenuItem[] {
  // A gate list that is not a list is no evidence about anything. This is not
  // defensive habit: `/api/capability-gates` answering with an object rather
  // than an array — a truncated body, a proxy's error page served as JSON, a
  // host older than the build — used to reach `.find` here and take the whole
  // composer down, which is a far worse outcome than a menu that offers a
  // capability the runtime will judge properly when it is invoked.
  const known: readonly CapabilityGate[] = Array.isArray(gates) ? gates : [];
  return COMPOSER_CAPABILITIES.filter(
    (capability) =>
      capability.group === group &&
      capability.surfaces.includes(surface) &&
      handled.has(capability.id),
  )
    .map((capability) => ({
      ...capability,
      blocked: blockFor(capability, known),
      readiness: readinessFor(capability, readiness),
    }))
    // A capability with no executor in this build is not "off", it is absent;
    // offering it with a route that cannot turn it on is the dead end this
    // whole list exists to avoid.
    .filter((item) => item.blocked?.reason !== DEFERRED)
    .sort((left, right) => left.priority - right.priority);
}

const DEFERRED = "__deferred__";

function blockFor(
  capability: ComposerCapability,
  gates: readonly CapabilityGate[],
): CapabilityBlock | null {
  if (capability.gate === undefined) return null;
  const gate = gates.find((entry) => entry.capability === capability.gate);
  // A gate Raiker has not reported is not a gate that is off. Saying nothing is
  // the honest state: the runtime still judges the action when it is invoked.
  if (gate === undefined) return null;
  if (isDeferred(gate)) return { reason: DEFERRED, href: null };
  if (!isDisabled(gate)) return null;
  return {
    reason: "Turned off in Permissions",
    href: capability.enableHref ?? "#/capabilities",
  };
}

/**
 * The readiness row for *capability*, or null.
 *
 * Null for an entry that names no runtime tool, and null for a tool the host
 * said nothing about — a missing row is not evidence of a problem, and printing
 * "Unavailable" because a payload was short would be inventing the one thing
 * this field exists to stop being invented.
 */
function readinessFor(
  capability: ComposerCapability,
  rows: readonly ToolReadiness[],
): ToolReadiness | null {
  if (capability.readinessTool === undefined) return null;
  const known: readonly ToolReadiness[] = Array.isArray(rows) ? rows : [];
  return known.find((row) => row.tool === capability.readinessTool) ?? null;
}
