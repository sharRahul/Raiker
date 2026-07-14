// Reliable memory controls (backlog item 3): the Memory view lists approved
// memories with governance metadata, supports pin/bookmark, forget, and an
// incognito opt-out toggle.
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import MemoryView from "./MemoryView.svelte";
import { stubFetch } from "../test-helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("MemoryView", () => {
  it("lists memories with provenance and sensitivity", async () => {
    stubFetch({
      "GET /api/memory": [
        {
          memory_id: "mem_1",
          text: "The user prefers tabs over spaces.",
          scope: "project:alpha",
          sensitivity: "normal",
          memory_type: "project",
          created_at: "2026-07-12T00:00:00Z",
          tags: ["style"],
          source: "agent",
          provenance: { source_session_id: "sess_x" },
          confidence: 0.9,
          trust_score: 0.8,
          retention: "until_forget",
          approval_state: "approved",
          pinned: false,
        },
      ],
      "GET /api/memory/settings": { incognito: false },
    });
    render(MemoryView);

    await waitFor(() =>
      expect(screen.getByText("The user prefers tabs over spaces.")).toBeInTheDocument(),
    );
    expect(screen.getByText("project:alpha")).toBeInTheDocument();
    expect(screen.getByText(/sensitivity: normal/i)).toBeInTheDocument();
    expect(screen.getByText(/confidence: 0.90/i)).toBeInTheDocument();
  });

  it("shows an empty state when there are no memories", async () => {
    stubFetch({
      "GET /api/memory": [],
      "GET /api/memory/settings": { incognito: false },
    });
    render(MemoryView);

    await waitFor(() =>
      expect(screen.getByText(/no approved memories yet/i)).toBeInTheDocument(),
    );
  });

  it("toggles incognito and reflects the new state", async () => {
    const fetchMock = stubFetch({
      "GET /api/memory": [],
      "GET /api/memory/settings": { incognito: false },
      "PUT /api/memory/incognito": { ok: true, incognito: true },
    });
    render(MemoryView);

    await waitFor(() => expect(screen.getByRole("checkbox")).not.toBeChecked());
    await fireEvent.click(screen.getByRole("checkbox"));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/memory/incognito",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({ incognito: true }),
        }),
      );
    });
  });

  it("pins and forgets a memory through the governed API", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const fetchMock = stubFetch({
      "GET /api/memory": [
        {
          memory_id: "mem_1",
          text: "remember this",
          scope: "project:alpha",
          sensitivity: "normal",
          memory_type: "project",
          created_at: "2026-07-12T00:00:00Z",
          tags: [],
          source: "agent",
          provenance: {},
          confidence: 0.5,
          trust_score: 0.5,
          retention: "until_forget",
          approval_state: "approved",
          pinned: false,
        },
      ],
      "GET /api/memory/settings": { incognito: false },
      "PUT /api/memory/mem_1/pin": { ok: true, memory_id: "mem_1", pinned: true },
      "DELETE /api/memory/mem_1": { ok: true, memory_id: "mem_1" },
    });
    render(MemoryView);

    await waitFor(() => expect(screen.getByText("remember this")).toBeInTheDocument());
    const pinBtn = screen.getByRole("button", { name: /pin memory/i });
    await fireEvent.click(pinBtn);
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/memory/mem_1/pin",
        expect.objectContaining({ method: "PUT" }),
      ),
    );

    const forgetBtn = screen.getByRole("button", { name: /forget memory/i });
    await fireEvent.click(forgetBtn);
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/memory/mem_1",
        expect.objectContaining({ method: "DELETE" }),
      ),
    );
  });
});
