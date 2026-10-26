/*
 * QUI-F03 — a goal noticed in conversation is offered once, under the answer,
 * and Not now is sent as the aim so it is never offered again.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import GoalSuggestion from "./GoalSuggestion.svelte";
import { stubFetch } from "../test-helpers";

afterEach(() => vi.unstubAllGlobals());

const OFFER = {
  aim_key: "abc",
  keywords: ["berlin", "marathon", "training"],
  title: "Adjust my Berlin marathon training plan",
  objective: "Adjust my Berlin marathon training plan",
  session_ids: ["sess_a"],
  session_titles: ["Marathon plan"],
};

describe("QUI-F03 goal suggestion", () => {
  it("offers to track an aim that came up elsewhere, naming where", async () => {
    stubFetch({ "GET /api/goals/suggestion": { session_id: "sess_b", suggestion: OFFER } });
    const ontrack = vi.fn();
    render(GoalSuggestion, { sessionId: "sess_b", revision: 1, ontrack });
    expect(await screen.findByText("This looks like an ongoing goal. Track it?")).toBeInTheDocument();
    expect(screen.getByText(/It also came up in “Marathon plan”\./)).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Track it" }));
    expect(ontrack).toHaveBeenCalledWith(OFFER);
  });

  it("sends Not now as the aim's keywords and goes away", async () => {
    const fetchMock = stubFetch({
      "GET /api/goals/suggestion": { session_id: "sess_b", suggestion: OFFER },
      "POST /api/goals/suggestion/dismiss": { ok: true, aim_key: "abc" },
    });
    render(GoalSuggestion, { sessionId: "sess_b", revision: 1, ontrack: vi.fn() });
    await fireEvent.click(await screen.findByRole("button", { name: "Not now" }));
    await waitFor(() => expect(screen.queryByText(/ongoing goal/)).not.toBeInTheDocument());
    const call = fetchMock.mock.calls.find(([url]) => String(url).includes("/suggestion/dismiss"));
    expect(JSON.parse(String((call?.[1] as RequestInit).body))).toEqual({ keywords: OFFER.keywords });
  });

  it("draws nothing when there is nothing to offer", async () => {
    const fetchMock = stubFetch({ "GET /api/goals/suggestion": { session_id: "sess_b", suggestion: null } });
    const { container } = render(GoalSuggestion, { sessionId: "sess_b", revision: 1, ontrack: vi.fn() });
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(container.querySelector(".goal-offer")).toBeNull();
  });
});
