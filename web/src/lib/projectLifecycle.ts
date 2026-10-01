/**
 * Projects §3.12 — the pure half of a project's lifecycle on the Projects page.
 *
 * Which folders a project may move into (UX-PROJ-06), what a delete removes in
 * words (UX-PROJ-07), and how a size reads. Kept out of the view so each rule is
 * tested on its own rather than through a rendered page.
 */
import type { ProjectDeletionPreview, ProjectView } from "./apiTypes";

/** A destination the move dialog offers, in tree order. */
export interface ProjectDestination {
  project: ProjectView;
  /** How many folders deep, for indentation. 0 is the top level. */
  depth: number;
  /** Why it cannot be chosen, or null when it can. */
  blocked: string | null;
}

/**
 * Every live project as a place `moving` could go, drawn as the hierarchy.
 *
 * The materialised `path` (`/root/child/`) gives both the order and the depth.
 * Ordering by the *names* along the path rather than the ids keeps siblings
 * alphabetical. Archived projects are left out: they are not somewhere work can
 * be filed, and the server refuses them. The project itself and its descendants
 * stay in, disabled, with the reason — a destination that vanishes reads as a
 * missing folder.
 */
export function projectDestinations(
  moving: ProjectView,
  projects: ProjectView[],
): ProjectDestination[] {
  const live = projects.filter((p) => !p.is_archived);
  const names = new Map(live.map((p) => [p.project_id, p.name.toLocaleLowerCase()]));
  const sortKey = (p: ProjectView) =>
    segments(p.path)
      .map((id) => names.get(id) ?? id)
      .join("\u0000");
  return live
    .slice()
    .sort((a, b) => sortKey(a).localeCompare(sortKey(b)))
    .map((project) => ({
      project,
      depth: Math.max(segments(project.path).length - 1, 0),
      blocked:
        project.project_id === moving.project_id
          ? "this project"
          : project.path.startsWith(moving.path)
            ? "inside this project"
            : null,
    }));
}

function segments(path: string): string[] {
  return path.split("/").filter((part) => part !== "");
}

/** "2.0 KB" — the size a person reads, from a byte count. */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function count(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}

/**
 * What a delete removes and what it keeps, as sentences.
 *
 * `removes` is the list the owner is agreeing to; `keeps` is what survives,
 * stated just as plainly, because an attached folder that survives and a child
 * project that is kept are as much a part of the decision as what goes.
 */
export function describeDeletion(preview: ProjectDeletionPreview): {
  removes: string[];
  keeps: string[];
} {
  const removes: string[] = [];
  const keeps: string[] = [];
  const exchanges = preview.turns > 0 ? ` (${count(preview.turns, "exchange", "exchanges")})` : "";
  removes.push(`${count(preview.sessions, "chat", "chats")}${exchanges}`);
  if (preview.tasks > 0) removes.push(count(preview.tasks, "task", "tasks"));
  if (preview.checkpoints > 0) removes.push(count(preview.checkpoints, "checkpoint", "checkpoints"));
  if (preview.managed_files > 0) {
    removes.push(`${count(preview.managed_files, "indexed file record", "indexed file records")}`);
  }
  if (preview.root_kind === "managed") {
    if (preview.folder_files === 0) {
      removes.push(`The folder ${preview.root_label} from this computer — it is empty`);
    } else {
      const files = `${preview.folder_truncated ? "at least " : ""}${count(preview.folder_files, "file", "files")}`;
      removes.push(
        `The folder ${preview.root_label} from this computer — ${files}, ${formatBytes(preview.folder_bytes)}`,
      );
    }
  } else {
    keeps.push(`The folder ${preview.root_label}. It is yours; Raiker does not touch it.`);
  }
  if (preview.descendants > 0) {
    keeps.push(
      `${count(preview.descendants, "project", "projects")} inside it — archived and moved to the top level, where they can be restored.`,
    );
  }
  return { removes, keeps };
}

/**
 * UX-PROJ-05 — the projects a picker offers: every live one.
 *
 * An archived project receives no new work, so it is not offered as a place to
 * start some. The one already chosen stays in the list even if it has since been
 * archived, so a select never silently shows a different value than it holds.
 */
export function pickableProjects(
  list: { projects: ProjectView[] } | null | undefined,
  chosen: string | null = null,
): ProjectView[] {
  return (list?.projects ?? []).filter(
    (project) => !project.is_archived || project.project_id === chosen,
  );
}

/** "PDF" — what kind of file, as a person names it: the extension, else the media type. */
export function fileKind(filename: string, mediaType: string): string {
  const dot = filename.lastIndexOf(".");
  if (dot > 0 && dot < filename.length - 1) return filename.slice(dot + 1).toUpperCase();
  return mediaType.split("/").pop()?.split(/[.+]/).pop()?.toUpperCase() || "File";
}
