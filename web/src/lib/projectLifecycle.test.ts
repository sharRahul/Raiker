import { describe, expect, it } from "vitest";
import type { ProjectDeletionPreview, ProjectView } from "./apiTypes";
import {
  describeDeletion,
  fileKind,
  formatBytes,
  pickableProjects,
  projectDestinations,
} from "./projectLifecycle";

function project(partial: Partial<ProjectView>): ProjectView {
  return {
    project_id: "p",
    name: "P",
    root_subpath: "",
    created_at: "2026-07-12T00:00:00Z",
    session_count: 0,
    selected: false,
    parent_id: null,
    path: "/p/",
    is_archived: false,
    archived_at: null,
    root_kind: "managed",
    root_label: "p",
    ...partial,
  };
}

const ROOT = project({ project_id: "root", name: "Root", path: "/root/" });
const CHILD = project({ project_id: "child", name: "Child", path: "/root/child/", parent_id: "root" });
const GRAND = project({ project_id: "grand", name: "Grand", path: "/root/child/grand/", parent_id: "child" });
const ALPHA = project({ project_id: "alpha", name: "alpha", path: "/alpha/" });
const ARCHIVED = project({ project_id: "old", name: "Old", path: "/old/", is_archived: true });

describe("projectDestinations", () => {
  it("draws the tree in order, indented, without archived folders", () => {
    const rows = projectDestinations(CHILD, [GRAND, ROOT, ARCHIVED, ALPHA, CHILD]);
    expect(rows.map((r) => [r.project.project_id, r.depth])).toEqual([
      ["alpha", 0],
      ["root", 0],
      ["child", 1],
      ["grand", 2],
    ]);
  });

  it("blocks the project itself and everything inside it, and nothing else", () => {
    const rows = projectDestinations(CHILD, [ROOT, CHILD, GRAND, ALPHA]);
    const blocked = Object.fromEntries(rows.map((r) => [r.project.project_id, r.blocked]));
    expect(blocked).toEqual({
      root: null,
      child: "this project",
      grand: "inside this project",
      alpha: null,
    });
  });

  it("does not mistake a sibling whose id starts the same for a descendant", () => {
    const rooted = project({ project_id: "ro", name: "Ro", path: "/ro/" });
    const rows = projectDestinations(rooted, [rooted, ROOT]);
    expect(rows.find((r) => r.project.project_id === "root")?.blocked).toBeNull();
  });
});

describe("pickableProjects", () => {
  it("leaves archived projects out unless one is the current choice", () => {
    const list = { projects: [ROOT, ARCHIVED] };
    expect(pickableProjects(list).map((p) => p.project_id)).toEqual(["root"]);
    expect(pickableProjects(list, "old").map((p) => p.project_id)).toEqual(["root", "old"]);
    expect(pickableProjects(null)).toEqual([]);
  });
});

describe("describeDeletion", () => {
  const preview: ProjectDeletionPreview = {
    project_id: "root",
    name: "Root",
    root_kind: "managed",
    root_label: "root",
    sessions: 1,
    turns: 1,
    tasks: 0,
    checkpoints: 0,
    managed_files: 0,
    descendants: 0,
    folder_files: 20000,
    folder_bytes: 3 * 1024 * 1024,
    folder_truncated: true,
    requires_step_up: true,
  };

  it("says what goes, with singular nouns and an 'at least' when the count stopped", () => {
    const { removes, keeps } = describeDeletion(preview);
    expect(removes).toEqual([
      "1 chat (1 exchange)",
      "The folder root from this computer — at least 20000 files, 3.0 MB",
    ]);
    expect(keeps).toEqual([]);
  });

  it("says an empty managed folder is empty rather than counting nothing", () => {
    const { removes } = describeDeletion({ ...preview, folder_files: 0, folder_bytes: 0, folder_truncated: false });
    expect(removes[1]).toBe("The folder root from this computer — it is empty");
  });

  it("keeps an attached folder and says so", () => {
    const { removes, keeps } = describeDeletion({
      ...preview,
      root_kind: "attached",
      root_label: "/home/me/repo",
      sessions: 0,
      turns: 0,
      descendants: 2,
    });
    expect(removes).toEqual(["0 chats"]);
    expect(keeps[0]).toMatch(/The folder \/home\/me\/repo\. It is yours/);
    expect(keeps[1]).toMatch(/^2 projects inside it/);
  });
});

describe("formatBytes and fileKind", () => {
  it("reads sizes and kinds the way a person does", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(5 * 1024 ** 3)).toBe("5.0 GB");
    expect(fileKind("brief.pdf", "application/pdf")).toBe("PDF");
    expect(fileKind("README", "text/markdown")).toBe("MARKDOWN");
    expect(fileKind("", "")).toBe("File");
  });
});
