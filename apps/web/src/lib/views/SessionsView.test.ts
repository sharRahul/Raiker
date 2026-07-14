// Conversation organisation: pin/bookmark + bulk delete in the Sessions view.
// These are organizing actions only — they grant nothing. The view surfaces
// pinned sessions first and lets the user select and delete one or many.
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
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
    // "Pin session" (exact) targets the unpinned row only; the pinned row's
    // button is labelled "Unpin session".
    const pinBtn = screen.getByRole("button", { name: /^pin session$/i });
    await fireEvent.click(pinBtn);

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
    // Target the delete button inside the "Second chat" row (sess_b), since
    // pinned sessions sort first and would otherwise shift the index.
    const row = screen.getByText("Second chat").closest("tr")!;
    const delBtn = row.querySelector('button[aria-label="Delete session"]') as HTMLButtonElement;
    await fireEvent.click(delBtn);

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
    // Select both sessions.
    const checkboxes = screen.getAllByRole("checkbox");
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
});
