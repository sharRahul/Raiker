import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import ApprovalsView from "./ApprovalsView.svelte";
import { stubFetch } from "../test-helpers";

const PENDING = {
  approval_id: "appr_1",
  action_id: "act_1",
  status: "pending",
  tool_name: "write_file",
  capability: "file_write_execution",
  risk_level: "medium",
  session_id: "sess_abcdef123456",
  turn_id: "turn_1",
  created_at: "2026-07-07T00:00:00Z",
  age_seconds: 60,
  requires_approval: true,
  executes_action: false,
};

const DETAIL = {
  approval: PENDING,
  arguments: { path: "notes.txt" },
  diff: "--- a/notes.txt\n+++ b/notes.txt\n+hello\n",
  diff_path: "notes.txt",
  preview_kind: "file_diff",
  metadata_only_notice:
    "Approval resolution is metadata-only. Recording a decision does NOT execute the action.",
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ApprovalsView", () => {
  it("lists pending approvals with their capability and risk", async () => {
    stubFetch({ "GET /api/approvals": [PENDING] });
    render(ApprovalsView);
    // The raw tool identifier "write_file" is shown as a plain-English name, not a code.
    await waitFor(() => {
      expect(screen.getByText("Write file")).toBeInTheDocument();
    });
    expect(screen.queryByText("write_file")).not.toBeInTheDocument();
    expect(screen.getByText("File writes")).toBeInTheDocument();
    expect(screen.getByText("medium")).toBeInTheDocument();
  });

  it("shows the metadata-only notice and diff preview in the review panel", async () => {
    stubFetch({
      "GET /api/approvals": [PENDING],
      "GET /api/approvals/appr_1": DETAIL,
    });
    render(ApprovalsView);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /review/i })).toBeInTheDocument();
    });
    await fireEvent.click(screen.getByRole("button", { name: /review/i }));
    await waitFor(() => {
      expect(screen.getByText(/metadata-only/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/\+hello/)).toBeInTheDocument();
    // Approve is explicit about not executing.
    expect(screen.getByRole("button", { name: /approve \(record only\)/i })).toBeInTheDocument();
  });

  it("shows a friendly empty state when nothing is pending", async () => {
    stubFetch({ "GET /api/approvals": [] });
    render(ApprovalsView);
    await waitFor(() => {
      expect(screen.getByText(/nothing waiting on you/i)).toBeInTheDocument();
    });
  });
});
