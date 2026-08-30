// MEM-08, at the surface: a link that names an exchange lands on it.
//
// `turnAnchor.test.ts` holds the helpers; this holds the thing an owner does.
// A search result, a citation, a checkpoint, or a link somebody was sent opens
// the conversation *at* the exchange, marks it, and spends the anchor so a
// later reload shows the conversation as it is rather than replaying a
// highlight. A coordinate this conversation does not hold says so, because the
// alternative — landing silently at the top — is indistinguishable from the
// bug this closes.
import { render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { stubFetch } from "../test-helpers";
import { resetModels } from "../models.svelte";
import ChatView from "./ChatView.svelte";

afterEach(() => {
  vi.unstubAllGlobals();
  resetModels();
  window.location.hash = "";
});

function turn(turnId: string, prompt: string) {
  return {
    turn_id: turnId,
    session_id: "sess_1",
    turn_type: "chat",
    status: "completed",
    prompt_text: prompt,
    created_at: "2026-03-12T09:00:00Z",
    completed_at: "2026-03-12T09:00:04Z",
    summary: `answer to ${prompt}`,
    reasoning: null,
    reasoning_chars: 0,
  };
}

function routes(overrides: Record<string, unknown> = {}) {
  return {
    "GET /api/models": { profiles: [], chat_profiles: [] },
    "GET /api/tasks": [],
    "GET /api/sessions/sess_1": {
      session: {
        session_id: "sess_1",
        title: "Key rotation",
        status: "active",
        created_at: "2026-03-12T09:00:00Z",
        updated_at: "2026-03-12T09:10:00Z",
        turn_count: 2,
        pinned: false,
        tags: [],
        project_id: null,
        archived: false,
        archived_at: null,
      },
      turns: [turn("turn_1", "How often do we rotate?"), turn("turn_2", "And who approves it?")],
    },
    ...overrides,
  };
}

describe("landing on an anchored exchange", () => {
  it("marks the exchange the link named and spends the anchor", async () => {
    stubFetch(routes());
    window.history.replaceState(null, "", "#/new-chat?session=sess_1&turn=turn_2");
    const { container } = render(ChatView, { sessionId: "sess_1", anchoredTurnId: "turn_2" });

    await screen.findByText("And who approves it?");
    await waitFor(() =>
      expect(container.querySelector('[data-turn-id="turn_2"].turn-anchored')).not.toBeNull(),
    );
    // The other exchange is untouched — the mark names one turn, not the page.
    expect(container.querySelector('[data-turn-id="turn_1"].turn-anchored')).toBeNull();
    // And a reload of this address opens the conversation, not the highlight.
    await waitFor(() => expect(window.location.hash).toBe("#/new-chat?session=sess_1"));
  });

  it("says a coordinate is not in this conversation rather than landing silently", async () => {
    stubFetch(routes());
    window.history.replaceState(null, "", "#/new-chat?session=sess_1&turn=turn_404");
    render(ChatView, { sessionId: "sess_1", anchoredTurnId: "turn_404" });

    expect(
      await screen.findByText("That exchange is not in this conversation."),
    ).toBeInTheDocument();
  });

  it("opens where the conversation left off when no exchange is named", async () => {
    stubFetch(routes());
    const { container } = render(ChatView, { sessionId: "sess_1" });

    await screen.findByText("And who approves it?");
    expect(container.querySelector(".turn-anchored")).toBeNull();
    expect(screen.queryByText("That exchange is not in this conversation.")).toBeNull();
  });

  // Two search results in the *same* conversation. Nothing reloads — the
  // session id has not changed — so landing only from the history load would
  // have silently ignored the second link and left the reader on the first
  // exchange, which is the bug this whole entry is about.
  it("honours a second link into a conversation that is already open", async () => {
    stubFetch(routes());
    window.history.replaceState(null, "", "#/new-chat?session=sess_1&turn=turn_2");
    const { container, rerender } = render(ChatView, {
      sessionId: "sess_1",
      anchoredTurnId: "turn_2",
    });

    await waitFor(() =>
      expect(container.querySelector('[data-turn-id="turn_2"].turn-anchored')).not.toBeNull(),
    );

    await rerender({ sessionId: "sess_1", anchoredTurnId: "turn_1" });
    await waitFor(() =>
      expect(container.querySelector('[data-turn-id="turn_1"].turn-anchored')).not.toBeNull(),
    );
  });
});
