// The document library is the one place an owner can hand Raiker a file to
// keep. What has to hold: every file type is offered (no MIME filter decides in
// the browser what the server will accept), a folder import preserves its
// hierarchy, each file's index state is stated honestly rather than implied,
// and one failed file in a batch is reported as that file's failure — not as
// the whole import having failed.
import { render, screen, waitFor } from "@testing-library/svelte";
import { fireEvent } from "@testing-library/dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ManagedFile } from "../apiTypes";
import { stubFetch } from "../test-helpers";
import FileLibrary from "./FileLibrary.svelte";

afterEach(() => vi.unstubAllGlobals());

function file(overrides: Partial<ManagedFile> = {}): ManagedFile {
  return {
    file_id: "mfile_1",
    scope_kind: "memory",
    project_id: null,
    relative_path: "notes/handbook.md",
    media_type: "text/markdown",
    size_bytes: 2048,
    content_hash: "abc",
    index_state: "ready",
    index_error: null,
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-01T00:00:00Z",
    ...overrides,
  };
}

function memoryRoutes(files: ManagedFile[] = [file()]) {
  return {
    "GET /api/memory/files": { ok: true, scope_kind: "memory", project_id: null, files },
  };
}

function fileInput(): HTMLInputElement {
  const inputs = document.querySelectorAll<HTMLInputElement>('input[type="file"]');
  return inputs[0];
}

function folderInput(): HTMLInputElement {
  const inputs = document.querySelectorAll<HTMLInputElement>('input[type="file"]');
  return inputs[1];
}

/** A File whose `webkitRelativePath` is set, as a folder selection produces. */
function selected(name: string, relativePath?: string): File {
  const created = new File(["contents"], name, { type: "text/markdown" });
  if (relativePath !== undefined) {
    Object.defineProperty(created, "webkitRelativePath", { value: relativePath });
  }
  return created;
}

function fileListOf(files: File[]): FileList {
  return {
    length: files.length,
    item: (index: number) => files[index] ?? null,
    [Symbol.iterator]: function* () {
      yield* files;
    },
    ...Object.fromEntries(files.map((entry, index) => [index, entry])),
  } as unknown as FileList;
}

describe("FileLibrary", () => {
  it("offers both file and folder import as one grouped control", async () => {
    stubFetch(memoryRoutes());
    render(FileLibrary, { props: { scope: "memory" } });

    expect(await screen.findByRole("button", { name: "Add files" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Add folder" })).toBeVisible();
    expect(screen.getByRole("group", { name: "Add to library" })).toBeInTheDocument();
  });

  it("filters no file type in the browser", async () => {
    stubFetch(memoryRoutes());
    render(FileLibrary, { props: { scope: "memory" } });

    await screen.findByRole("button", { name: "Add files" });
    // Acceptance is the server's decision. An `accept` attribute here would
    // hide types Raiker stores perfectly well.
    expect(fileInput().hasAttribute("accept")).toBe(false);
    expect(fileInput().multiple).toBe(true);
    expect(folderInput().hasAttribute("webkitdirectory")).toBe(true);
  });

  it("states each file's index state and its managed path", async () => {
    stubFetch(
      memoryRoutes([
        file(),
        file({
          file_id: "mfile_2",
          relative_path: "archive/data.custom",
          media_type: "application/x-custom",
          index_state: "metadata_only",
          index_error: "no_local_extractor",
        }),
      ]),
    );
    render(FileLibrary, { props: { scope: "memory" } });

    expect(await screen.findByText("notes/handbook.md")).toBeVisible();
    expect(screen.getByText("Ready")).toBeVisible();
    expect(screen.getByText("archive/data.custom")).toBeVisible();
    expect(screen.getByText("Metadata only")).toBeVisible();
    expect(screen.getByText("No safe local reader for this format")).toBeVisible();
  });

  it("sends each selected file's relative path so a folder keeps its shape", async () => {
    const fetchMock = stubFetch({
      ...memoryRoutes([]),
      "POST /api/memory/files": {
        ok: true,
        scope_kind: "memory",
        project_id: null,
        results: [{ ok: true, ...file() }],
      },
    });
    render(FileLibrary, { props: { scope: "memory" } });
    await screen.findByRole("button", { name: "Add folder" });

    const input = folderInput();
    Object.defineProperty(input, "files", {
      value: fileListOf([
        selected("intro.md", "book/ch1/intro.md"),
        selected("body.md", "book/ch2/body.md"),
      ]),
      configurable: true,
    });
    await fireEvent.change(input);

    await waitFor(() => {
      const post = fetchMock.mock.calls.find(
        ([, init]) => (init as RequestInit | undefined)?.method === "POST",
      );
      expect(post).toBeDefined();
      const body = JSON.parse(String((post?.[1] as RequestInit).body));
      expect(body.files.map((entry: { relative_path: string }) => entry.relative_path)).toEqual([
        "book/ch1/intro.md",
        "book/ch2/body.md",
      ]);
    });
  });

  it("announces a partial import instead of failing the whole batch", async () => {
    stubFetch({
      ...memoryRoutes([file()]),
      "POST /api/memory/files": {
        ok: false,
        scope_kind: "memory",
        project_id: null,
        results: [
          { ok: true, ...file() },
          { ok: false, relative_path: "../escape.md", reason_code: "managed_file_path_outside_scope" },
        ],
      },
    });
    render(FileLibrary, { props: { scope: "memory" } });
    await screen.findByRole("button", { name: "Add files" });

    const input = fileInput();
    Object.defineProperty(input, "files", {
      value: fileListOf([selected("handbook.md"), selected("escape.md")]),
      configurable: true,
    });
    await fireEvent.change(input);

    const status = await screen.findByRole("status");
    await waitFor(() => expect(status).toHaveTextContent("1 of 2 files stored."));
    expect(screen.getByText("managed_file_path_outside_scope")).toBeVisible();
  });

  it("offers retry only for a file that is not indexed, and delete for every file", async () => {
    stubFetch(
      memoryRoutes([
        file(),
        file({ file_id: "mfile_2", relative_path: "broken.pdf", index_state: "failed", index_error: "extraction_failed" }),
      ]),
    );
    render(FileLibrary, { props: { scope: "memory" } });

    await screen.findByText("broken.pdf");
    expect(screen.getByRole("button", { name: "Retry indexing broken.pdf" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Retry indexing notes/handbook.md" })).toBeNull();
    // Delete keeps its own accessible name per row, and stays outside the
    // segmented group: removing a file is not one of a set of equivalent adds.
    expect(screen.getByRole("button", { name: "Remove notes/handbook.md" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Remove broken.pdf" })).toBeVisible();
  });

  it("reads a project's own library from that project's endpoint", async () => {
    const fetchMock = stubFetch({
      "GET /api/projects/proj_1/managed-files": {
        ok: true,
        scope_kind: "project",
        project_id: "proj_1",
        files: [file({ scope_kind: "project", project_id: "proj_1", relative_path: "spec.md" })],
      },
    });
    render(FileLibrary, { props: { scope: "project", projectId: "proj_1" } });

    expect(await screen.findByText("spec.md")).toBeVisible();
    expect(
      fetchMock.mock.calls.some(([url]) =>
        String(url).includes("/api/projects/proj_1/managed-files"),
      ),
    ).toBe(true);
  });

  it("asks for a project before offering to import into one", async () => {
    stubFetch({});
    render(FileLibrary, { props: { scope: "project", projectId: null } });

    expect(await screen.findByText(/select a project to manage its files/i)).toBeVisible();
    expect(screen.getByRole("button", { name: "Add files" })).toBeDisabled();
  });
});
