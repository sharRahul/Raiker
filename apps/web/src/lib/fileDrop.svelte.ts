/**
 * One drop target, used by every surface that already accepts an upload
 * (BUG-252).
 *
 * Dropping a file onto the document library worked; dropping the same file onto
 * the Chat composer, the Build composer, the task composer or a project's file
 * list did nothing at all — not refused, not explained, just ignored. A product
 * where the gesture works in one place and silently fails in four teaches the
 * owner not to try it anywhere.
 *
 * The fix is not five drop handlers. It is this one, because the parts that are
 * easy to get wrong are the parts worth writing once:
 *
 * * **`preventDefault` on `dragover` is what makes a drop possible at all.**
 *   Without it the browser navigates to the dropped file and the page is gone.
 * * **`dragleave` fires when the pointer crosses onto a *child*.** A naive
 *   `dragover → true` / `dragleave → false` pair therefore flickers the whole
 *   time a file is moved across the target's own contents. Enter and leave are
 *   counted instead, so the highlight reflects the target and not its children.
 * * **A drag that carries no file is not a file drop.** Dragging selected text,
 *   or a card the page itself is reordering, must fall through to whatever else
 *   is listening rather than being swallowed by an import.
 *
 * Nothing here decides anything. Every dropped file goes through the same
 * validation the buttons use — allowlist, size cap, magic-byte sniff, and the
 * server's own re-validation. This only removes the requirement to find a
 * button.
 */

/** A drag carries files when any item it advertises is a file. */
export function carriesFiles(transfer: DataTransfer | null | undefined): boolean {
  if (!transfer) return false;
  const types = transfer.types;
  if (types && Array.from(types).includes("Files")) return true;
  // Safari has historically populated `items` before `types`; checking both
  // costs nothing and the alternative is a target that ignores a real drop.
  return Array.from(transfer.items ?? []).some((item) => item.kind === "file");
}

export interface FileDropOptions {
  /** Called with the dropped files. Never called with an empty list. */
  onFiles: (files: FileList) => void;
  /** When this returns false the target neither highlights nor accepts. */
  enabled?: () => boolean;
}

export interface FileDrop {
  /** True while a file drag is over this target. Drives the highlight. */
  readonly over: boolean;
  readonly ondragenter: (event: DragEvent) => void;
  readonly ondragover: (event: DragEvent) => void;
  readonly ondragleave: (event: DragEvent) => void;
  readonly ondrop: (event: DragEvent) => void;
}

export function createFileDrop(options: FileDropOptions): FileDrop {
  let depth = $state(0);
  const allowed = () => (options.enabled === undefined ? true : options.enabled());

  function reset() {
    depth = 0;
  }

  return {
    get over() {
      return depth > 0 && allowed();
    },
    ondragenter(event: DragEvent) {
      if (!carriesFiles(event.dataTransfer)) return;
      event.preventDefault();
      depth += 1;
    },
    ondragover(event: DragEvent) {
      if (!carriesFiles(event.dataTransfer)) return;
      // Required for a drop to fire at all, and the place to say whether the
      // gesture is a copy — the cursor is the only feedback before the drop.
      event.preventDefault();
      if (event.dataTransfer) {
        event.dataTransfer.dropEffect = allowed() ? "copy" : "none";
      }
      // A drag that entered before the listener was attached still gets a
      // highlight, rather than a target that only lights up on the second try.
      if (depth === 0) depth = 1;
    },
    ondragleave(event: DragEvent) {
      if (!carriesFiles(event.dataTransfer)) return;
      depth = Math.max(0, depth - 1);
    },
    ondrop(event: DragEvent) {
      if (!carriesFiles(event.dataTransfer)) return;
      event.preventDefault();
      reset();
      if (!allowed()) return;
      const files = event.dataTransfer?.files;
      if (files && files.length > 0) options.onFiles(files);
    },
  };
}
