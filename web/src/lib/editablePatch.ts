/**
 * BUG-271 / QUI-F20 — the text a reviewer edits when they write their own
 * version of a proposed change.
 *
 * Only a patch can be corrected as text, and the server accepts a replacement
 * only for `apply_patch` (`_PATCH_TOOLS` in `routes_approvals.py`). Its preview
 * is drawn as a file diff, so the preview kind cannot say whether an edit is
 * possible: the tool and the proposal's own `patch` argument can. The edit
 * starts from that patch, not from the drawn diff, so the targets the server
 * checks are the ones it was proposed with.
 */
export function editablePatch(toolName: string, args: Record<string, unknown> | null | undefined): string | null {
  if (toolName !== "apply_patch") return null;
  const patch = args?.patch;
  return typeof patch === "string" && patch.trim() !== "" ? patch : null;
}
