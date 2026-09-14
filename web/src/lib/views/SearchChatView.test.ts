// Route-level coverage for Search Chat: state grammar (prompt/loading/error)
// plus the preserved resume link into a matched conversation.
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import SearchChatView from "./SearchChatView.svelte";
import { stubFetch } from "../test-helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const MATCH = {
  session_id: "sess_hit1",
  title: "Release planning",
  status: "active",
  created_at: "2026-07-15T00:00:00Z",
  updated_at: "2026-07-15T01:00:00Z",
  turn_count: 4,
  pinned: false,
  tags: [],
  project_id: null,
  archived: false,
  archived_at: null,
};

function thread(partial: Record<string, unknown> = {}) {
  return {
    session_id: "sess_1",
    title: "Release planning",
    kind: "chat",
    updated_at: "2026-07-16T01:00:00Z",
    turn_count: 4,
    project_id: null,
    project_name: null,
    ...partial,
  };
}

/**
 * NEW-THREAD-01 — the board reads the server index now, so every case that used
 * to stub a bare array of threads stubs the page it comes in.
 *
 * `projects` and `kinds` are the server's facets, computed over everything that
 * matched rather than over the rows on this page — which is the finding, so the
 * helper derives them the way the server does and individual cases override
 * them where the distinction is what is under test.
 */
function pageOf(
  threads: Array<Record<string, unknown>>,
  overrides: Record<string, unknown> = {},
) {
  const projects = [
    ...new Map(
      threads
        .filter((t) => t.project_id)
        .map((t) => [String(t.project_id), String(t.project_name ?? t.project_id)]),
    ),
  ].map(([value, label]) => ({
    value,
    label,
    count: threads.filter((t) => t.project_id === value).length,
  }));
  const kinds = [...new Set(threads.map((t) => String(t.kind)))].map((value) => ({
    value,
    label: value,
    count: threads.filter((t) => t.kind === value).length,
  }));
  return {
    threads,
    next_cursor: null,
    total: threads.length,
    projects,
    kinds,
    scan_truncated: false,
    ...overrides,
  };
}

