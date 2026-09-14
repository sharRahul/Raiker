// Coverage for the Projects view (web-app task 5): list + create + set-active.
// A project is an organizing scope only; the view never grants anything —
// creation POSTs a name (the root subpath is derived server-side) and
// activation PUTs the selection.
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { setToken } from "../api";
import type { ProjectView } from "../apiTypes";
import { stubFetch, stubFetchPending } from "../test-helpers";
import ProjectsView from "./ProjectsView.svelte";
import { resetWorkProject, workProject } from "../workProject.svelte";

afterEach(() => {
  setToken(null);
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function project(partial: Partial<ProjectView>): ProjectView {
  return {
    project_id: "proj_1",
    name: "Alpha",
    root_subpath: "projects/alpha",
    created_at: "2026-07-12T00:00:00Z",
    session_count: 0,
    selected: false,
    parent_id: null,
    path: "/",
    is_archived: false,
    archived_at: null,
    root_kind: "managed",
    root_label: "alpha",
    ...partial,
  };
}

describe("ProjectsView", () => {
  it("shows a route-level loading state while projects are fetched", async () => {
    stubFetchPending();
    render(ProjectsView);
    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent(/loading projects/i);
  });

  it("shows a route-level error state when projects cannot load", async () => {
    stubFetch({});
    render(ProjectsView);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/couldn't load projects/i);
    expect(alert).toHaveTextContent(/unavailable \(404\)/i);
  });

  it("lists projects with their scope and marks the active one", async () => {
    stubFetch({
      "GET /api/projects": {
        projects: [
          project({ project_id: "proj_1", name: "Alpha", selected: true, session_count: 2 }),
          project({ project_id: "proj_2", name: "Beta", root_subpath: "projects/beta" }),
        ],
        active_project_id: "proj_1",
      },
      "GET /api/projects/tree": [],
    });
    render(ProjectsView);
    await waitFor(() => expect(screen.getByText("Alpha")).toBeInTheDocument());
    expect(screen.getByText("Beta")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("projects/alpha")).toBeInTheDocument();
  });

  it("shows the empty state when no projects exist", async () => {
    stubFetch({ "GET /api/projects": { projects: [], active_project_id: null }, "GET /api/projects/tree": [] });
    render(ProjectsView);
    await waitFor(() => expect(screen.getByText("No projects yet")).toBeInTheDocument());
  });

  it("creates a project by POSTing only the name and notifies the shell", async () => {
    const mock = stubFetch({
      "GET /api/projects": { projects: [], active_project_id: null },
      "GET /api/projects/tree": [],
      "POST /api/projects": {
        ok: true,
        project_id: "proj_new",
        name: "Tejas Mk1A",
        root_subpath: "projects/tejas-mk1a",
      },
    });
    const onchanged = vi.fn();
    render(ProjectsView, { props: { onchanged } });
    await waitFor(() => expect(screen.getByText("No projects yet")).toBeInTheDocument());

    const input = screen.getByLabelText("New project name") as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "Tejas Mk1A" } });
    await fireEvent.click(screen.getByText("Create project"));

    await waitFor(() => {
      const post = mock.mock.calls.find(
        (c) => (c[1]?.method ?? "GET").toUpperCase() === "POST",
      );
      expect(post).toBeTruthy();
      expect(JSON.parse(post![1]!.body as string)).toEqual({ name: "Tejas Mk1A" });
    });
    await waitFor(() => expect(onchanged).toHaveBeenCalled());
  });

  it("offers Start in Build instead of an account-wide activation", async () => {
    // "Set active" wrote a preference no route reads any more. What the owner
    // wanted from it — work in this one — is now explicit and local to Build.
    const mock = stubFetch({
      "GET /api/projects": {
        projects: [project({ project_id: "proj_1", name: "Alpha" })],
        active_project_id: null,
      },
      "GET /api/projects/tree": [],
    });
    render(ProjectsView);

    await waitFor(() => expect(screen.getByText("Start in Build")).toBeInTheDocument());
    expect(screen.queryByText("Set active")).not.toBeInTheDocument();
    expect(screen.queryByText("Deactivate")).not.toBeInTheDocument();

    await fireEvent.click(screen.getByText("Start in Build"));

    expect(window.localStorage.getItem("raiker.build.project")).toBe("proj_1");
    expect(window.location.hash).toBe("#/build");
    expect(
      mock.mock.calls.some(([url]) => String(url).includes("/api/projects/selection")),
    ).toBe(false);
  });

  it("exports a loaded project's redacted JSONL via POST", async () => {
    vi.useFakeTimers();
    const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method ?? "GET").toUpperCase();
      if (method === "GET" && url === "/api/projects") {
        return { ok: true, status: 200, json: async () => ({ projects: [project({})], active_project_id: null }) } as Response;
      }
      if (method === "GET" && url === "/api/projects/tree") {
        return { ok: true, status: 200, json: async () => [] } as Response;
      }
      if (method === "GET" && url === "/api/projects/proj_1") {
        return {
          ok: true,
          status: 200,
          json: async () => ({ project: project({}), context: { instructions: "", attachment_ids: [], memory_enabled: false }, sessions: [], checkpoints: [] }),
        } as Response;
      }
      if (method === "POST" && url === "/api/projects/proj_1/export") {
        return { ok: true, status: 200, blob: async () => new Blob(["{}\n"], { type: "application/jsonl" }) } as Response;
      }
      return { ok: false, status: 404, json: async () => ({}) } as Response;
    });
    const click = vi.fn();
    const createObjectURL = vi.fn(() => "blob:export");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("fetch", mock);
    vi.stubGlobal("URL", { createObjectURL, revokeObjectURL });
    vi.spyOn(document, "createElement").mockImplementation(((tagName: string) => {
      const element = document.createElementNS("http://www.w3.org/1999/xhtml", tagName);
      if (tagName === "a") vi.spyOn(element, "click").mockImplementation(click);
      return element;
    }) as typeof document.createElement);
    setToken("export-token");

    render(ProjectsView);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /open project alpha/i })).toBeInTheDocument(),
    );
    await fireEvent.click(screen.getByRole("button", { name: /open project alpha/i }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Export project" })).toBeInTheDocument());
    await fireEvent.click(screen.getByRole("button", { name: "Export project" }));

    await waitFor(() => {
      expect(mock).toHaveBeenCalledWith(
        "/api/projects/proj_1/export",
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({ get: expect.any(Function) }),
        }),
      );
      expect(createObjectURL).toHaveBeenCalledOnce();
      expect(click).toHaveBeenCalledOnce();
    });
    const exportRequest = mock.mock.calls.find((call) => String(call[0]) === "/api/projects/proj_1/export");
    expect(new Headers(exportRequest![1]!.headers).get("Authorization")).toBe("Bearer export-token");
    expect(revokeObjectURL).not.toHaveBeenCalled();

    await vi.runAllTimersAsync();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:export");
  });

  it("renders an accessible error when project export is rejected", async () => {
    const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method ?? "GET").toUpperCase();
      if (method === "GET" && url === "/api/projects") {
        return { ok: true, status: 200, json: async () => ({ projects: [project({})], active_project_id: null }) } as Response;
      }
      if (method === "GET" && url === "/api/projects/tree") {
        return { ok: true, status: 200, json: async () => [] } as Response;
      }
      if (method === "GET" && url === "/api/projects/proj_1") {
        return {
          ok: true,
          status: 200,
          json: async () => ({ project: project({}), context: { instructions: "", attachment_ids: [], memory_enabled: false }, sessions: [], checkpoints: [] }),
        } as Response;
      }
      if (method === "POST" && url === "/api/projects/proj_1/export") {
        return { ok: false, status: 403, json: async () => ({ detail: { reason_code: "forbidden" } }) } as Response;
      }
      return { ok: false, status: 404, json: async () => ({}) } as Response;
    });
    vi.stubGlobal("fetch", mock);

    render(ProjectsView);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /open project alpha/i })).toBeInTheDocument(),
    );
    await fireEvent.click(screen.getByRole("button", { name: /open project alpha/i }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Export project" })).toBeInTheDocument());
    await fireEvent.click(screen.getByRole("button", { name: "Export project" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not export (403).");
  });

  it("surfaces an honest server rejection on create", async () => {
    const mock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(_input);
      const method = (init?.method ?? "GET").toUpperCase();
      if (method === "POST") {
        return {
          ok: false,
          status: 403,
          json: async () => ({ detail: { reason_code: "invalid_project_name" } }),
        } as Response;
      }
      return {
        ok: true,
        status: 200,
        json: async () =>
          url.includes("/api/projects/tree") ? [] : { projects: [], active_project_id: null },
      } as Response;
    });
    vi.stubGlobal("fetch", mock);

    render(ProjectsView);
    await waitFor(() => expect(screen.getByText("No projects yet")).toBeInTheDocument());
    const input = screen.getByLabelText("New project name") as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "///" } });
    await fireEvent.click(screen.getByText("Create project"));
    await waitFor(() => expect(screen.getByText(/invalid_project_name/)).toBeInTheDocument());
  });
});

