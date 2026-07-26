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

  it("sets a project active via PUT /api/projects/selection", async () => {
    const mock = stubFetch({
      "GET /api/projects": {
        projects: [project({ project_id: "proj_1", name: "Alpha" })],
        active_project_id: null,
      },
      "GET /api/projects/tree": [],
      "PUT /api/projects/selection": { ok: true, active_project_id: "proj_1" },
    });
    render(ProjectsView);
    await waitFor(() => expect(screen.getByText("Set active")).toBeInTheDocument());
    await fireEvent.click(screen.getByText("Set active"));

    await waitFor(() => {
      const put = mock.mock.calls.find(
        (c) =>
          (c[1]?.method ?? "GET").toUpperCase() === "PUT" &&
          String(c[0]).includes("/api/projects/selection"),
      );
      expect(put).toBeTruthy();
      expect(JSON.parse(put![1]!.body as string)).toEqual({ project_id: "proj_1" });
    });
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
    await waitFor(() => expect(screen.getByText("Details")).toBeInTheDocument());
    await fireEvent.click(screen.getByText("Details"));
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
    await waitFor(() => expect(screen.getByText("Details")).toBeInTheDocument());
    await fireEvent.click(screen.getByText("Details"));
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
// Opening a project shows its files and the work scoped to it. Files are
// metadata plus provenance — never content — and selecting one links the change
// back to the turn that made it.
describe("ProjectsView context home", () => {
  const DETAIL = {
    project: project({}),
    context: { instructions: "", attachment_ids: [], memory_enabled: false, memory_mode: "inherit" },
    sessions: [],
    checkpoints: [],
  };

  const FILES = {
    project_id: "proj_1",
    root_subpath: "projects/alpha",
    root_exists: true,
    truncated: false,
    note: "Metadata only. Raiker never serves workspace file content to the browser.",
    files: [
      {
        workspace_path: "projects/alpha/brief.md",
        name: "brief.md",
        is_directory: false,
        size_bytes: 2048,
        modified_at: "2026-07-24T00:00:00Z",
        depth: 0,
      },
    ],
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
      "GET /api/tasks": [],
      ...overrides,
    };
  }

  async function openDetail(routeMap: Record<string, unknown>) {
    stubFetch(routeMap);
    render(ProjectsView);
    await waitFor(() => expect(screen.getByText("Details")).toBeInTheDocument());
    await fireEvent.click(screen.getByText("Details"));
  }

  it("lists project files as metadata and flags governed changes", async () => {
    await openDetail(routes());
    expect(await screen.findByLabelText("Inspect projects/alpha/brief.md")).toBeInTheDocument();
    expect(screen.getByText("2.0 KB")).toBeInTheDocument();
    expect(screen.getByText("governed change")).toBeInTheDocument();
  });

  it("links a file's provenance back to the session and audit log", async () => {
    await openDetail(routes());
    await fireEvent.click(await screen.findByLabelText("Inspect projects/alpha/brief.md"));

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

  it("states that content is never shown, only what changed", async () => {
    await openDetail(routes());
    await fireEvent.click(await screen.findByLabelText("Inspect projects/alpha/brief.md"));
    expect(
      await screen.findByText(/shows what changed and who changed it, never the file's contents/i),
    ).toBeInTheDocument();
  });

  it("says a file has no recorded governed write rather than implying one", async () => {
    await openDetail(routes({ "GET /api/projects/proj_1/files": { ...FILES, provenance: {} } }));
    await fireEvent.click(await screen.findByLabelText("Inspect projects/alpha/brief.md"));
    expect(
      await screen.findByText(/no governed write is recorded against this path/i),
    ).toBeInTheDocument();
  });

  it("explains a project folder that does not exist on disk yet", async () => {
    await openDetail(
      routes({
        "GET /api/projects/proj_1/files": { ...FILES, root_exists: false, files: [], provenance: {} },
      }),
    );
    expect(await screen.findByText(/does not exist on disk yet/i)).toBeInTheDocument();
  });

  it("degrades politely when the file listing is unavailable", async () => {
    const withoutFiles = Object.fromEntries(
      Object.entries(routes()).filter(([key]) => key !== "GET /api/projects/proj_1/files"),
    );
    await openDetail(withoutFiles);
    expect(await screen.findByText(/files unavailable \(404\)/i)).toBeInTheDocument();
    // The rest of the project home stays usable.
    expect(await screen.findByText("Project context")).toBeInTheDocument();
  });
});
