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

  it("browses every chat recent-first while the query is empty", async () => {
    const fetchMock = stubFetch({
      "GET /api/sessions": [
        { ...MATCH, session_id: "sess_older", title: "Older chat", updated_at: "2026-07-15T01:00:00Z" },
        { ...MATCH, session_id: "sess_newest", title: "Newest chat", updated_at: "2026-07-16T01:00:00Z" },
      ],
    });
    render(SearchChatView);
    expect(await screen.findByText("Newest chat")).toBeInTheDocument();
    const links = screen.getAllByRole("link", { name: /open conversation/i });
    expect(links[0]).toHaveAttribute("href", "#/new-chat?session=sess_newest");
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("origin=chat"))).toBe(true);
  });

  it("keeps untitled and empty chats browseable", async () => {
    stubFetch({ "GET /api/sessions": [{ ...MATCH, title: null, turn_count: 0 }] });
    render(SearchChatView);
    expect(await screen.findByText("Untitled chat")).toBeInTheDocument();
    expect(screen.getByText(/0 turns/)).toBeInTheDocument();
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
