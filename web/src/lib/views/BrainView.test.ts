import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import BrainView from "./BrainView.svelte";
import { stubFetch, stubFetchPending } from "../test-helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("BrainView", () => {
  it("shows a route-level loading state while the graph is fetched", async () => {
    stubFetchPending();
    render(BrainView);
    const statuses = await screen.findAllByRole("status");
    expect(statuses.some((el) => /loading the knowledge graph/i.test(el.textContent ?? ""))).toBe(true);
  });

  it("shows a route-level error state when the graph cannot load", async () => {
    stubFetch({});
    render(BrainView);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/couldn't load the knowledge graph/i);
    expect(alert).toHaveTextContent(/unavailable \(404\)/i);
  });

  it("renders runtime records in a force-directed graph with graph controls", async () => {
    stubFetch({
      "GET /api/brain": {
        generated_at: "2026-07-15T00:00:00Z",
        illustrative_motion_notice: "Animated pulses indicate visual activity only; every node and connection is stored runtime data.",
        nodes: [
          { node_id: "principal:p", node_type: "user", label: "You", status: "active", detail: null, progress_percent: null, is_real: true },
          { node_id: "task:t", node_type: "task", label: "Draft a plan", status: "running", detail: "Write outline", progress_percent: 40, is_real: true },
          { node_id: "agent:a", node_type: "agent", label: "Researcher", status: "idle", detail: "Draft a plan", progress_percent: null, is_real: true },
        ],
        edges: [{ source: "principal:p", target: "task:t", relationship: "tracks", is_active: true }],
      },
    });
    render(BrainView);

    await waitFor(() => expect(screen.getByRole("button", { name: /Draft a plan, task record/i })).toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "Knowledge Map" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Researcher, agent record/i })).toBeInTheDocument();
    expect(screen.getByRole("application", { name: /interactive force-directed knowledge graph/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add workspace source" })).toBeInTheDocument();

    // The Global/Local segmented control is gone. It sat in the toolbar
    // permanently while being half disabled: `centreNode()` already enters local
    // mode when a node is focused, so the switch's only unique job was leaving
    // it again — and that now lives beside the depth slider, which is the other
    // control that exists only in local mode. Nothing announces the scope you
    // are already looking at.
    expect(screen.queryByRole("button", { name: "Global" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Local" })).toBeNull();
    expect(screen.queryByRole("button", { name: /fullscreen/i })).toBeNull();
    // Global is the resting scope, so neither the depth control nor its way out
    // is on screen until something is focused.
    expect(screen.queryByLabelText("Relationship depth")).toBeNull();
    expect(screen.queryByRole("button", { name: "Show all" })).toBeNull();
  });

  it("shows evidence and lets the owner reject a reviewed entity link", async () => {
    vi.spyOn(window, "prompt").mockReturnValue("Incorrect relationship");
    const fetchMock = stubFetch({
      "GET /api/brain": {
        generated_at: "2026-08-21T00:00:00Z",
        illustrative_motion_notice: "Stored records only.",
        nodes: [
          { node_id: "principal:p", node_type: "user", label: "You", status: "active", detail: null, progress_percent: null, is_real: true },
          { node_id: "entity:rahul", node_type: "entity", label: "Rahul", status: "reviewed", detail: "person", progress_percent: null, is_real: true },
          { node_id: "entity:raiker", node_type: "entity", label: "Raiker", status: "reviewed", detail: "project", progress_percent: null, is_real: true },
        ],
        edges: [{
          source: "entity:rahul", target: "entity:raiker", relationship: "works_on",
          is_active: false, relationship_id: "rel_1", evidence_memory_id: "mem_1",
          owner_can_reject: true,
        }],
      },
      "POST /api/memory/entity-relationships/rel_1/reject": {
        ok: true, relationship_id: "rel_1", active: false,
      },
    });
    render(BrainView);

    await fireEvent.click(await screen.findByRole("button", { name: /Rahul, entity record/i }));
    expect(await screen.findByText("Evidence: mem_1")).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: /reject link/i }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/memory/entity-relationships/rel_1/reject",
      expect.objectContaining({ method: "POST" }),
    ));
  });

  it("shows the governed starter graph and opens force settings", async () => {
    stubFetch({
      "GET /api/brain": {
        generated_at: "2026-07-15T00:00:00Z",
        illustrative_motion_notice: "Visual motion only.",
        nodes: [{ node_id: "principal:p", node_type: "user", label: "You", status: "active", detail: null, progress_percent: null, is_real: true }],
        edges: [],
      },
    });
    render(BrainView);

    expect(await screen.findByText("Build your knowledge graph")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Workspace, workspace record/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Add first source, source record/i })).toBeInTheDocument();
    screen.getByRole("button", { name: "Graph settings" }).click();
    expect(await screen.findByRole("complementary", { name: "Graph settings" })).toBeInTheDocument();
    expect(screen.getByText("Centre force")).toBeInTheDocument();
    expect(screen.getByText("Always alive")).toBeInTheDocument();
  });

  it("opens on the boundary, browses one root, and reviews before adding", async () => {
    const fetchMock = stubFetch({
      "GET /api/brain": {
        generated_at: "2026-07-15T00:00:00Z", illustrative_motion_notice: "Visual motion only.",
        nodes: [{ node_id: "principal:p", node_type: "user", label: "You", status: "active", detail: null, progress_percent: null, is_real: true }], edges: [],
      },
      "GET /api/brain/settings": { settings: {} },
      // The picker's first read is the boundary itself: named places, never a
      // listing of the workspace (BUG-88).
      "GET /api/brain/sources/browse": {
        path: "", parent: null, truncated: false, children: [],
        roots: [
          { root_id: "generated-files", label: "Generated files", detail: "Documents Raiker produced.", kind: "raiker", browsable: true, path: null },
          { root_id: "raiker-database", label: "Raiker database", detail: "Chat, Build, Tasks, Schedules and uploads are already in this graph.", kind: "database", browsable: false, path: null },
        ],
      },
      "GET /api/brain/sources/browse?path=generated-files": {
        path: "generated-files", parent: "", truncated: false, roots: [],
        children: [{ name: "notes.md", path: "generated-files/notes.md", kind: "file", size_bytes: 12 }],
      },
      "POST /api/brain/sources/review": {
        path: "generated-files/notes.md", kind: "file", supported_files: 1, unsupported_files: 0,
        total_bytes: 12, examples: ["generated-files/notes.md"], warnings: [], review_cap: 5000,
      },
      "POST /api/brain/sources": { ok: true, path: "generated-files/notes.md" },
    });
    render(BrainView);
    await screen.findByRole("button", { name: "Add workspace source" });
    await fireEvent.click(screen.getByRole("button", { name: "Add workspace source" }));
    expect(screen.getByRole("dialog", { name: "Add a source" }).tagName).toBe("DIALOG");
    // The database is listed so the owner can see it is covered, and is not
    // offered as a folder to walk.
    expect(screen.getByText("Raiker database")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Raiker database/ })).toBeDisabled();
    await fireEvent.click(screen.getByRole("button", { name: /Generated files/ }));
    await fireEvent.click(await screen.findByRole("button", { name: /notes\.md/ }));
    await fireEvent.click(screen.getByRole("button", { name: "Review indexing plan" }));
    expect(await screen.findByText("Indexing plan")).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Add reviewed source" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/brain/sources", expect.objectContaining({ method: "POST" }),
    ));
  });

  it("will not store a file from the computer until the owner says it may", async () => {
    // Granting a folder reads it where it is; an upload duplicates the file
    // into the workspace, so the copy is a separate, explicit decision.
    stubFetch({
      "GET /api/brain": {
        generated_at: "2026-07-15T00:00:00Z", illustrative_motion_notice: "Visual motion only.",
        nodes: [{ node_id: "principal:p", node_type: "user", label: "You", status: "active", detail: null, progress_percent: null, is_real: true }], edges: [],
      },
      "GET /api/brain/settings": { settings: {} },
      "GET /api/brain/sources/browse": { path: "", parent: null, truncated: false, children: [], roots: [] },
    });
    render(BrainView);
    await fireEvent.click(await screen.findByRole("button", { name: "Add workspace source" }));

    // Reading in place is offered beside the copy, and says which it is.
    expect(screen.getByLabelText(/Grant a folder/)).toBeInTheDocument();
    expect(screen.getByText(/Or add a single file/)).toBeInTheDocument();

    const picker = screen.getByLabelText("File to copy into Raiker") as HTMLInputElement;
    const file = new File(["notes"], "notes.md", { type: "text/markdown" });
    Object.defineProperty(picker, "files", { value: [file] });
    await fireEvent.change(picker);

    // Choosing a file is not consent: the store button exists only behind the
    // tick, and is disabled until it is ticked.
    const store = await screen.findByRole("button", { name: "Store the copy and add it" });
    expect(store).toBeDisabled();
    await fireEvent.click(screen.getByRole("checkbox"));
    expect(store).toBeEnabled();
  });

  it("opens source review by keyboard and restores focus when it closes", async () => {
    stubFetch({
      "GET /api/brain": {
        generated_at: "2026-07-15T00:00:00Z", illustrative_motion_notice: "Visual motion only.",
        nodes: [{ node_id: "principal:p", node_type: "user", label: "You", status: "active", detail: null, progress_percent: null, is_real: true }], edges: [],
      },
      "GET /api/brain/settings": { settings: {} },
      "GET /api/brain/sources/browse": { path: "", parent: null, truncated: false, children: [], roots: [] },
    });
    render(BrainView);
    const trigger = await screen.findByRole("button", { name: "Add workspace source" });
    trigger.focus();
    await fireEvent.keyDown(trigger, { key: "Enter" });
    await fireEvent.click(trigger);
    const dialog = screen.getByRole("dialog", { name: "Add a source" });
    await fireEvent(dialog, new Event("cancel", { cancelable: true }));
    await waitFor(() => expect(trigger).toHaveFocus());
  });
});
