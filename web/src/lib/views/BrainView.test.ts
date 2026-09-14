import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
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
  // ── NEW-MAP-01 and NEW-MAP-02 — what the map shows, and when it was true ──

  it("stops calling a graph live once a refresh has failed (NEW-MAP-01)", async () => {
    // The graph an owner reads to decide what Raiker knows about them kept the
    // words "Live workspace graph" through every failed refresh, because the
    // label only ever asked whether *some* update had once happened.
    vi.useFakeTimers();
    let calls = 0;
    const GRAPH = {
      generated_at: "2026-09-13T00:00:00Z",
      illustrative_motion_notice: "Stored records only.",
      nodes: [
        { node_id: "principal:p", node_type: "user", label: "You", status: "active", detail: null, progress_percent: null, is_real: true },
      ],
      edges: [],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
        if (url.includes("/api/brain/settings")) {
          return { ok: true, status: 200, json: async () => ({ settings: {} }) } as Response;
        }
        if (url.includes("/api/brain")) {
          calls += 1;
          if (calls > 1) return { ok: false, status: 500, json: async () => ({}) } as Response;
          return { ok: true, status: 200, json: async () => GRAPH } as Response;
        }
        return { ok: false, status: 404, json: async () => ({}) } as Response;
      }),
    );
    render(BrainView);

    expect(await screen.findByText("Live workspace graph")).toBeInTheDocument();

    await vi.advanceTimersByTimeAsync(15_000);
    await vi.waitFor(() => expect(screen.queryByText("Live workspace graph")).toBeNull());
    // Still on screen — throwing away the only graph anyone has helps nobody —
    // and it says how old it is and that renewing it failed.
    expect(screen.getByText(/last updated/i)).toHaveTextContent(/refresh failed/i);
    expect(screen.getByRole("button", { name: /You, user record/i })).toBeInTheDocument();
    vi.useRealTimers();
  });

  // Both NEW-MAP-02 cases pick their source from the browser, which is how the
  // dialog is actually used: the "Selected source" field only exists once
  // something is selected.
  const BROWSE = {
    // A folder rather than the top level: at the top the browser lists the
    // *places* an owner has granted, and files only appear inside one.
    path: "/granted",
    parent: "",
    truncated: false,
    roots: [],
    children: [
      { name: "notes-a.md", path: "/granted/notes-a.md", kind: "file" },
      { name: "notes-b.md", path: "/granted/notes-b.md", kind: "file" },
    ],
  };

  const GRAPH_ONE_NODE = {
    generated_at: "2026-09-13T00:00:00Z",
    illustrative_motion_notice: "Stored records only.",
    nodes: [
      { node_id: "principal:p", node_type: "user", label: "You", status: "active", detail: null, progress_percent: null, is_real: true },
    ],
    edges: [],
  };

  function sourceDialogFetch(
    review: (path: string) => Promise<Response> | Response,
  ): ReturnType<typeof vi.fn> {
    return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/api/brain/settings")) {
        return { ok: true, status: 200, json: async () => ({ settings: {} }) } as Response;
      }
      if (url.includes("/api/brain/sources/review")) {
        const body = JSON.parse(String(init?.body ?? "{}")) as { path?: string };
        return review(String(body.path ?? ""));
      }
      if (url.includes("/api/brain/sources/browse")) {
        return { ok: true, status: 200, json: async () => BROWSE } as Response;
      }
      if (url.includes("/api/brain/sources")) {
        return { ok: true, status: 200, json: async () => ({ ok: true }) } as Response;
      }
      if (url.includes("/api/brain")) {
        return { ok: true, status: 200, json: async () => GRAPH_ONE_NODE } as Response;
      }
      return { ok: false, status: 404, json: async () => ({}) } as Response;
    });
  }

  function plan(path: string, supported: number): Response {
    return {
      ok: true,
      status: 200,
      json: async () => ({ path, supported_files: supported, unsupported_files: 0, total_bytes: supported * 10, warnings: [] }),
    } as Response;
  }

  it("never presents one file's indexing plan under another's selection (NEW-MAP-02)", async () => {
    // The reachable reproduction. Reviewing disables its own button while it
    // runs, but *choosing a different source* in the browser does not — and it
    // is the browser the dialog is built around. Select A, review it, pick B
    // while A is still on the wire, and A's plan used to land under B's
    // selection; **Add reviewed source** then added A, because it adds
    // `sourceReview.path`. The owner reads a plan for one source and indexes
    // another.
    const slow: { release: ((value: Response) => void) | null } = { release: null };
    const fetchMock = sourceDialogFetch((path) =>
      path === "/granted/notes-a.md"
        ? new Promise<Response>((resolve) => { slow.release = resolve; })
        : plan(path, 2),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(BrainView);

    await fireEvent.click(await screen.findByRole("button", { name: "Add workspace source" }));
    await fireEvent.click(await screen.findByRole("button", { name: /notes-a\.md/ }));
    await fireEvent.click(await screen.findByRole("button", { name: /Review indexing plan/i }));

    // The owner changes their mind while A is still on the wire.
    await fireEvent.click(screen.getByRole("button", { name: /notes-b\.md/ }));
    expect(screen.queryByRole("region", { name: "Source indexing review" })).toBeNull();

    // A finally answers. It is a plan for a source that is no longer selected,
    // so it is not shown at all.
    slow.release?.(plan("/granted/notes-a.md", 900));
    await waitFor(() => expect(screen.getByLabelText("Selected source")).toHaveValue("/granted/notes-b.md"));
    expect(screen.queryByRole("region", { name: "Source indexing review" })).toBeNull();
    expect(screen.queryByText(/notes-a\.md/)).not.toHaveTextContent("900");

    // Reviewing the source that *is* selected works, and adds that one. Found
    // by writing this: the superseded response still has to release the dialog,
    // or the owner is left looking at a "Reviewing…" button for a review whose
    // answer was thrown away.
    await fireEvent.click(await screen.findByRole("button", { name: /Review indexing plan/i }));
    const review = await screen.findByRole("region", { name: "Source indexing review" });
    expect(review).toHaveTextContent("/granted/notes-b.md");
    await fireEvent.click(within(review).getByRole("button", { name: "Add reviewed source" }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([url, init]) =>
            String(url).endsWith("/api/brain/sources") &&
            String((init as RequestInit | undefined)?.body ?? "").includes("/granted/notes-b.md"),
        ),
      ).toBe(true),
    );
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url).endsWith("/api/brain/sources") &&
          String((init as RequestInit | undefined)?.body ?? "").includes("notes-a"),
      ),
    ).toBe(false);
  });

  it("refuses to add a plan whose selection has since changed (NEW-MAP-02)", async () => {
    const fetchMock = sourceDialogFetch((path) => plan(path, 1));
    vi.stubGlobal("fetch", fetchMock);
    render(BrainView);

    await fireEvent.click(await screen.findByRole("button", { name: "Add workspace source" }));
    await fireEvent.click(await screen.findByRole("button", { name: /notes-a\.md/ }));
    await fireEvent.click(await screen.findByRole("button", { name: /Review indexing plan/i }));
    const review = await screen.findByRole("region", { name: "Source indexing review" });
    expect(review).toHaveTextContent("/granted/notes-a.md");

    // The field stays editable while a plan is on screen, which is fine — what
    // is not fine is adding the plan for something else.
    const selected = screen.getByLabelText("Selected source");
    await fireEvent.input(selected, { target: { value: "/granted/notes-b.md" } });
    // Editing clears the plan, so the owner cannot press Add at all; the guard
    // below is what holds if a future change ever stops clearing it.
    expect(screen.queryByRole("region", { name: "Source indexing review" })).toBeNull();
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url).endsWith("/api/brain/sources") &&
          String((init as RequestInit | undefined)?.body ?? "").includes("notes-a"),
      ),
    ).toBe(false);
  });
});
