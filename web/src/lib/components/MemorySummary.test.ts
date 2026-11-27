import { fireEvent, render, screen, within } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import MemorySummary from "./MemorySummary.svelte";
import type { MemoryControlView } from "../apiTypes";

const memory = (id: string, extra: Partial<MemoryControlView> = {}): MemoryControlView => ({
  memory_id: id, text: `Fact ${id}`, memory_type: "preference", scope: "account",
  sensitivity: "normal", approval_state: "approved", tags: [], source: "owner",
  provenance: {}, confidence: 1, trust_score: 1, retention: "until_forget",
  created_at: "2026-11-01T00:00:00Z", pinned: false, search_enabled: true,
  expires_at: null, archived_at: null, source_event_id: "", created_by: "owner",
  valid_from: null, valid_until: null, supersedes_memory_id: null, remembered_reason: null,
  updated_at: null, last_used_at: null, recall_turn_count: 0,
  last_recalled_session_id: null, last_recalled_turn_id: null, last_recalled_origin: null,
  review_priority: 0, review_reasons: [], ...extra,
});

describe("Memory summary", () => {
  it("groups approved active facts and keeps their scope visible", () => {
    render(MemorySummary, { memories: [
      memory("tea"), memory("repo", { memory_type: "project", scope: "project:alpha" }),
      memory("future", { memory_type: "unknown-kind" }),
      memory("archived", { archived_at: "2026-11-02T00:00:00Z" }),
      memory("expired", { expires_at: "2000-01-01T00:00:00Z" }),
      memory("pending", { approval_state: "pending" }),
    ], onSave: vi.fn(), onForget: vi.fn() });
    expect(screen.getByRole("heading", { name: "Preferences" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Projects" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Other memories" })).toBeInTheDocument();
    expect(screen.getByText("In one project only")).toBeInTheDocument();
    expect(screen.queryByText("project:alpha")).toBeNull();
    expect(screen.queryByText("Fact archived")).toBeNull();
    expect(screen.queryByText("Fact expired")).toBeNull();
    expect(screen.queryByText("Fact pending")).toBeNull();
  });

  it("preserves a failed edit and saves a corrected draft in place", async () => {
    const save = vi.fn().mockRejectedValueOnce(new Error("offline")).mockResolvedValue(undefined);
    render(MemorySummary, { memories: [memory("tea")], onSave: save, onForget: vi.fn() });
    await fireEvent.click(screen.getByRole("button", { name: "Edit Fact tea" }));
    await fireEvent.input(screen.getByRole("textbox", { name: "Memory text" }), { target: { value: "Prefer Assam" } });
    await fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/could not save/i);
    expect(screen.getByRole("textbox")).toHaveValue("Prefer Assam");
    await fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Memory updated");
    expect(save).toHaveBeenLastCalledWith(expect.objectContaining({ memory_id: "tea" }), "Prefer Assam");
  });

  it("offers forgetting beside the fact", async () => {
    const forget = vi.fn();
    render(MemorySummary, { memories: [memory("tea")], onSave: vi.fn(), onForget: forget });
    const row = screen.getByRole("listitem");
    await fireEvent.click(within(row).getByRole("button", { name: "Forget Fact tea" }));
    expect(forget).toHaveBeenCalledWith(expect.objectContaining({ memory_id: "tea" }));
  });
});
