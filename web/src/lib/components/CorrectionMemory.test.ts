import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

import CorrectionMemory from "./CorrectionMemory.svelte";
import { stubFetch } from "../test-helpers";

afterEach(() => vi.unstubAllGlobals());

describe("QUI-F20 Remember this correction", () => {
  it("files the owner's words as a proposal and approves it on Save", async () => {
    const fetchMock = stubFetch({
      "POST /api/memory/proposals": { ok: true, candidate_id: "memcand_1", text: "Anna prefers short replies." },
      "POST /api/memory/proposals/memcand_1/decision": { ok: true, candidate_id: "memcand_1", decision: "approved", memory_id: "mem_1" },
    });
    render(CorrectionMemory, { sessionId: "s1", turnId: "t1", text: "Anna prefers short replies." });
    expect(screen.getByText("Anna prefers short replies?")).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(screen.getByText(/Remembered/)).toBeInTheDocument());
    const posted = fetchMock.mock.calls.filter(([, init]) => (init as RequestInit | undefined)?.method === "POST").map(([url]) => String(url));
    expect(posted).toEqual(["/api/memory/proposals", "/api/memory/proposals/memcand_1/decision"]);
  });

  it("keeps nothing on Dismiss", async () => {
    const fetchMock = stubFetch({});
    render(CorrectionMemory, { sessionId: "s1", turnId: "t1", text: "Use metric units." });
    await fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByRole("group", { name: "Remember this correction" })).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