describe("SearchChatView", () => {
  // A single-turn conversation read "1 turns" in the FTS5 evidence sweep of
  // 2026-08-17. Small, but it is on the row a reader scans to decide whether a
  // hit is worth opening.
  it.each([
    [1, "1 turn ·"],
    [4, "4 turns ·"],
  ])("counts %i turn(s) in the singular or plural it needs", async (count, expected) => {
    stubFetch({
      "GET /api/chat-search": [{ ...MATCH, turn_count: count }],
      "GET /api/work-threads/page": pageOf([]),
    });
    render(SearchChatView);
    await fireEvent.input(screen.getByLabelText("Search chat history"), {
      target: { value: "release" },
    });
    await fireEvent.click(await screen.findByRole("button", { name: "Search message text" }));
    await waitFor(() =>
      expect(screen.getByText(new RegExp(expected.replace("·", "\\u00b7")))).toBeInTheDocument(),
    );
  });

  // C18 — with an empty box this page stopped being a search and became the
  // board: what the owner is working on, across chats, projects and routines.
  // The routine threads are the half that had no reader at all before C11 gave
  // each task a conversation.
  it("lists every thread of work recent-first while the query is empty", async () => {
    const fetchMock = stubFetch({
      "GET /api/work-threads/page": pageOf([
        thread({ session_id: "sess_newest", title: "Newest chat" }),
        thread({
          session_id: "sess_older",
          title: "Older chat",
          updated_at: "2026-07-15T01:00:00Z",
        }),
      ]),
    });
    render(SearchChatView);
    expect(await screen.findByText("Newest chat")).toBeInTheDocument();
    const links = screen.getAllByRole("link", { name: /newest chat/i });
    expect(links[0]).toHaveAttribute("href", "#/new-chat?session=sess_newest");
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/api/work-threads"))).toBe(
      true,
    );
  });

  it("shows a routine's own thread beside the owner's chats", async () => {
    stubFetch({
      "GET /api/work-threads/page": pageOf([
        thread({ session_id: "sess_chat", title: "Release planning" }),
        thread({
          session_id: "sess_routine",
          title: "Overnight research",
          kind: "routine",
          cadence: "daily",
          task_id: "task_1",
        }),
      ]),
    });
    render(SearchChatView);

    expect(await screen.findByText("Overnight research")).toBeInTheDocument();
    expect(screen.getByText("Runs daily")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /overnight research/i })).toHaveAttribute(
      "href",
      "#/new-chat?session=sess_routine",
    );
  });

  // NEW-THREAD-01 — filtering is the index's job now, so what this asserts is
  // that the page asks the right question rather than sieving what arrived.
  // Sieving is exactly what stopped a project outside the first page from being
  // offered at all.
  it("asks the index for the narrowed question", async () => {
    const fetchMock = stubFetch({
      "GET /api/work-threads/page": pageOf([
        thread({
          session_id: "sess_chat",
          title: "Release planning",
          project_id: "proj_a",
          project_name: "Alpha",
        }),
        thread({ session_id: "sess_routine", title: "Overnight research", kind: "routine" }),
      ]),
    });
    render(SearchChatView);
    await screen.findByText("Release planning");

    await fireEvent.click(screen.getByRole("button", { name: "Routines" }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) => String(url).includes("kind=routine")),
      ).toBe(true),
    );

    await fireEvent.change(screen.getByLabelText("Filter by project"), {
      target: { value: "proj_a" },
    });
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) => String(url).includes("project_id=proj_a")),
      ).toBe(true),
    );
  });

  it("offers every project the index has work in, not only this page's", async () => {
    // The finding itself. A project whose newest thread is a hundred rows down
    // used to be missing from the filter entirely, which on screen is
    // indistinguishable from a project with nothing in it.
    stubFetch({
      "GET /api/work-threads/page": pageOf(
        [thread({ session_id: "sess_1", title: "Release planning" })],
        {
          total: 140,
          projects: [
            { value: "proj_a", label: "Alpha", count: 130 },
            { value: "proj_old", label: "Last quarter", count: 3 },
          ],
          next_cursor: "cursor-2",
        },
      ),
    });
    render(SearchChatView);

    const filter = await screen.findByLabelText("Filter by project");
    expect(filter).toHaveTextContent("Last quarter (3)");
    // And the page says it is a window rather than the inventory.
    expect(screen.getByText(/Showing 1 of 140 threads/)).toBeInTheDocument();
  });

  it("keeps the filters, and the project, while the owner types", async () => {
    // Typing used to hide the filters and call an unscoped search, so narrowing
    // something down silently widened it.
    const fetchMock = stubFetch({
      "GET /api/work-threads/page": pageOf([
        thread({
          session_id: "sess_chat",
          title: "Release planning",
          project_id: "proj_a",
          project_name: "Alpha",
        }),
      ]),
    });
    render(SearchChatView);
    await screen.findByText("Release planning");
    await fireEvent.change(screen.getByLabelText("Filter by project"), {
      target: { value: "proj_a" },
    });

    await fireEvent.input(screen.getByLabelText("Search chat history"), {
      target: { value: "release" },
    });

    // Still on screen…
    await waitFor(() => expect(screen.getByLabelText("Filter by project")).toBeInTheDocument());
    // …and still applied.
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([url]) =>
            String(url).includes("project_id=proj_a") && String(url).includes("query=release"),
        ),
      ).toBe(true),
    );
  });

  it("loads the next page instead of pretending there is none", async () => {
    let call = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
        if (!url.includes("/api/work-threads/page")) {
          return { ok: false, status: 404, json: async () => ({}) } as Response;
        }
        call += 1;
        const body =
          call === 1
            ? pageOf([thread({ session_id: "sess_1", title: "First page" })], {
                total: 2,
                next_cursor: "cursor-2",
              })
            : pageOf([thread({ session_id: "sess_2", title: "Second page" })], { total: 2 });
        return { ok: true, status: 200, json: async () => body } as Response;
      }),
    );
    render(SearchChatView);

    expect(await screen.findByText("First page")).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Load more" }));

    // Appended, not replaced: a cursor page continues one answer.
    expect(await screen.findByText("Second page")).toBeInTheDocument();
    expect(screen.getByText("First page")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Load more" })).toBeNull();
  });

  it("says what a thread is blocked on rather than leaving it to be discovered", async () => {
    stubFetch({
      "GET /api/work-threads/page": pageOf([
        thread({
          session_id: "sess_routine",
          title: "Overnight research",
          kind: "routine",
          waiting_on: "Waiting for your approval",
        }),
      ]),
    });
    render(SearchChatView);
    expect(await screen.findByText("Waiting for your approval")).toBeInTheDocument();
  });

  it("says so plainly when nothing is going yet", async () => {
    stubFetch({ "GET /api/work-threads/page": pageOf([]) });
    render(SearchChatView);
    expect(await screen.findByText("Nothing going yet")).toBeInTheDocument();
  });

  it("links each match back into the conversation", async () => {
    stubFetch({ "GET /api/chat-search": [MATCH], "GET /api/work-threads/page": pageOf([]) });
    render(SearchChatView);
    await fireEvent.input(screen.getByLabelText("Search chat history"), {
      target: { value: "release" },
    });
    await fireEvent.click(await screen.findByRole("button", { name: "Search message text" }));
    await waitFor(() => expect(screen.getByText("Release planning")).toBeInTheDocument());
    const link = screen.getByRole("link", { name: /release planning/i });
    expect(link).toHaveAttribute("href", "#/new-chat?session=sess_hit1");
  });

  // MEM-08 — the coordinate the search already knew. Before this, a hit in turn
  // 180 of a long conversation opened at turn 1 and the reader scrolled.
  it("opens the exchange that matched when the search names one", async () => {
    stubFetch({
      "GET /api/chat-search": [{ ...MATCH, match_turn_id: "turn_180" }],
      "GET /api/work-threads/page": pageOf([]),
    });
    render(SearchChatView);
    await fireEvent.input(screen.getByLabelText("Search chat history"), {
      target: { value: "release" },
    });
    await fireEvent.click(await screen.findByRole("button", { name: "Search message text" }));
    await waitFor(() => expect(screen.getByText("Release planning")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: /release planning/i })).toHaveAttribute(
      "href",
      "#/new-chat?session=sess_hit1&turn=turn_180",
    );
    expect(screen.getByText(/Open the match/)).toBeInTheDocument();
  });

  it("shows a route-level error state when the index fails", async () => {
    stubFetch({});
    render(SearchChatView);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/couldn't load your threads/i);
    expect(alert).toHaveTextContent(/unavailable \(404\)/i);
  });
});
