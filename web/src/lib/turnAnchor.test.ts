// MEM-08 — a turn coordinate you can open.
//
// `conversation_search` returns `session_id` and `turn_id`, chat search returns
// `match_turn_id`, and every checkpoint names the turn it was taken at. All
// three coordinates existed and none of them was a link, so verifying a recalled
// claim — "we settled this in March" — meant opening the conversation at the top
// and scrolling until you recognised it.
//
// These assert the two halves that make one clickable: the link a surface
// builds, and the landing that spends it.
import { describe, expect, it, vi } from "vitest";
import { conversationLink, forgetTurnInRoute, revealTurn } from "./turnAnchor";

describe("conversationLink", () => {
  it("carries the exchange when the caller knows which one matched", () => {
    expect(conversationLink("new-chat", "sess_1", "turn_9")).toBe(
      "#/new-chat?session=sess_1&turn=turn_9",
    );
  });

  it("opens the conversation when no exchange is named", () => {
    expect(conversationLink("new-chat", "sess_1")).toBe("#/new-chat?session=sess_1");
    expect(conversationLink("build", "sess_1", "")).toBe("#/build?session=sess_1");
    expect(conversationLink("build", "sess_1", null)).toBe("#/build?session=sess_1");
  });

  it("escapes a coordinate rather than letting it shape the query", () => {
    expect(conversationLink("new-chat", "sess a&b", "turn=1")).toBe(
      "#/new-chat?session=sess+a%26b&turn=turn%3D1",
    );
  });
});

describe("revealTurn", () => {
  function transcript(...turnIds: string[]): HTMLElement {
    const root = document.createElement("div");
    for (const id of turnIds) {
      const turn = document.createElement("div");
      turn.className = "turn";
      turn.dataset.turnId = id;
      root.append(turn);
    }
    return root;
  }

  it("marks the anchored exchange and lets go of the mark", () => {
    vi.useFakeTimers();
    const root = transcript("turn_1", "turn_2");
    expect(revealTurn(root, "turn_2")).toBe(true);

    const marked = root.querySelector('[data-turn-id="turn_2"]');
    expect(marked?.classList.contains("turn-anchored")).toBe(true);
    // A shared link says "look here"; it does not put the conversation into a
    // permanent highlighted state.
    vi.advanceTimersByTime(3000);
    expect(marked?.classList.contains("turn-anchored")).toBe(false);
    vi.useRealTimers();
  });

  it("reports a coordinate this conversation does not hold", () => {
    expect(revealTurn(transcript("turn_1"), "turn_404")).toBe(false);
    expect(revealTurn(undefined, "turn_1")).toBe(false);
    expect(revealTurn(transcript("turn_1"), "")).toBe(false);
  });
});

describe("forgetTurnInRoute", () => {
  it("spends the anchor and keeps everything else in the address", () => {
    window.history.replaceState(null, "", "#/new-chat?session=sess_1&turn=turn_9");
    forgetTurnInRoute();
    expect(window.location.hash).toBe("#/new-chat?session=sess_1");
  });

  it("leaves an address that carries no anchor untouched", () => {
    window.history.replaceState(null, "", "#/new-chat?session=sess_1");
    forgetTurnInRoute();
    expect(window.location.hash).toBe("#/new-chat?session=sess_1");
  });
});
