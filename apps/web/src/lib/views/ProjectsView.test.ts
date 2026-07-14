// Coverage for the Projects view (web-app task 5): list + create + set-active.
// A project is an organizing scope only; the view never grants anything —
// creation POSTs a name (the root subpath is derived server-side) and
// activation PUTs the selection.
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ProjectView } from "../apiTypes";
import { stubFetch } from "../test-helpers";
import ProjectsView from "./ProjectsView.svelte";

afterEach(() => {
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

    render(ProjectsView);
    await waitFor(() => expect(screen.getByText("Details")).toBeInTheDocument());
    await fireEvent.click(screen.getByText("Details"));
    await waitFor(() => expect(screen.getByRole("button", { name: "Export project" })).toBeInTheDocument());
    await fireEvent.click(screen.getByRole("button", { name: "Export project" }));

    await waitFor(() => {
      expect(mock).toHaveBeenCalledWith("/api/projects/proj_1/export", expect.objectContaining({ method: "POST" }));
      expect(createObjectURL).toHaveBeenCalledOnce();
      expect(click).toHaveBeenCalledOnce();
      expect(revokeObjectURL).toHaveBeenCalledWith("blob:export");
    });
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
