// B17 / C13 — the controls over a turn that is already running.
//
// What matters here is not that two buttons render. It is that the control is
// honest about what it does: it never claims to have stopped anything, it says
// the stop is a request applied at a safe boundary, it refuses to pretend it can
// act before the conversation has an id, and a steer is described as reaching
// the turn rather than as a new message.
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import TurnControl from "./TurnControl.svelte";
import { stubFetch } from "../test-helpers";

afterEach(() => vi.unstubAllGlobals());

describe("TurnControl", () => {
  it("cannot act until the conversation has an id, and says so", () => {
    render(TurnControl, { sessionId: null });
    expect(screen.getByRole("button", { name: "Stop this turn" })).toBeDisabled();
    expect(screen.getByPlaceholderText("Starting…")).toBeDisabled();
  });

  it("asks for a safe-boundary stop and reports it as requested, not done", async () => {
    const fetchMock = stubFetch({
      "POST /api/interrupts": { applied: [], safe_boundary: true, turn_control: { action: "stop", queued: 0 } },
    });
    render(TurnControl, { sessionId: "sess_1" });
    await fireEvent.click(screen.getByRole("button", { name: "Stop this turn" }));

    await waitFor(() => expect(screen.getByText(/Stop requested/)).toBeInTheDocument());
    expect(screen.getByText(/ends at its next safe boundary/)).toBeInTheDocument();
    const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body));
    expect(body).toMatchObject({ session_id: "sess_1", action_type: "cancel", all: true });
  });

  it("queues the owner's words for the running turn and counts them", async () => {
    const fetchMock = stubFetch({
      "POST /api/interrupts": { applied: [], safe_boundary: true, turn_control: { action: "steer", queued: 1 } },
    });
    render(TurnControl, { sessionId: "sess_1" });
    await fireEvent.input(screen.getByLabelText("Add to this turn"), {
      target: { value: "use the changelog instead" },
    });
    await fireEvent.click(screen.getByRole("button", { name: /Steer/ }));

    await waitFor(() =>
      expect(screen.getByText(/1 instruction queued for this turn/)).toBeInTheDocument(),
    );
    const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body));
    expect(body).toMatchObject({ action_type: "steer", steer_text: "use the changelog instead" });
    // The field clears, so the same instruction cannot be sent twice by accident.
    expect(screen.getByLabelText("Add to this turn")).toHaveValue("");
  });

  it("says when the request itself failed instead of looking successful", async () => {
    stubFetch({});
    render(TurnControl, { sessionId: "sess_1" });
    await fireEvent.click(screen.getByRole("button", { name: "Stop this turn" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/Stop failed/));
    expect(screen.queryByText(/Stop requested/)).not.toBeInTheDocument();
  });
});
