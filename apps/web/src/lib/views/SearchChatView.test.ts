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
  it("invites a search while the query is empty", async () => {
    stubFetch({});
    render(SearchChatView);
    expect(await screen.findByText("Search your chats")).toBeInTheDocument();
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