// ── Project context home ──────────────────────────────────────────────────
// Opening a project shows one file list, not two. The managed document library
// and the walk of the project folder described the same files differently,
// which left the owner deciding which to believe; the explorer replaced both.
// Provenance survived that merge, because nothing else records who changed a
// file.
describe("ProjectsView context home", () => {
  const DETAIL = {
    project: project({}),
    context: { instructions: "", attachment_ids: [], memory_enabled: false, memory_mode: "inherit" },
    sessions: [],
    checkpoints: [],
  };

  const BROWSE = {
    path: "",
    parent: null,
    entries: [
      {
        name: "brief.md",
        relative_path: "brief.md",
        is_directory: false,
        size_bytes: 2048,
        media_type: "text/markdown",
        index_state: "ready",
      },
    ],
    truncated: false,
    root_kind: "managed",
    root_label: "alpha",
    root_missing: false,
  };

  const STATUS = {
    ok: true,
    project_id: "proj_1",
    root_kind: "managed",
    root_label: "alpha",
    root_path: null,
    root_missing: false,
    writable: true,
    watching: false,
    watch_reason: "not_started",
    last_scanned_at: "",
    indexed_files: 1,
  };

  const FILES = {
    project_id: "proj_1",
    root_subpath: "projects/alpha",
    root_exists: true,
    truncated: false,
    note: "Metadata only. Raiker never serves workspace file content to the browser.",
    files: [],
    provenance: {
      "projects/alpha/brief.md": [
        {
          turn_id: "turn_9",
          action_id: "act_9",
          session_id: "sess_alpha",
          capability: "filesystem_write",
          principal_id: "principal_owner",
          capture_status: "captured",
          existed_before: true,
          pre_image_size: 1024,
          created_at: "2026-07-24T00:00:00Z",
        },
      ],
    },
  };

  function routes(overrides: Record<string, unknown> = {}) {
    return {
      "GET /api/projects": { projects: [project({})], active_project_id: null },
      "GET /api/projects/tree": [],
      "GET /api/projects/proj_1": DETAIL,
      "GET /api/projects/proj_1/files": FILES,
      "GET /api/projects/proj_1/browse": BROWSE,
      "GET /api/projects/proj_1/root/status": STATUS,
      "GET /api/projects/proj_1/managed-files": {
        ok: true,
        scope_kind: "project",
        project_id: "proj_1",
        files: [],
      },
      "GET /api/tasks": [],
      ...overrides,
    };
  }

  async function openDetail(routeMap: Record<string, unknown>) {
    stubFetch(routeMap);
    render(ProjectsView);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /open project alpha/i })).toBeInTheDocument(),
    );
    await fireEvent.click(screen.getByRole("button", { name: /open project alpha/i }));
  }

  /*
   * BUG-282 — a picture generated in a project is that project's material.
   *
   * The filter is the row's own `project_id`. These two cases are the ones that
   * decide whether the section is honest: a picture made elsewhere must not
   * appear here, and a picture made before the column existed carries no
   * project and belongs to none of them.
   */
  function generation(partial: Record<string, unknown>) {
    return {
      generation_id: "img_1",
      profile_id: "openai-hosted",
      provider: "openai",
      model: "gpt-image-1",
      prompt: "a leaf",
      size: "1024x1024",
      status: "ok",
      reason_code: null,
      has_image: true,
      media_type: "image/png",
      byte_size: 100,
      created_at: "2026-09-12T10:00:00Z",
      kind: "create",
      source_generation_id: null,
      project_id: "proj_1",
      ...partial,
    };
  }

  it("shows the images generated while this project was the working one", async () => {
    await openDetail(
      routes({
        "GET /api/images": {
          sizes: ["1024x1024"],
          generations: [generation({ generation_id: "img_1", prompt: "a maple leaf" })],
        },
      }),
    );

    // NEW-PROJ-02 — the alt text names the action, because the picture is now
    // a link to itself rather than an illustration.
    const shot = await screen.findByRole("img", { name: "Open in Design: a maple leaf" });
    expect(shot).toHaveAttribute("src", "/api/images/img_1/bytes");
  });

  it("opens the image that was clicked, not the whole Design history (NEW-PROJ-02)", async () => {
    // The strip showed eight pictures and offered no way to open one: the only
    // continuation was a bare `#/design`, so finding the image you had just
    // been looking at meant searching the account's whole Design history.
    await openDetail(
      routes({
        "GET /api/images": {
          sizes: ["1024x1024"],
          generations: [generation({ generation_id: "img_1", prompt: "a maple leaf" })],
        },
      }),
    );

    const link = (await screen.findByRole("img", { name: /a maple leaf/ })).closest("a");
    expect(link).toHaveAttribute("href", "#/design?project=proj_1&asset=img_1");
    // And View all keeps the project rather than dropping the owner into every
    // image they have ever generated.
    expect(screen.getByRole("link", { name: "View all in Design" })).toHaveAttribute(
      "href",
      "#/design?project=proj_1",
    );
  });

  it("says how many images there are when the strip is truncated (NEW-PROJ-02)", async () => {
    await openDetail(
      routes({
        "GET /api/images": {
          sizes: ["1024x1024"],
          generations: Array.from({ length: 11 }, (_unused, index) =>
            generation({ generation_id: `img_${index}`, prompt: `picture ${index}` }),
          ),
        },
      }),
    );

    // Eight tiles that look like the whole set are a count nobody stated.
    expect(await screen.findByText("Showing 8 of 11.")).toBeInTheDocument();
  });

  it("keeps out a picture that belongs to another project or to none", async () => {
    await openDetail(
      routes({
        "GET /api/images": {
          sizes: ["1024x1024"],
          generations: [
            generation({ generation_id: "img_2", prompt: "elsewhere", project_id: "proj_2" }),
            generation({ generation_id: "img_3", prompt: "unfiled", project_id: null }),
            generation({
              generation_id: "img_4",
              prompt: "refused",
              status: "refused",
              has_image: false,
            }),
          ],
        },
      }),
    );

    expect(
      await screen.findByText(/pictures generated in design while this project is active/i),
    ).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: "elsewhere" })).not.toBeInTheDocument();
    expect(screen.queryByRole("img", { name: "unfiled" })).not.toBeInTheDocument();
    expect(screen.queryByRole("img", { name: "refused" })).not.toBeInTheDocument();
  });

  it("renders exactly one file list", async () => {
    await openDetail(routes());
    await screen.findByRole("tree", { name: /project files/i });
    expect(screen.getAllByRole("tree").length).toBe(1);
  });

  it("lists project files through the explorer", async () => {
    await openDetail(routes());
    expect(await screen.findByRole("button", { name: "Inspect brief.md" })).toBeInTheDocument();
    expect(screen.getByText("2.0 KB")).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
  });

  it("links a selected file's provenance back to the session and audit log", async () => {
    await openDetail(routes());
    await fireEvent.click(await screen.findByRole("button", { name: "Inspect brief.md" }));

    expect(await screen.findByText("Provenance")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /session sess_alpha/i })).toHaveAttribute(
      "href",
      "#/sessions?session=sess_alpha",
    );
    expect(screen.getByRole("link", { name: /turn_9 in the audit log/i })).toHaveAttribute(
      "href",
      "#/observe?tab=activity&session=sess_alpha",
    );
  });

  it("says a file has no recorded governed write rather than implying one", async () => {
    await openDetail(routes({ "GET /api/projects/proj_1/files": { ...FILES, provenance: {} } }));
    await fireEvent.click(await screen.findByRole("button", { name: "Inspect brief.md" }));
    expect(
      await screen.findByText(/no governed write is recorded against this path/i),
    ).toBeInTheDocument();
  });

  it("keeps the file list when provenance is unavailable", async () => {
    // Provenance is supplementary now. Losing it must cost one line, not the
    // tree — which is the whole reason the tree no longer reads from it.
    const withoutFiles = Object.fromEntries(
      Object.entries(routes()).filter(([key]) => key !== "GET /api/projects/proj_1/files"),
    );
    await openDetail(withoutFiles);
    expect(await screen.findByRole("button", { name: "Inspect brief.md" })).toBeInTheDocument();
    expect(await screen.findByText(/files unavailable \(404\)/i)).toBeInTheDocument();
  });

  it("offers attaching a folder to a managed project", async () => {
    await openDetail(routes());
    expect(await screen.findByRole("button", { name: "Attach a folder" })).toBeVisible();
  });

  it("does not offer attaching to a project that already has a folder", async () => {
    await openDetail(
      routes({
        "GET /api/projects/proj_1": {
          ...DETAIL,
          project: project({ root_kind: "attached", root_label: "repo" }),
        },
        "GET /api/projects/proj_1/browse": { ...BROWSE, root_kind: "attached", root_label: "repo" },
        "GET /api/projects/proj_1/root/status": { ...STATUS, root_kind: "attached" },
      }),
    );
    await screen.findByRole("tree", { name: /project files/i });
    expect(screen.queryByRole("button", { name: "Attach a folder" })).not.toBeInTheDocument();
  });
});

