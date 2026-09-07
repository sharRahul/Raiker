import { render, screen, waitFor } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import { api } from "../api";
import BuildSidePanel from "./BuildSidePanel.svelte";

describe("BuildSidePanel", () => {
  it("keeps an unavailable background-work error visible instead of claiming nothing is running", async () => {
    vi.spyOn(api, "tasks").mockRejectedValue(new Error("offline"));

    render(BuildSidePanel, { onclose: vi.fn() });

    await waitFor(() => expect(screen.getByText("Background work unavailable.")).toBeInTheDocument());
    expect(screen.queryByText("Nothing running")).not.toBeInTheDocument();
  });

  it("offers a direct approval review link for a waiting task", async () => {
    vi.spyOn(api, "tasks").mockResolvedValue([
      {
        task_id: "task-1",
        session_id: "session-1",
        status: "waiting_for_approval",
        title: "Apply the governed edit",
        objective: "",
        current_step: "Waiting for your decision",
        progress_percent: 50,
        created_at: "2026-07-28T10:00:00Z",
        updated_at: "2026-07-28T10:00:00Z",
        completed_at: null,
        summary: null,
        project_id: null,
      },
    ]);

    render(BuildSidePanel, { onclose: vi.fn() });

    const review = await screen.findByRole("link", { name: "Review approval" });
    expect(review).toHaveAttribute("href", "#/approvals?session=session-1");
  });
});
