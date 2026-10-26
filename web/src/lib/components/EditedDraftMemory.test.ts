/*
 * QUI-F20 — a correction made by editing Raiker's draft is offered as memory in
 * the owner's own words, never guessed from the diff.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import EditedDraftMemory from "./EditedDraftMemory.svelte";
import { stubFetch } from "../test-helpers";

afterEach(() => vi.unstubAllGlobals());

describe("QUI-F20 edited draft", () => {
  it("files the owner's words as a memory through the proposal path", async () => {
    const fetchMock = stubFetch({
      "POST /api/memory/proposals": { candidate_id: "cand_1", text: "Keep commit messages short." },
      "POST /api/memory/proposals/cand_1/decision": { ok: true },
    });
    render(EditedDraftMemory, { sessionId: "sess_1" });
    const save = screen.getByRole("button", { name: "Save" });
    expect(save).toBeDisabled();
    await fireEvent.input(screen.getByLabelText(/Anything to remember for next time/), {
      target: { value: "Keep commit messages short." },
    });
    await fireEvent.click(save);
    expect(await screen.findByText(/Remembered\./)).toBeInTheDocument();
    const proposal = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/api/memory/proposals"));
    expect(JSON.parse(String((proposal?.[1] as RequestInit).body))).toEqual({
      text: "Keep commit messages short.",
      session_id: "sess_1",
    });
  });

  it("keeps nothing on Dismiss", async () => {
    const fetchMock = stubFetch({});
    const ondone = vi.fn();
    render(EditedDraftMemory, { sessionId: "sess_1", ondone });
    await fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    await waitFor(() => expect(ondone).toHaveBeenCalled());
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
