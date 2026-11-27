import { fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

import TurnMemoryProposals, { forgetHeldProposals } from "./TurnMemoryProposals.svelte";

const proposal = (over: Record<string, unknown> = {}) => ({
  candidate_id: "memcand_1",
  source_event_id: "evt_1",
  memory_type: "project",
  scope: "project",
  text: "My dentist is Dr. Okafor",
  sensitivity: "normal",
  confidence: 0.9,
  decision: "deferred",
  created_at: "2026-11-25T00:00:00Z",
  similar_memory: null,
  source_session_id: "sess_1",
  source_turn_id: "turn_1",
  source_role: "user",
  ...over,
});

function stub(list: unknown[], remembered: unknown[] = []) {
  const calls: { url: string; body?: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url: String(url), body: init?.body ? JSON.parse(String(init.body)) : undefined });
      const json = String(url).endsWith("/decision")
        ? { ok: true, candidate_id: "memcand_1", decision: "approved" }
        : String(url).includes("/api/memory/remembered")
          ? remembered
          : String(url).includes("/api/memory/mem_")
            ? { ok: true }
            : list;
      return { ok: true, status: 200, json: async () => json, headers: new Headers() } as Response;
    }),
  );
  return calls;
}

afterEach(() => {
  forgetHeldProposals();
  vi.unstubAllGlobals();
});

describe("TurnMemoryProposals (RU-10)", () => {
  it("offers only this answer's proposal, and Keep approves it", async () => {
    const calls = stub([proposal(), proposal({ candidate_id: "memcand_2", source_turn_id: "turn_2", text: "Other" })]);
    render(TurnMemoryProposals, { sessionId: "sess_1", turnId: "turn_1" });
    expect(await screen.findByText("“My dentist is Dr. Okafor”")).toBeInTheDocument();
    expect(screen.queryByText("“Other”")).toBeNull();
    await fireEvent.click(screen.getByRole("button", { name: "Keep" }));
    expect(await screen.findByText(/Kept\./)).toBeInTheDocument();
    const decision = calls.find((call) => call.url.endsWith("/memcand_1/decision"));
    expect(decision?.body).toMatchObject({ decision: "approved", expected_decision: "deferred" });
  });

  it("does not offer a sentence the model wrote", async () => {
    stub([proposal({ candidate_id: "memcand_9", source_role: "assistant", text: "Dr. Okafor is meticulous" })]);
    render(TurnMemoryProposals, { sessionId: "sess_1", turnId: "turn_1" });
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(screen.queryByText(/Dr. Okafor is meticulous/)).toBeNull();
  });

  it("Not this rejects it and the offer goes away", async () => {
    const calls = stub([proposal()]);
    render(TurnMemoryProposals, { sessionId: "sess_1", turnId: "turn_1" });
    await fireEvent.click(await screen.findByRole("button", { name: "Not this" }));
    await vi.waitFor(() => expect(screen.queryByRole("group")).toBeNull());
    expect(calls.find((call) => call.url.endsWith("/decision"))?.body).toMatchObject({ decision: "rejected" });
  });

  it("offers a lesson Raiker's own commands taught, named as a lesson (RU-12)", async () => {
    stub([
      proposal({
        source_role: "raiker_lesson",
        memory_type: "lesson",
        scope: "project:alpha",
        text: "In this project, `npm test -- --runInBand` works where `npm test` failed.",
      }),
    ]);
    render(TurnMemoryProposals, { sessionId: "sess_1", turnId: "turn_1" });
    expect(await screen.findByText(/Lesson for this project/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Keep" })).toBeInTheDocument();
  });

  it("shows what Raiker kept on its own, and Undo forgets it", async () => {
    const calls = stub([], [
      { memory_id: "mem_1", text: "I prefer green tea", memory_type: "preference", source_turn_id: "turn_1" },
      { memory_id: "mem_2", text: "Other turn", memory_type: "preference", source_turn_id: "turn_2" },
    ]);
    render(TurnMemoryProposals, { sessionId: "sess_1", turnId: "turn_1" });
    expect(await screen.findByText(/Remembered/)).toBeInTheDocument();
    expect(screen.queryByText("“Other turn”")).toBeNull();
    await fireEvent.click(screen.getByRole("button", { name: "Undo" }));
    expect(await screen.findByText("Forgotten.")).toBeInTheDocument();
    expect(calls.some((call) => call.url.includes("/api/memory/mem_1"))).toBe(true);
  });
});
