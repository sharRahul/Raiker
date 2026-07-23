// Conversation organisation: pin/bookmark + bulk delete in the Sessions view.
// These are organizing actions only — they grant nothing. The view surfaces
// pinned sessions first and lets the user select and delete one or many.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import SessionsView from "./SessionsView.svelte";
import { stubFetch } from "../test-helpers";

const SESSIONS_ROUTE = {
  "GET /api/sessions": [
    {
      session_id: "sess_b",
      title: "Second chat",
      status: "open",
      created_at: "2026-07-10T00:00:00Z",
      updated_at: "2026-07-10T00:01:00Z",
      turn_count: 1,
      pinned: false,
      tags: ["alpha"],
      project_id: null,
      archived: false,
      archived_at: null,
    },
    {
      session_id: "sess_a",
      title: "Pinned chat",
      status: "open",
      created_at: "2026-07-09T00:00:00Z",
      updated_at: "2026-07-09T00:00:30Z",
      turn_count: 2,
      pinned: true,
      tags: [],
      project_id: null,
      archived: false,
      archived_at: null,
    },
  ],
  "GET /api/projects": {
    projects: [
      {
        project_id: "proj_a",
        name: "Alpha",
        root_subpath: "alpha",
        created_at: "2026-07-01T00:00:00Z",
        session_count: 0,
        selected: false,
        parent_id: null,
        path: "/",
        is_archived: false,
        archived_at: null,
      },
    ],
    active_project_id: null,
  },
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("SessionsView organisation", () => {
  it("surfaces pinned sessions first", async () => {
    stubFetch(SESSIONS_ROUTE);
    render(SessionsView);

    await waitFor(() => expect(screen.getByText("Pinned chat")).toBeInTheDocument());

    // The pinned session must appear before the unpinned one regardless of
    // the backend's updated_at order. Skip the header row.
    const rows = screen.getAllByRole("row").slice(1);
    expect(rows[0].textContent).toContain("Pinned chat");
    expect(rows[1].textContent).toContain("Second chat");
  });

  it("pins a session by toggling the star and refreshes", async () => {
    const fetchMock = stubFetch({
      ...SESSIONS_ROUTE,
      "PUT /api/sessions/sess_b/pin": { ok: true, session_id: "sess_b", pinned: true },
    });
    render(SessionsView);

    await waitFor(() => expect(screen.getByText("Pinned chat")).toBeInTheDocument());
    // Pin lives in the row's session menu; the unpinned row offers "Pin".
    const row = screen.getByText("Second chat").closest("tr")!;
    await fireEvent.click(within(row as HTMLElement).getByRole("button", { name: /session actions/i }));
    await fireEvent.click(within(row as HTMLElement).getByRole("menuitem", { name: /^pin$/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/sessions/sess_b/pin",
        expect.objectContaining({ method: "PUT" }),
      );
    });
    // The list is reloaded after the toggle.
    await waitFor(() => {
      const listCalls = fetchMock.mock.calls.filter(
        (c) => String(c[0]) === "/api/sessions" && (c[1]?.method ?? "GET") === "GET",
      );
      expect(listCalls.length).toBeGreaterThan(1);
    });
  });

  it("deletes a single session after confirmation and refreshes", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    const fetchMock = stubFetch({
      ...SESSIONS_ROUTE,
      "DELETE /api/sessions/sess_b": { ok: true, session_id: "sess_b" },
    });
    render(SessionsView);

    await waitFor(() => expect(screen.getByText("Second chat")).toBeInTheDocument());
    // Delete lives in the row's session menu.
    const row = screen.getByText("Second chat").closest("tr")!;
    await fireEvent.click(within(row as HTMLElement).getByRole("button", { name: /session actions/i }));
    await fireEvent.click(within(row as HTMLElement).getByRole("menuitem", { name: /delete/i }));

    // The DELETE call must carry the confirmation header. `request()` wraps
    // headers in a Headers object, so read it back through `.get`.
    await waitFor(() => {
      const deleteCall = fetchMock.mock.calls.find(
        (c) => String(c[0]) === "/api/sessions/sess_b" && c[1]?.method === "DELETE",
      );
      expect(deleteCall).toBeDefined();
      const headers = deleteCall![1]!.headers as Headers;
      expect(headers.get("X-Session-Delete-Confirm")).toBe("sess_b");
    });
    expect(confirmSpy).toHaveBeenCalled();
  });

  it("deletes multiple selected sessions via the bulk bar", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const fetchMock = stubFetch({
      ...SESSIONS_ROUTE,
      "DELETE /api/sessions/bulk": { ok: true, session_ids: ["sess_a", "sess_b"] },
    });
    render(SessionsView);

    await waitFor(() => expect(screen.getByText("Pinned chat")).toBeInTheDocument());
    // Select both sessions (skip the header select-all checkbox by targeting
    // only the per-session checkboxes, which carry the session title in their
    // aria-label).
    const checkboxes = screen.getAllByRole("checkbox", { name: /Pinned chat|Second chat/i });
    for (const cb of checkboxes) await fireEvent.click(cb);

    // The bulk bar appears with the count and a delete button.
    expect(screen.getByText(/2 selected/i)).toBeInTheDocument();
    const bulkDelete = screen.getByRole("button", { name: /delete selected/i });
    await fireEvent.click(bulkDelete);

    await waitFor(() => {
      const bulkDelete = fetchMock.mock.calls.find(
        (c) => String(c[0]) === "/api/sessions/bulk" && c[1]?.method === "DELETE",
      );
      expect(bulkDelete).toBeDefined();
      expect(JSON.parse(String(bulkDelete![1]!.body))).toEqual({ session_ids: ["sess_a", "sess_b"] });
    });
    expect(
      fetchMock.mock.calls.some(
        (c) =>
          (String(c[0]) === "/api/sessions/sess_a" || String(c[0]) === "/api/sessions/sess_b") &&
          c[1]?.method === "DELETE",
      ),
    ).toBe(false);
  });

  it("renders tag chips for sessions that carry tags", async () => {
    stubFetch(SESSIONS_ROUTE);
    render(SessionsView);

    await waitFor(() => expect(screen.getByText("Second chat")).toBeInTheDocument());
    // The "alpha" chip is rendered for sess_b (which carries ["alpha"]).
    expect(screen.getByText("alpha")).toBeInTheDocument();
    // sess_a has no tags, so it has no chip — only one chip text node.
    expect(screen.getAllByText("alpha").length).toBe(1);
  });

  it("adds a tag by typing and clicking the add button, then refreshes", async () => {
    const fetchMock = stubFetch({
      ...SESSIONS_ROUTE,
      "PUT /api/sessions/sess_a/tags": { ok: true, session_id: "sess_a", tags: ["beta"] },
    });
    render(SessionsView);

    await waitFor(() => expect(screen.getByText("Pinned chat")).toBeInTheDocument());
    // Target the add-tag input inside the "Pinned chat" row (sess_a), since
    // that row has no chips yet.
    const row = screen.getByText("Pinned chat").closest("tr")!;
    const input = row.querySelector('input[aria-label^="Add a tag to"]') as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "beta" } });

    const addBtn = row.querySelector('button[aria-label^="Add tag to"]') as HTMLButtonElement;
    await fireEvent.click(addBtn);

    await waitFor(() => {
      const putCall = fetchMock.mock.calls.find(
        (c) => String(c[0]) === "/api/sessions/sess_a/tags" && c[1]?.method === "PUT",
      );
      expect(putCall).toBeDefined();
      const body = JSON.parse(String(putCall![1]!.body));
      expect(body.tags).toEqual(["beta"]);
    });
    // The list is reloaded after the toggle.
    await waitFor(() => {
      const listCalls = fetchMock.mock.calls.filter(
        (c) => String(c[0]) === "/api/sessions" && (c[1]?.method ?? "GET") === "GET",
      );
      expect(listCalls.length).toBeGreaterThan(1);
    });
  });

  it("removes a tag by clicking the chip × button", async () => {
    const fetchMock = stubFetch({
      ...SESSIONS_ROUTE,
      "PUT /api/sessions/sess_b/tags": { ok: true, session_id: "sess_b", tags: [] },
    });
    render(SessionsView);

    await waitFor(() => expect(screen.getByText("Second chat")).toBeInTheDocument());
    // sess_b carries ["alpha"]; the remove button is labelled "Remove tag alpha from Second chat".
    const removeBtn = screen.getByRole("button", { name: /remove tag alpha from second chat/i });
    await fireEvent.click(removeBtn);

    await waitFor(() => {
      const putCall = fetchMock.mock.calls.find(
        (c) => String(c[0]) === "/api/sessions/sess_b/tags" && c[1]?.method === "PUT",
      );
      expect(putCall).toBeDefined();
      const body = JSON.parse(String(putCall![1]!.body));
      // The remove path sends the remaining tags (alpha filtered out → []).
      expect(body.tags).toEqual([]);
    });
  });

  it("filters the list down to sessions whose tags contain the query", async () => {
    stubFetch(SESSIONS_ROUTE);
    render(SessionsView);

    await waitFor(() => expect(screen.getByText("Pinned chat")).toBeInTheDocument());
    // Both sessions are visible before filtering.
    expect(screen.getByText("Second chat")).toBeInTheDocument();
    expect(screen.getByText("Pinned chat")).toBeInTheDocument();

    const filterInput = screen.getByLabelText("Filter sessions by tag");
    await fireEvent.input(filterInput, { target: { value: "alpha" } });

    // Only sess_b carries the "alpha" tag; sess_a is filtered out.
    await waitFor(() => expect(screen.getByText("Second chat")).toBeInTheDocument());
    expect(screen.queryByText("Pinned chat")).toBeNull();
  });

  it("selects every visible session from the select-all checkbox", async () => {
    stubFetch(SESSIONS_ROUTE);
    render(SessionsView);

    await waitFor(() => expect(screen.getByText("Pinned chat")).toBeInTheDocument());
    await fireEvent.click(screen.getByRole("checkbox", { name: "Select all sessions" }));
    expect(screen.getByText(/2 selected/i)).toBeInTheDocument();
  });

  it("clears hidden selections when the tag filter changes", async () => {
    stubFetch(SESSIONS_ROUTE);
    render(SessionsView);

    await waitFor(() => expect(screen.getByText("Pinned chat")).toBeInTheDocument());
    await fireEvent.click(screen.getByRole("checkbox", { name: "Select all sessions" }));
    expect(screen.getByText(/2 selected/i)).toBeInTheDocument();

    // Filtering to "alpha" hides sess_a; its selection must not survive as an
    // invisible member of a later bulk action.
    await fireEvent.input(screen.getByLabelText("Filter sessions by tag"), {
      target: { value: "alpha" },
    });
    await waitFor(() => expect(screen.getByText(/1 selected/i)).toBeInTheDocument());
  });

  it("renames a session from the session menu", async () => {
    const fetchMock = stubFetch({
      ...SESSIONS_ROUTE,
      "PUT /api/sessions/sess_b/rename": { ok: true, session_id: "sess_b", title: "Renamed chat" },
    });
    render(SessionsView);

    await waitFor(() => expect(screen.getByText("Second chat")).toBeInTheDocument());
    const row = screen.getByText("Second chat").closest("tr")!;
    await fireEvent.click(within(row as HTMLElement).getByRole("button", { name: /session actions/i }));
    await fireEvent.click(within(row as HTMLElement).getByRole("menuitem", { name: /rename/i }));
    await fireEvent.input(within(row as HTMLElement).getByLabelText("Session title"), {
      target: { value: "Renamed chat" },
    });
    await fireEvent.click(within(row as HTMLElement).getByRole("menuitem", { name: "Save name" }));

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(
        (c) => String(c[0]) === "/api/sessions/sess_b/rename" && c[1]?.method === "PUT",
      );
      expect(call).toBeDefined();
      expect(JSON.parse(String(call![1]!.body))).toEqual({ title: "Renamed chat" });
    });
  });

  it("archives a session from the session menu and refreshes", async () => {
    const fetchMock = stubFetch({
      ...SESSIONS_ROUTE,
      "PUT /api/sessions/sess_b/archive": { ok: true, session_id: "sess_b", archived: true },
    });
    render(SessionsView);

    await waitFor(() => expect(screen.getByText("Second chat")).toBeInTheDocument());
    const row = screen.getByText("Second chat").closest("tr")!;
    await fireEvent.click(within(row as HTMLElement).getByRole("button", { name: /session actions/i }));
    await fireEvent.click(within(row as HTMLElement).getByRole("menuitem", { name: /^archive$/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/sessions/sess_b/archive",
        expect.objectContaining({ method: "PUT" }),
      );
    });
  });

  it("shows archived sessions on demand and unarchives from the menu", async () => {
    const archivedRow = {
      session_id: "sess_c",
      title: "Archived chat",
      status: "open",
      created_at: "2026-07-08T00:00:00Z",
      updated_at: "2026-07-08T00:01:00Z",
      turn_count: 3,
      pinned: false,
      tags: [],
      project_id: null,
      archived: true,
      archived_at: "2026-07-09T00:00:00Z",
    };
    const fetchMock = stubFetch({
      ...SESSIONS_ROUTE,
      "PUT /api/sessions/sess_c/unarchive": { ok: true, session_id: "sess_c", archived: false },
    });
    // The include_archived read returns the archived session too.
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method ?? "GET").toUpperCase();
      if (method === "GET" && url.startsWith("/api/sessions")) {
        const list = url.includes("include_archived=true")
          ? [...(SESSIONS_ROUTE["GET /api/sessions"] as unknown[]), archivedRow]
          : SESSIONS_ROUTE["GET /api/sessions"];
        return { ok: true, status: 200, json: async () => list } as Response;
      }
      if (method === "GET" && url.startsWith("/api/projects")) {
        return { ok: true, status: 200, json: async () => SESSIONS_ROUTE["GET /api/projects"] } as Response;
      }
      if (method === "PUT" && url === "/api/sessions/sess_c/unarchive") {
        return { ok: true, status: 200, json: async () => ({ ok: true, session_id: "sess_c", archived: false }) } as Response;
      }
      return { ok: false, status: 404, json: async () => ({ detail: {} }) } as Response;
    });
    render(SessionsView);

    await waitFor(() => expect(screen.getByText("Second chat")).toBeInTheDocument());
    expect(screen.queryByText("Archived chat")).toBeNull();

    await fireEvent.click(screen.getByLabelText("Show archived sessions"));
    await waitFor(() => expect(screen.getByText("Archived chat")).toBeInTheDocument());

    const row = screen.getByText("Archived chat").closest("tr")!;
    await fireEvent.click(within(row as HTMLElement).getByRole("button", { name: /session actions/i }));
    await fireEvent.click(within(row as HTMLElement).getByRole("menuitem", { name: /unarchive/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/sessions/sess_c/unarchive",
        expect.objectContaining({ method: "PUT" }),
      );
    });
  });

  it("links each conversation back into the chat surface", async () => {
    stubFetch(SESSIONS_ROUTE);
    render(SessionsView);

    await waitFor(() => expect(screen.getByText("Second chat")).toBeInTheDocument());
    const link = screen.getByRole("link", { name: "Open Second chat in chat" });
    expect(link).toHaveAttribute("href", "#/new-chat?session=sess_b");
  });

  it("links a session detail to its audit events and checkpoints", async () => {
    stubFetch({
      ...SESSIONS_ROUTE,
      "GET /api/sessions/sess_b": {
        session: SESSIONS_ROUTE["GET /api/sessions"][0],
        turns: [],
      },
    });
    render(SessionsView);

    await waitFor(() => expect(screen.getByText("Second chat")).toBeInTheDocument());
    await fireEvent.click(screen.getByText("Second chat"));

    expect(await screen.findByRole("link", { name: "View audit events" })).toHaveAttribute(
      "href",
      "#/activity?session=sess_b",
    );
    expect(screen.getByRole("link", { name: "View checkpoints" })).toHaveAttribute(
      "href",
      "#/checkpoints?session=sess_b",
    );
  });
});
