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

describe("SearchChatView", () => {
  // A single-turn conversation read "1 turns" in the FTS5 evidence sweep of
  // 2026-08-17. Small, but it is on the row a reader scans to decide whether a
  // hit is worth opening.
  it.each([
    [1, "1 turn ·"],
    [4, "4 turns ·"],
  ])("counts %i turn(s) in the singular or plural it needs", async (count, expected) => {
    stubFetch({ "GET /api/chat-search": [{ ...MATCH, turn_count: count }] });
    render(SearchChatView);
    await fireEvent.input(screen.getByLabelText("Search chat history"), {
      target: { value: "release" },
    });
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
      "GET /api/work-threads": [
        thread({ session_id: "sess_newest", title: "Newest chat" }),
        thread({
          session_id: "sess_older",
          title: "Older chat",
          updated_at: "2026-07-15T01:00:00Z",
        }),
      ],
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
      "GET /api/work-threads": [
        thread({ session_id: "sess_chat", title: "Release planning" }),
        thread({
          session_id: "sess_routine",
          title: "Overnight research",
          kind: "routine",
          cadence: "daily",
          task_id: "task_1",
        }),
      ],
    });
    render(SearchChatView);

    expect(await screen.findByText("Overnight research")).toBeInTheDocument();
    expect(screen.getByText("Runs daily")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /overnight research/i })).toHaveAttribute(
      "href",
      "#/new-chat?session=sess_routine",
    );
  });

  it("narrows the board to routines, and to one project", async () => {
    stubFetch({
      "GET /api/work-threads": [
        thread({
          session_id: "sess_chat",
          title: "Release planning",
          project_id: "proj_a",
          project_name: "Alpha",
        }),
        thread({
          session_id: "sess_routine",
          title: "Overnight research",
          kind: "routine",
          cadence: "daily",
        }),
      ],
    });
    render(SearchChatView);

    await screen.findByText("Release planning");
    await fireEvent.click(screen.getByRole("button", { name: "Routines" }));
    expect(screen.queryByText("Release planning")).toBeNull();
    expect(screen.getByText("Overnight research")).toBeInTheDocument();

    await fireEvent.click(screen.getByRole("button", { name: "All" }));
    // The cross-project view the gap named: a project the owner can filter to,
    // built from the threads that are actually in one.
    await fireEvent.change(screen.getByLabelText("Filter by project"), {
      target: { value: "proj_a" },
    });
    expect(screen.getByText("Release planning")).toBeInTheDocument();
    expect(screen.queryByText("Overnight research")).toBeNull();
  });

  it("says what a thread is blocked on rather than leaving it to be discovered", async () => {
    stubFetch({
      "GET /api/work-threads": [
        thread({
          session_id: "sess_routine",
          title: "Overnight research",
          kind: "routine",
          waiting_on: "Waiting for your approval",
        }),
      ],
    });
    render(SearchChatView);
    expect(await screen.findByText("Waiting for your approval")).toBeInTheDocument();
  });

  it("says so plainly when nothing is going yet", async () => {
    stubFetch({ "GET /api/work-threads": [] });
    render(SearchChatView);
    expect(await screen.findByText("Nothing going yet")).toBeInTheDocument();
  });

  it("links each match back into the conversation", async () => {
    stubFetch({ "GET /api/chat-search": [MATCH] });
    render(SearchChatView);
    await fireEvent.input(screen.getByLabelText("Search chat history"), {
      target: { value: "release" },
    });
    await waitFor(() => expect(screen.getByText("Release planning")).toBeInTheDocument());
    const link = screen.getByRole("link", { name: /release planning/i });
    expect(link).toHaveAttribute("href", "#/new-chat?session=sess_hit1");
  });

  // MEM-08 — the coordinate the search already knew. Before this, a hit in turn
  // 180 of a long conversation opened at turn 1 and the reader scrolled.
  it("opens the exchange that matched when the search names one", async () => {
    stubFetch({ "GET /api/chat-search": [{ ...MATCH, match_turn_id: "turn_180" }] });
    render(SearchChatView);
    await fireEvent.input(screen.getByLabelText("Search chat history"), {
      target: { value: "release" },
    });
    await waitFor(() => expect(screen.getByText("Release planning")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: /release planning/i })).toHaveAttribute(
      "href",
      "#/new-chat?session=sess_hit1&turn=turn_180",
    );
    expect(screen.getByText(/Open the match/)).toBeInTheDocument();
  });

  it("shows a route-level error state when search fails", async () => {
    stubFetch({});
    render(SearchChatView);
    await fireEvent.input(screen.getByLabelText("Search chat history"), {
      target: { value: "release" },
    });
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/couldn't search chats/i);
    expect(alert).toHaveTextContent(/unavailable \(404\)/i);
  });
});
