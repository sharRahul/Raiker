// One explorer over both project root kinds.
//
// The two things worth defending here are laziness and honesty. A folder the
// owner attached can be a whole repository, so a tree that walked itself on
// open would stall the page on a folder they only wanted to glance at. And an
// index state is shown only where one exists — a file Raiker cannot read has
// none, and a blank badge would read as a failure rather than as "not a
// document".
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { setToken } from "../api";
import type { ProjectBrowseEntry, ProjectBrowseView } from "../apiTypes";
import { stubFetch } from "../test-helpers";
import ProjectExplorer from "./ProjectExplorer.svelte";

afterEach(() => {
  setToken(null);
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function file(name: string, partial: Partial<ProjectBrowseEntry> = {}): ProjectBrowseEntry {
  return {
    name,
    relative_path: name,
    is_directory: false,
    size_bytes: 1024,
    media_type: "text/markdown",
    index_state: null,
    ...partial,
  };
}

function dir(name: string, partial: Partial<ProjectBrowseEntry> = {}): ProjectBrowseEntry {
  return {
    name,
    relative_path: name,
    is_directory: true,
    size_bytes: 0,
    media_type: "",
    index_state: null,
    ...partial,
  };
}

function browse(
  entries: ProjectBrowseEntry[],
  partial: Partial<ProjectBrowseView> = {},
): ProjectBrowseView {
  return {
    path: "",
    parent: null,
    entries,
    truncated: false,
    root_kind: "attached",
    root_label: "repo",
    root_missing: false,
    ...partial,
  };
}

const STATUS = {
  ok: true,
  project_id: "proj_1",
  root_kind: "attached",
  root_label: "repo",
  root_path: "C:/repo",
  root_missing: false,
  writable: true,
  watching: true,
  watch_reason: "watching",
  last_scanned_at: "2026-08-25T10:00:00Z",
  indexed_files: 3,
};

function attached(overrides: Record<string, unknown> = {}) {
  return {
    "GET /api/projects/proj_1/browse": browse([]),
    "GET /api/projects/proj_1/root/status": STATUS,
    ...overrides,
  };
}

function props(rootKind: "attached" | "managed" = "attached") {
  return { projectId: "proj_1", rootKind, rootLabel: rootKind === "attached" ? "repo" : "alpha" };
}

describe("ProjectExplorer", () => {
  it("expands a directory lazily rather than walking the whole tree", async () => {
    const mock = stubFetch(
      attached({
        "GET /api/projects/proj_1/browse": browse([dir("src"), file("README.md")]),
        "GET /api/projects/proj_1/browse?path=src": browse([file("main.py")], { path: "src" }),
      }),
    );
    render(ProjectExplorer, { props: props() });

    await fireEvent.click(await screen.findByRole("button", { name: "Expand src" }));

    expect(await screen.findByText("main.py")).toBeVisible();
    expect(
      mock.mock.calls.filter(([u]) => String(u).includes("/browse")).length,
    ).toBe(2);
  });

  it("does not re-fetch a directory it has already read", async () => {
    const mock = stubFetch(
      attached({
        "GET /api/projects/proj_1/browse": browse([dir("src")]),
        "GET /api/projects/proj_1/browse?path=src": browse([file("main.py")], { path: "src" }),
      }),
    );
    render(ProjectExplorer, { props: props() });

    const toggle = await screen.findByRole("button", { name: "Expand src" });
    await fireEvent.click(toggle);
    await screen.findByText("main.py");
    await fireEvent.click(await screen.findByRole("button", { name: "Collapse src" }));
    await fireEvent.click(await screen.findByRole("button", { name: "Expand src" }));

    await waitFor(() => expect(screen.getByText("main.py")).toBeVisible());
    expect(
      mock.mock.calls.filter(([u]) => String(u).includes("/browse")).length,
    ).toBe(2);
  });

  it("shows index state on a file that has one and nothing on a file that does not", async () => {
    stubFetch(
      attached({
        "GET /api/projects/proj_1/browse": browse([
          file("README.md", { index_state: "ready" }),
          file("logo.bin", { index_state: null, media_type: "" }),
        ]),
      }),
    );
    render(ProjectExplorer, { props: props() });

    expect(await screen.findByText("Ready")).toBeVisible();
    expect(screen.queryByText("Queued")).not.toBeInTheDocument();
    expect(screen.getAllByRole("treeitem").length).toBe(2);
  });

  it("hides import controls for an attached root", async () => {
    // The folder is the owner's and is read where it lives. Offering to "add
    // files" would imply Raiker copies them somewhere, which it does not.
    stubFetch(attached());
    render(ProjectExplorer, { props: props() });

    await screen.findByRole("tree", { name: /project files/i });
    expect(screen.queryByRole("button", { name: "Add files" })).not.toBeInTheDocument();
  });

  it("offers import controls for a managed root", async () => {
    stubFetch({
      "GET /api/projects/proj_1/browse": browse([], { root_kind: "managed", root_label: "alpha" }),
      "GET /api/projects/proj_1/root/status": { ...STATUS, root_kind: "managed" },
      "GET /api/projects/proj_1/managed-files": {
        ok: true,
        scope_kind: "project",
        project_id: "proj_1",
        files: [],
      },
    });
    render(ProjectExplorer, { props: props("managed") });

    expect(await screen.findByRole("button", { name: /Add files/ })).toBeVisible();
  });

  it("says the root is gone rather than rendering an empty tree", async () => {
    stubFetch(
      attached({
        "GET /api/projects/proj_1/browse": browse([], { root_missing: true }),
        "GET /api/projects/proj_1/root/status": { ...STATUS, root_missing: true },
      }),
    );
    render(ProjectExplorer, { props: props() });

    expect(await screen.findByText(/folder is no longer available/i)).toBeVisible();
  });

  it("states when watching failed instead of implying the index is fresh", async () => {
    stubFetch(
      attached({
        "GET /api/projects/proj_1/root/status": {
          ...STATUS,
          watching: false,
          watch_reason: "watch_failed:OSError",
        },
      }),
    );
    render(ProjectExplorer, { props: props() });

    expect(await screen.findByText(/not watching for changes/i)).toBeVisible();
  });

  it("indexes the folder on request and reloads what it finds", async () => {
    const mock = stubFetch(
      attached({
        "GET /api/projects/proj_1/browse": browse([file("README.md")]),
        "POST /api/projects/proj_1/root/index": {
          ok: true,
          project_id: "proj_1",
          indexed: 2,
          updated: 0,
          retired: 0,
          skipped: 1,
          truncated: false,
          scanned_at: "2026-08-25T11:00:00Z",
        },
      }),
    );
    render(ProjectExplorer, { props: props() });

    await fireEvent.click(await screen.findByRole("button", { name: /Index this folder/i }));

    await waitFor(() =>
      expect(
        mock.mock.calls.some(
          ([u, i]) =>
            String(u).endsWith("/root/index") &&
            (i as RequestInit | undefined)?.method === "POST",
        ),
      ).toBe(true),
    );
    expect(await screen.findByText(/2 newly indexed/i)).toBeVisible();
  });

  it("reports selection to its parent rather than owning the inspect pane", async () => {
    stubFetch(attached({ "GET /api/projects/proj_1/browse": browse([file("README.md")]) }));
    const onselect = vi.fn();
    render(ProjectExplorer, { props: { ...props(), onselect } });

    await fireEvent.click(await screen.findByRole("button", { name: "Inspect README.md" }));

    expect(onselect).toHaveBeenCalledWith(
      expect.objectContaining({ name: "README.md", relative_path: "README.md" }),
    );
  });

  it("says the listing stopped at its limit rather than showing a short tree as complete", async () => {
    stubFetch(
      attached({
        "GET /api/projects/proj_1/browse": browse([file("a.md")], { truncated: true }),
      }),
    );
    render(ProjectExplorer, { props: props() });

    expect(await screen.findByText(/stopped at its size limit/i)).toBeVisible();
  });

  it("degrades politely when the folder cannot be read", async () => {
    stubFetch({ "GET /api/projects/proj_1/root/status": STATUS });
    render(ProjectExplorer, { props: props() });

    expect(await screen.findByText(/could not be read/i)).toBeVisible();
  });
});
