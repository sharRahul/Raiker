import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ApprovalDetailView, ApprovalView } from "./apiTypes";

const approvals = vi.fn();
const approval = vi.fn();
const resolveApproval = vi.fn();

vi.mock("./api", () => ({
  api: {
    approvals: () => approvals(),
    approval: (id: string) => approval(id),
    resolveApproval: (id: string, body: unknown) => resolveApproval(id, body),
  },
  ApiError: class ApiError extends Error {},
}));

const PENDING: ApprovalView = {
  approval_id: "appr_1",
  action_id: "act_1",
  status: "pending",
  tool_name: "write_file",
  capability: "file_write_execution",
  risk_level: "high",
  session_id: "sess_a",
  turn_id: "turn_a",
  created_at: "2026-06-22T17:00:00Z",
  age_seconds: 42,
  requires_approval: true,
  executes_action: false,
};

const DETAIL: ApprovalDetailView = {
  approval: PENDING,
  arguments: { path: "notes.txt", text: "hello" },
  diff: "--- a/notes.txt\n+++ b/notes.txt\n+hello\n",
  diff_path: "notes.txt",
  preview_kind: "file_diff",
  metadata_only_notice:
    "Approval resolution is metadata-only. Recording a decision does NOT execute the action.",
};

describe("ApprovalQueue", () => {
  beforeEach(() => {
    approvals.mockReset();
    approval.mockReset();
    resolveApproval.mockReset();
  });

  it("renders the queue with an Approval-required badge and the metadata-only banner", async () => {
    approvals.mockResolvedValue([PENDING]);
    const { default: ApprovalQueue } = await import("./ApprovalQueue.svelte");
    render(ApprovalQueue);

    expect(await screen.findByText("write_file")).toBeInTheDocument();
    expect(screen.getByText("file_write_execution")).toBeInTheDocument();
    expect(screen.getAllByText("Approval-required").length).toBeGreaterThan(0);
    // Persistent metadata-only banner is present (asserted, per the test matrix).
    expect(screen.getByText(/does/i)).toBeInTheDocument();
    expect(screen.getAllByText(/metadata-only/i).length).toBeGreaterThan(0);
  });

  it("opens detail and resolves with a required reason via the client", async () => {
    approvals.mockResolvedValue([PENDING]);
    approval.mockResolvedValue(DETAIL);
    resolveApproval.mockResolvedValue({
      approval_id: "appr_1",
      action_id: "act_1",
      status: "approved",
      executes_action: false,
      reason: "looks good",
    });

    const { default: ApprovalQueue } = await import("./ApprovalQueue.svelte");
    render(ApprovalQueue);

    await fireEvent.click(await screen.findByRole("button", { name: /review/i }));

    // Detail shows the diff preview.
    expect((await screen.findAllByText(/notes\.txt/)).length).toBeGreaterThan(0);

    const approve = await screen.findByRole("button", { name: /approve/i });
    // Approve is disabled until a reason is provided.
    expect(approve).toBeDisabled();

    const reason = screen.getByLabelText(/reason/i);
    await fireEvent.input(reason, { target: { value: "looks good" } });
    expect(approve).toBeEnabled();

    await fireEvent.click(approve);
    await waitFor(() =>
      expect(resolveApproval).toHaveBeenCalledWith("appr_1", { approve: true, reason: "looks good" }),
    );
    expect(await screen.findByText(/No action was executed/i)).toBeInTheDocument();
  });
});
