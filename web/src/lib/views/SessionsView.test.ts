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

  // BUG-303 — pin, rename, archive, move and the tag editor were here. They
  // are how somebody organises the conversations they work in; this is the page
  // whose job is audit. The tests that asserted them now live beside the
  // controls, in SearchChatView.test.ts.
  it("offers none of the conversation-library controls", async () => {
    stubFetch(SESSIONS_ROUTE);
    render(SessionsView);

    await waitFor(() => expect(screen.getByText("Second chat")).toBeInTheDocument());
    const row = screen.getByText("Second chat").closest("tr")!;
    await fireEvent.click(
      within(row as HTMLElement).getByRole("button", { name: /session actions/i }),
    );
    for (const gone of [/^pin$/i, /^rename$/i, /^archive$/i, /move to project/i]) {
      expect(within(row as HTMLElement).queryByRole("menuitem", { name: gone })).toBeNull();
    }
    // Delete stays: it removes the audit record, which is this page's subject.
    expect(within(row as HTMLElement).getByRole("menuitem", { name: /delete/i })).toBeVisible();
    // And there is no tag editor anywhere on the page.
    expect(document.querySelector('input[aria-label^="Add a tag to"]')).toBeNull();
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

  it("renders a tag as a label rather than as something to edit", async () => {
    // BUG-303 — reading a tag is finding a record, which is this page's job.
    // Applying one is filing a conversation, which is not.
    stubFetch(SESSIONS_ROUTE);
    render(SessionsView);

    await waitFor(() => expect(screen.getByText("Second chat")).toBeInTheDocument());
    expect(screen.getByText("alpha")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /remove tag alpha/i })).toBeNull();
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

  it("can still read an archived session's record, and cannot file it", async () => {
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
    const fetchMock = stubFetch(SESSIONS_ROUTE);
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
      return { ok: false, status: 404, json: async () => ({ detail: {} }) } as Response;
    });
    render(SessionsView);

    await waitFor(() => expect(screen.getByText("Second chat")).toBeInTheDocument());
    expect(screen.queryByText("Archived chat")).toBeNull();

    await fireEvent.click(screen.getByLabelText("Show archived sessions"));
    await waitFor(() => expect(screen.getByText("Archived chat")).toBeInTheDocument());

    // BUG-303 — an archived conversation still has evidence to read, so the
    // inspector still reaches it. Restoring it is done on Threads, where
    // archiving it was.
    const row = screen.getByText("Archived chat").closest("tr")!;
    await fireEvent.click(
      within(row as HTMLElement).getByRole("button", { name: /session actions/i }),
    );
    expect(within(row as HTMLElement).queryByRole("menuitem", { name: /unarchive/i })).toBeNull();
    expect(
      within(row as HTMLElement).getByRole("menuitem", { name: /organise in threads/i }),
    ).toHaveAttribute("href", "#/search-chat");
  });

  // REM-SESSIONS — the row used to carry an "Open" link straight into Chat,
  // which made the evidence inspector a second place to resume a conversation.
  // Resuming lives in Threads; the row here opens the record.
  it("offers no per-row way to resume a conversation", async () => {
    stubFetch(SESSIONS_ROUTE);
    render(SessionsView);

    await waitFor(() => expect(screen.getByText("Second chat")).toBeInTheDocument());
    expect(screen.queryByRole("link", { name: "Open Second chat in chat" })).toBeNull();
    expect(screen.getByRole("link", { name: "Threads" })).toHaveAttribute(
      "href",
      "#/search-chat",
    );
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

  it("cross-links a session detail to every related work surface", async () => {
    stubFetch({
      ...SESSIONS_ROUTE,
      "GET /api/sessions/sess_b": {
        session: SESSIONS_ROUTE["GET /api/sessions"][0],
        turns: [],
      },
    });
    render(SessionsView);

    await fireEvent.click(await screen.findByText("Second chat"));

    // REM-SESSIONS / REM-THREAD-03 — one way back, named for the surface this
    // conversation was done on, rather than the two side-by-side guesses
    // ("Open in chat" / "Open in Build") every session used to be offered.
    expect(screen.getByRole("link", { name: "Resume in Chat" })).toHaveAttribute(
      "href",
      "#/new-chat?session=sess_b",
    );
    expect(screen.queryByRole("link", { name: "Open in chat" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Open in Build" })).toBeNull();
    expect(screen.getByRole("link", { name: "View session tasks" })).toHaveAttribute(
      "href",
      "#/tasks?session=sess_b",
    );
    expect(screen.getByRole("link", { name: "View session approvals" })).toHaveAttribute(
      "href",
      "#/approvals?session=sess_b",
    );
  });

  it("opens the session named in a session deep link", async () => {
    stubFetch({
      ...SESSIONS_ROUTE,
      "GET /api/sessions/sess_b": {
        session: SESSIONS_ROUTE["GET /api/sessions"][0],
        turns: [],
      },
    });
    render(SessionsView, { sessionId: "sess_b" });

    expect(await screen.findByRole("heading", { name: "Second chat" })).toBeInTheDocument();
  });
});

describe("SessionsView renders a reopened turn as the parts it declared", () => {
  // BUG-300 — Sessions reads a stored turn, not a live response, so it printed
  // the raw `raiker:table` fence and its JSON where the conversation showed a
  // table. The parts arrive already split by the runtime.
  const ANSWER =
    'Spending so far.\n\n```raiker:table\n{"caption":"Cost by provider",' +
    '"columns":["Provider","Spend"],"rows":[["Anthropic","$4.10"]]}\n```\n';

  const withTurn = (contentParts: unknown[]) => ({
    ...SESSIONS_ROUTE,
    "GET /api/sessions/sess_b": {
      session: SESSIONS_ROUTE["GET /api/sessions"][0],
      turns: [
        {
          turn_id: "turn_1",
          session_id: "sess_b",
          turn_type: "prompt",
          status: "completed",
          prompt_text: "How much did we spend?",
          created_at: "2026-07-10T00:00:00Z",
          completed_at: "2026-07-10T00:00:05Z",
          summary: ANSWER,
          content_parts: contentParts,
        },
      ],
    },
    "GET /api/turns/turn_1": {
      turn: {
        turn_id: "turn_1",
        session_id: "sess_b",
        turn_type: "prompt",
        status: "completed",
        prompt_text: "How much did we spend?",
        created_at: "2026-07-10T00:00:00Z",
        completed_at: "2026-07-10T00:00:05Z",
        summary: ANSWER,
        content_parts: contentParts,
      },
      events: [],
    },
  });

  const openTheTurn = async () => {
    render(SessionsView);
    await fireEvent.click(await screen.findByText("Second chat"));
    await fireEvent.click(await screen.findByText("How much did we spend?"));
  };

  it("shows a declared table as a table rather than as its fence", async () => {
    stubFetch(
      withTurn([
        { type: "text", text: "Spending so far.\n\n" },
        {
          type: "table",
          data: {
            caption: "Cost by provider",
            columns: ["Provider", "Spend"],
            rows: [["Anthropic", "$4.10"]],
          },
        },
      ]),
    );
    await openTheTurn();

    // Scoped to the turn inspector: the conversation list above it is a table
    // too, and this is about the answer rather than the page.
    const table = await screen.findByRole("table", { name: /Cost by provider/i });
    expect(within(table).getByRole("columnheader", { name: /Provider/ })).toBeInTheDocument();
    expect(within(table).getByText("$4.10")).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("raiker:table");
  });

  it("falls back to the stored text when the answer declared nothing", async () => {
    stubFetch(withTurn([]));
    await openTheTurn();

    // No parts, so no typed rendering — the stored string is shown as it
    // always was, fence and all, because that is what the record holds.
    await waitFor(() =>
      expect(screen.queryByRole("table", { name: /Cost by provider/i })).not.toBeInTheDocument(),
    );
    expect(document.body.textContent).toContain("raiker:table");
  });
});
