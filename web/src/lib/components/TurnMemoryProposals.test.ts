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
  ...over,
});

function stub(list: unknown[]) {
  const calls: { url: string; body?: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url: String(url), body: init?.body ? JSON.parse(String(init.body)) : undefined });
      const json = String(url).endsWith("/decision") ? { ok: true, candidate_id: "memcand_1", decision: "approved" } : list;
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

  it("Not this rejects it and the offer goes away", async () => {
    const calls = stub([proposal()]);
    render(TurnMemoryProposals, { sessionId: "sess_1", turnId: "turn_1" });
    await fireEvent.click(await screen.findByRole("button", { name: "Not this" }));
    await vi.waitFor(() => expect(screen.queryByRole("group")).toBeNull());
    expect(calls.find((call) => call.url.endsWith("/decision"))?.body).toMatchObject({ decision: "rejected" });
  });
});
