import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { api, setToken } from "../api";
import type { ApprovalView } from "../apiTypes";
import ApprovalPrompt from "./ApprovalPrompt.svelte";

beforeEach(() => {
  setToken("test-token");
  window.location.hash = "#/new-chat";
});
afterEach(() => {
  setToken(null);
  vi.restoreAllMocks();
});

function approval(partial: Partial<ApprovalView> = {}): ApprovalView {
  return {
    approval_id: "ap_1",
    action_id: "act_1",
    status: "pending",
    tool_name: "write_file",
    capability: "file_write",
    risk_level: "medium",
    session_id: "sess_1",
    turn_id: "turn_1",
    created_at: "2026-09-03T00:00:00Z",
    age_seconds: 4,
    requires_approval: true,
    expires_at: null,
    is_expired: false,
    executes_action: false,
    critical: false,
    resolved_by: null,
    queue_position: 1,
    queue_total: 1,
    ...partial,
  };
}

it("announces a pending decision on whatever page is open and resolves it there", async () => {
  vi.spyOn(api, "approvals").mockResolvedValue([approval()]);
  const resolve = vi.spyOn(api, "resolveApproval").mockResolvedValue({
    ok: true,
    approval_id: "ap_1",
    status: "approved",
    executes_action: false,
  } as never);
  render(ApprovalPrompt);

  expect(await screen.findByText("Approval needed")).toBeInTheDocument();
  expect(screen.getByText("Write file")).toBeInTheDocument();

  await fireEvent.click(screen.getByRole("button", { name: /Approve/ }));
  await waitFor(() =>
    expect(resolve).toHaveBeenCalledWith("ap_1", {
      approve: true,
      reason: "approved from the prompt",
    }),
  );
});

it("sends a critical decision to the inbox instead of answering it here", async () => {
  vi.spyOn(api, "approvals").mockResolvedValue([approval({ critical: true })]);
  render(ApprovalPrompt);

  expect(await screen.findByText(/needs your password/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Approve/ })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Review" })).toBeInTheDocument();
});

it("keeps quiet on the Approvals page, which already lists everything", async () => {
  window.location.hash = "#/approvals";
  vi.spyOn(api, "approvals").mockResolvedValue([approval()]);
  render(ApprovalPrompt);

  await new Promise((resolve) => setTimeout(resolve, 20));
  expect(screen.queryByText("Approval needed")).not.toBeInTheDocument();
});

it("puts one decision aside without resolving it", async () => {
  vi.spyOn(api, "approvals").mockResolvedValue([
    approval(),
    approval({ approval_id: "ap_2", tool_name: "run_command" }),
  ]);
  const resolve = vi.spyOn(api, "resolveApproval");
  render(ApprovalPrompt);

  expect(await screen.findByText("1 more")).toBeInTheDocument();
  await fireEvent.click(screen.getByRole("button", { name: "Decide later" }));

  expect(await screen.findByText("Run command")).toBeInTheDocument();
  expect(resolve).not.toHaveBeenCalled();
});
