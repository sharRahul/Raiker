/**
 * VIS2-12 — what Build's third pane can show, declared once.
 *
 * The tabs live here rather than inside the pane for the same reason the
 * composer's capabilities do: two places have to agree about them. The pane
 * draws them, and `BuildView` *chooses* between them — it is the only thing
 * that knows a command just started or a turn just finished, so it owns the
 * auto-focus decision. A list written in the component and a set of string
 * literals written in the view is one rename away from a tab nothing can
 * select.
 */

/** The four views of one workspace. */
export const ARTIFACT_TABS = [
  { id: "changes", label: "Changes" },
  { id: "preview", label: "Preview" },
  { id: "terminal", label: "Terminal" },
  { id: "runs", label: "Runs" },
] as const;

export type ArtifactTab = (typeof ARTIFACT_TABS)[number]["id"];

/** What just happened, in the words the view already uses for it. */
export type ArtifactEvent =
  | "file-opened"
  | "command-started"
  | "turn-changed-files"
  | "background-work";

/**
 * Which tab an event should bring forward, or null to leave the owner where
 * they are.
 *
 * Auto-focus is a *courtesy*, and the failure mode is a pane that yanks itself
 * away from what somebody is reading. So the rule is narrow: an event selects
 * its tab only when the owner has not already chosen a different one *for this
 * event*. A turn finishing while the owner reads the terminal output that turn
 * produced must not pull them to Changes — they are looking at the thing the
 * event is about.
 */
export function focusFor(event: ArtifactEvent, current: ArtifactTab): ArtifactTab | null {
  switch (event) {
    case "file-opened":
      return "preview";
    case "command-started":
      return "terminal";
    case "background-work":
      return "runs";
    case "turn-changed-files":
      // The one conditional case, and the reason this is a function rather than
      // a lookup table: a turn that changed files is worth showing *unless* the
      // owner is already reading that turn's own output.
      return current === "terminal" ? null : "changes";
  }
}

/** A count of changed files, as the pane's lead line and tab badge read it. */
export function changesSummary(
  changes: { entries: { path: string }[] } | null,
): { count: number; text: string } {
  const count = changes?.entries.length ?? 0;
  if (count === 0) return { count: 0, text: "No uncommitted changes." };
  return {
    count,
    text: count === 1 ? "1 file changed and not committed." : `${count} files changed and not committed.`,
  };
}
