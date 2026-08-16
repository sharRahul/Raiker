/**
 * Composer ergonomics shared by Chat and Build (GAP-BUILD B19, GAP-CHAT C14).
 *
 * Both composers were a textarea and a Send button. Everything a person does
 * dozens of times a day in a class-leading assistant — start a slash command,
 * point at a file with `@`, let the box grow with what is being written — was
 * absent, and each absence is small on its own. Together they are most of the
 * felt difference in daily use.
 *
 * The rules this module exists to keep:
 *
 * 1. **A listed command is a command that exists.** Every entry names an action
 *    the surface really performs. There is no "coming soon" row: an inert menu
 *    item is a promise the product does not keep, and the backlog this closes is
 *    full of exactly that.
 * 2. **Nothing here grants anything.** A slash command is a shortcut to a
 *    control the owner already has. It does not raise a capability, skip an
 *    approval, or reach the model with more authority than typing would.
 * 3. **Completion reads what the owner already indexed.** `@` offers paths out
 *    of the code map the owner built, never a live scan of their disk, so a
 *    completion menu can never become a listing surface (see
 *    `GET /api/code/map/paths`).
 * 4. **Parsing is pure.** Everything here is a function of the text and the
 *    caret. It is the reason this can be unit-tested without a browser, and the
 *    reason a mis-parse can never send something the owner did not type.
 */

/** Which composer is asking. The two surfaces do different work. */
export type ComposerSurface = "chat" | "build";

export interface SlashCommand {
  /** Typed after the slash, e.g. `model` for `/model`. */
  readonly name: string;
  /** One line, in the owner's language, describing what running it does. */
  readonly summary: string;
  /**
   * What the surface should do. Handled by the view, because these are the
   * view's own controls — this module decides *which* commands exist, never
   * what a control means.
   */
  readonly action:
    | "new"
    | "model"
    | "attach"
    | "context"
    | "approvals"
    | "export"
    | "stop"
    | "plan"
    | "mode-plan"
    | "mode-edit"
    | "mode-auto"
    | "terminal"
    | "repos"
    | "shortcuts";
}

/**
 * Commands common to both composers, then the surface's own.
 *
 * Chat's set is the assistant's: start again, change model, attach, export.
 * Build's adds the coding agent's controls — the three modes it really enforces
 * (`buildModes.ts` sets them server-side), the governed terminal, and the
 * repository list.
 */
const SHARED: readonly SlashCommand[] = [
  { name: "new", summary: "Start a new conversation", action: "new" },
  { name: "model", summary: "Choose the model for this surface", action: "model" },
  { name: "attach", summary: "Attach a file or a workspace path", action: "attach" },
  { name: "context", summary: "Show what is in the context window", action: "context" },
  { name: "approvals", summary: "Open the approvals inbox", action: "approvals" },
  { name: "plan", summary: "Show the agent's current plan", action: "plan" },
  { name: "stop", summary: "Stop the running turn at its next safe boundary", action: "stop" },
  { name: "shortcuts", summary: "Show the keyboard shortcuts", action: "shortcuts" },
];

const CHAT_ONLY: readonly SlashCommand[] = [
  { name: "export", summary: "Export this conversation as HTML, Markdown or PDF", action: "export" },
];

const BUILD_ONLY: readonly SlashCommand[] = [
  { name: "plan-mode", summary: "Plan only — propose, change nothing", action: "mode-plan" },
  { name: "edit-mode", summary: "Edit — every change asks first", action: "mode-edit" },
  { name: "auto-mode", summary: "Auto — act within your standing permissions", action: "mode-auto" },
  { name: "terminal", summary: "Open the governed terminal", action: "terminal" },
  { name: "repos", summary: "Choose the repository to work in", action: "repos" },
];

export function slashCommands(surface: ComposerSurface): readonly SlashCommand[] {
  const own = surface === "build" ? BUILD_ONLY : CHAT_ONLY;
  return [...SHARED, ...own].sort((a, b) => a.name.localeCompare(b.name));
}