// ── Attaching a folder ────────────────────────────────────────────────────
// For anyone whose work already lives in a folder, attaching one *is* how they
// make a project. It sits beside creating one rather than inside a project they
// had to create first.
describe("ProjectsView folder attachment", () => {
  function listRoutes(overrides: Record<string, unknown> = {}) {
    return {
      "GET /api/projects": { projects: [project({})], active_project_id: null },
      "GET /api/projects/tree": [],
      ...overrides,
    };
  }

  it("offers attaching an existing folder beside creating one", async () => {
    stubFetch(listRoutes());
    render(ProjectsView);

    expect(await screen.findByRole("button", { name: "Create project" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Attach existing folder…" })).toBeVisible();
  });

  it("states that the folder is read where it lives and never copied", async () => {
    stubFetch(listRoutes());
    render(ProjectsView);

    await fireEvent.click(await screen.findByRole("button", { name: "Attach existing folder…" }));

    expect(await screen.findByText(/read where it lives on this machine/i)).toBeVisible();
    expect(screen.getByText(/will not delete the folder/i)).toBeVisible();
  });

  it("sends the folder path and the write decision together", async () => {
    const mock = stubFetch(
      listRoutes({
        "POST /api/projects": {
          ok: true,
          project_id: "proj_attached",
          name: "Repo",
          root_subpath: "",
        },
      }),
    );
    render(ProjectsView);

    await fireEvent.click(await screen.findByRole("button", { name: "Attach existing folder…" }));
    await fireEvent.input(screen.getByLabelText("Attached project name"), {
      target: { value: "Repo" },
    });
    await fireEvent.input(screen.getByLabelText("Folder path"), {
      target: { value: "C:/work/repo" },
    });
    await fireEvent.click(screen.getByRole("button", { name: "Attach folder" }));

    await waitFor(() => {
      const post = mock.mock.calls.find(
        (call) => (call[1]?.method ?? "GET").toUpperCase() === "POST",
      );
      expect(post).toBeTruthy();
      expect(JSON.parse(post![1]!.body as string)).toEqual({
        name: "Repo",
        attach_path: "C:/work/repo",
        attach_writable: true,
      });
    });
  });

  it("surfaces the server's refusal by name rather than as a generic failure", async () => {
    stubFetch(
      listRoutes({
        "POST /api/projects": {
          __status: 400,
          detail: { reason_code: "attach_path_inside_workspace" },
        },
      }),
    );
    render(ProjectsView);

    await fireEvent.click(await screen.findByRole("button", { name: "Attach existing folder…" }));
    await fireEvent.input(screen.getByLabelText("Attached project name"), {
      target: { value: "Repo" },
    });
    await fireEvent.input(screen.getByLabelText("Folder path"), {
      target: { value: "C:/ws/inside" },
    });
    await fireEvent.click(screen.getByRole("button", { name: "Attach folder" }));

    expect(await screen.findByText(/attach_path_inside_workspace/)).toBeInTheDocument();
  });
});

// ── Deleting ──────────────────────────────────────────────────────────────

/**
 * REM-PROJ-01 — Archive, Move and Delete moved into the card's overflow menu,
 * so reaching Delete is two steps and the helper below is both of them.
 *
 * Written as a helper rather than inlined because the point of the change is
 * that a destructive action is *not* one click from a card an owner clicks all
 * day; a test that could still find it in one would no longer be testing the
 * thing the row promises.
 */
async function openLifecycleMenu(projectName = "Alpha"): Promise<void> {
  await fireEvent.click(
    await screen.findByRole("button", { name: new RegExp(`More actions for ${projectName}`, "i") }),
  );
}

describe("ProjectsView deletion", () => {
  it("states that deleting an attached project keeps the folder", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    stubFetch({
      "GET /api/projects": {
        projects: [project({ root_kind: "attached", root_label: "repo" })],
        active_project_id: null,
      },
      "GET /api/projects/tree": [],
    });
    render(ProjectsView);

    await openLifecycleMenu();
    await fireEvent.click(await screen.findByRole("menuitem", { name: /^Delete$/ }));

    expect(confirmSpy.mock.calls[0][0]).toMatch(/folder repo will not be deleted/i);
  });

  it("keeps today's wording for a managed project", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    stubFetch({
      "GET /api/projects": { projects: [project({})], active_project_id: null },
      "GET /api/projects/tree": [],
    });
    render(ProjectsView);

    await openLifecycleMenu();
    await fireEvent.click(await screen.findByRole("menuitem", { name: /^Delete$/ }));

    expect(confirmSpy.mock.calls[0][0]).toMatch(/permanently delete all project chats and files/i);
  });

  it("keeps the three lifecycle actions off the card's own row", async () => {
    // REM-PROJ-01 / UX-PROJ-02 — the finding, as an assertion. Five actions at
    // equal weight meant Delete, which erases a managed project's folder, was
    // the same size and one click away as New chat, which an owner presses all
    // day. Work stays on the card; lifecycle is one deliberate reach further.
    stubFetch({
      "GET /api/projects": { projects: [project({})], active_project_id: null },
      "GET /api/projects/tree": [],
    });
    render(ProjectsView);

    expect(await screen.findByRole("button", { name: /^New chat$/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Start in Build$/ })).toBeInTheDocument();
    for (const action of [/^Archive$/, /^Move$/, /^Delete$/]) {
      expect(screen.queryByRole("button", { name: action })).toBeNull();
    }

    await openLifecycleMenu();
    for (const action of [/^Archive$/, /^Move$/, /^Delete$/]) {
      expect(screen.getByRole("menuitem", { name: action })).toBeInTheDocument();
    }
  });
});

/*
 * RR-PROJECT-01 — "New chat" on a project card starts the chat in that project.
 *
 * The button navigated and established nothing, while "Start in Build" beside
 * it established the project. Retrieval stays owner-wide; what changes is where
 * the conversation is filed, which is the ordinary meaning of the button.
 */
describe("ProjectsView work actions", () => {
  afterEach(() => resetWorkProject());

  it("makes the project the one a new chat is filed under", async () => {
    stubFetch({
      "GET /api/projects": { projects: [project({ project_id: "proj_7" })], active_project_id: null },
      "GET /api/projects/tree": [],
    });
    render(ProjectsView);

    await fireEvent.click(await screen.findByRole("button", { name: /^New chat$/ }));

    expect(workProject()).toBe("proj_7");
    expect(window.location.hash).toBe("#/new-chat");
  });

  it("sends Build to the same project, as it always did", async () => {
    stubFetch({
      "GET /api/projects": { projects: [project({ project_id: "proj_7" })], active_project_id: null },
      "GET /api/projects/tree": [],
    });
    render(ProjectsView);

    await fireEvent.click(await screen.findByRole("button", { name: /^Start in Build$/ }));

    expect(workProject()).toBe("proj_7");
    expect(window.location.hash).toBe("#/build");
  });
});

/*
 * NEW-PROJ-01 — a project header is a promise about everything under it.
 *
 * Four reads share one set of view variables. Resolve them out of order and the
 * page presented one project's name over another project's files, with nothing
 * on screen to say so. The fetch stub here is bespoke because the defect *is*
 * the ordering: the routes have to be resolvable by hand.
 */
describe("ProjectsView selection races", () => {
  type Deferred = { resolve: (value: unknown) => void; reject: (reason: unknown) => void };

  /**
   * A fetch stub whose named routes can be resolved by hand, one call at a
   * time. The defect *is* the ordering, so the queue is per route and per call:
   * two selections hit the same task and image endpoints, and the whole point is
   * to answer the first one after the second has already been answered.
   */
  function deferredFetch(immediate: Record<string, unknown>, deferredPaths: string[]) {
    const pending = new Map<string, Deferred[]>();
    const answer = (value: unknown) =>
      ({ ok: true, status: 200, json: async () => value }) as Response;
    const queue = (key: string) => {
      const existing = pending.get(key) ?? [];
      pending.set(key, existing);
      return existing;
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
        const path = url.split("?")[0];
        const key = `${(init?.method ?? "GET").toUpperCase()} ${path}`;
        if (deferredPaths.includes(key)) {
          return new Promise<Response>((resolve, reject) => {
            queue(key).push({ resolve: (value) => resolve(answer(value)), reject });
          });
        }
        if (key in immediate) return answer(immediate[key]);
        return { ok: false, status: 404, json: async () => ({ detail: { reason_code: "unrouted" } }) } as Response;
      }),
    );
    return {
      waiting: (key: string) => (pending.get(key) ?? []).length,
      answer: (key: string, index: number, value: unknown) =>
        pending.get(key)![index].resolve(value),
      fail: (key: string, index: number, reason: unknown) =>
        pending.get(key)![index].reject(reason),
    };
  }

  const detailOf = (id: string, name: string) => ({
    project: project({ project_id: id, name }),
    context: { instructions: "", attachment_ids: [], memory_enabled: false, memory_mode: "inherit" },
    sessions: [],
    checkpoints: [],
  });

  const LIST = {
    projects: [
      project({ project_id: "proj_a", name: "Alpha" }),
      project({ project_id: "proj_b", name: "Beta", root_subpath: "projects/beta" }),
    ],
    active_project_id: null,
  };

  const filesOf = (id: string, subpath: string) => ({
    project_id: id,
    root_subpath: subpath,
    root_exists: true,
    truncated: false,
    note: "",
    files: [],
    provenance: {},
  });

  it("does not stand one project's header over another project's work", async () => {
    const control = deferredFetch(
      {
        "GET /api/projects": LIST,
        "GET /api/projects/tree": [],
        "GET /api/projects/proj_a": detailOf("proj_a", "Alpha"),
        "GET /api/projects/proj_b": detailOf("proj_b", "Beta"),
        "GET /api/projects/proj_a/files": filesOf("proj_a", "projects/alpha"),
        "GET /api/projects/proj_b/files": filesOf("proj_b", "projects/beta"),
        "GET /api/images": { sizes: [], generations: [] },
      },
      ["GET /api/tasks"],
    );
    render(ProjectsView);

    await fireEvent.click(await screen.findByRole("button", { name: /open project alpha/i }));
    await waitFor(() => expect(control.waiting("GET /api/tasks")).toBe(1));

    await fireEvent.click(screen.getByRole("button", { name: /open project beta/i }));
    await waitFor(() => expect(control.waiting("GET /api/tasks")).toBe(2));

    // Beta is on screen and has no work. Alpha's task read now lands, late.
    control.answer("GET /api/tasks", 1, []);
    control.answer("GET /api/tasks", 0, [
      {
        task_id: "task_alpha",
        title: "Alpha's private task",
        state: "scheduled",
        schedule_kind: "once",
        schedule_value: "",
        next_run_at: null,
        last_run_at: null,
        last_status: null,
        created_at: "2026-09-01T00:00:00Z",
        project_id: "proj_a",
      },
    ]);
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(screen.getByRole("heading", { name: "Beta" })).toBeInTheDocument();
    expect(screen.queryByText("Alpha's private task")).toBeNull();
  });

  it("does not let an older failure clear a newer selection", async () => {
    // The other direction of the same race, and the one that looks like a bug in
    // the project you *did* open: a rejected read for a project you left behind
    // replaced a workspace that had loaded correctly with an error about it.
    const control = deferredFetch(
      {
        "GET /api/projects": LIST,
        "GET /api/projects/tree": [],
        "GET /api/projects/proj_b": detailOf("proj_b", "Beta"),
        "GET /api/projects/proj_b/files": filesOf("proj_b", "projects/beta"),
        "GET /api/tasks": [],
        "GET /api/images": { sizes: [], generations: [] },
      },
      ["GET /api/projects/proj_a"],
    );
    render(ProjectsView);

    await fireEvent.click(await screen.findByRole("button", { name: /open project alpha/i }));
    await waitFor(() => expect(control.waiting("GET /api/projects/proj_a")).toBe(1));

    await fireEvent.click(screen.getByRole("button", { name: /open project beta/i }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Beta" })).toBeInTheDocument());

    control.fail("GET /api/projects/proj_a", 0, new TypeError("network"));
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(screen.getByRole("heading", { name: "Beta" })).toBeInTheDocument();
    expect(screen.queryByText(/Could not load project/)).toBeNull();
  });
});