/**
 * The slash token being typed, or null.
 *
 * A slash only opens the menu at the very start of the prompt, which is the
 * behaviour every terminal agent has and the reason `n/a` or a URL in the middle
 * of a sentence does not pop a menu over what is being written.
 */
export function slashFragment(text: string, caret: number): string | null {
  if (!text.startsWith("/")) return null;
  const upToCaret = text.slice(0, caret);
  if (upToCaret.includes("\n") || upToCaret.includes(" ")) return null;
  return upToCaret.slice(1);
}

export function matchCommands(
  surface: ComposerSurface,
  fragment: string,
): readonly SlashCommand[] {
  const needle = fragment.trim().toLowerCase();
  const all = slashCommands(surface);
  if (needle === "") return all;
  return all.filter((command) => command.name.toLowerCase().startsWith(needle));
}

/**
 * Remove the `/command` token once it has been run.
 *
 * The command *is* the action; it is never sent to the model. Anything typed
 * after it is kept, so `/new draft the release notes` runs the command and
 * leaves the sentence in the box rather than discarding what was written.
 */
export function stripSlashToken(text: string): string {
  return text.replace(/^\/\S*/, "").trimStart();
}

export interface MentionToken {
  /** Index of the `@` in the text. */
  readonly start: number;
  /** Index just past the caret — where the replacement ends. */
  readonly end: number;
  /** What has been typed after the `@`, which is the search fragment. */
  readonly fragment: string;
}

/**
 * The `@`-mention being typed at the caret, or null.
 *
 * The `@` has to open a word — preceded by start-of-text or whitespace — so an
 * email address in a sentence is not read as a file reference. A space closes
 * the token, because a path with a space in it cannot be completed this way and
 * pretending otherwise would insert the wrong thing.
 */
export function mentionAt(text: string, caret: number): MentionToken | null {
  const upToCaret = text.slice(0, caret);
  const at = upToCaret.lastIndexOf("@");
  if (at === -1) return null;
  const before = at === 0 ? "" : upToCaret[at - 1];
  if (before !== "" && !/\s/.test(before)) return null;
  const fragment = upToCaret.slice(at + 1);
  if (/[\s]/.test(fragment)) return null;
  return { start: at, end: caret, fragment };
}

/** Put the chosen path where the `@`-token was, and leave a trailing space. */
export function applyMention(
  text: string,
  token: MentionToken,
  path: string,
): { text: string; caret: number } {
  const head = `${text.slice(0, token.start)}@${path} `;
  return { text: head + text.slice(token.end), caret: head.length };
}

/**
 * Grow a prompt box with what is being written, up to a ceiling.
 *
 * A two-row box that never grows means a long prompt is composed through a
 * letterbox. A box that grows without limit pushes the transcript off the
 * screen, so it stops at `maxPx` and scrolls from there.
 */
export function autoGrow(element: HTMLTextAreaElement | null, maxPx = 320): void {
  if (element === null) return;
  element.style.height = "auto";
  const wanted = element.scrollHeight;
  element.style.height = `${Math.min(wanted, maxPx)}px`;
  element.style.overflowY = wanted > maxPx ? "auto" : "hidden";
}

export interface Shortcut {
  readonly keys: string;
  readonly what: string;
}

/**
 * The keyboard map, per surface. Every row is a binding that really exists —
 * this is documentation of the code, not a wish list.
 */
export function shortcuts(surface: ComposerSurface): readonly Shortcut[] {
  const shared: Shortcut[] = [
    { keys: "Enter", what: "Send" },
    { keys: "Shift + Enter", what: "New line" },
    { keys: "/", what: "Slash commands, at the start of the prompt" },
    { keys: "@", what: "Mention a file from the code map" },
    { keys: "↑ / ↓", what: "Move through an open menu" },
    { keys: "Esc", what: "Close an open menu" },
  ];
  if (surface === "build") {
    shared.push({ keys: "Shift + Tab", what: "Cycle Plan → Edit → Auto" });
  }
  return shared;
}
