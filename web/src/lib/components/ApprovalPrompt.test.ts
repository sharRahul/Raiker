import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { api, setToken } from "../api";
import type { ApprovalView } from "../apiTypes";
import { uiPrefs } from "../prefs.svelte";
import ApprovalPrompt from "./ApprovalPrompt.svelte";

beforeEach(() => {
  setToken("test-token");
  window.location.hash = "#/new-chat";
});
afterEach(() => {
  setToken(null);
  uiPrefs.desktop = false;
  Object.defineProperty(document, "hidden", { value: false, configurable: true });
  vi.unstubAllGlobals();
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

// BUG-255 — a decision raised while Raiker is in the background.

/** Put a Notification constructor in place and report what it was handed. */
function stubNotifications(permission: NotificationPermission) {
  const raised: { title: string; options?: NotificationOptions }[] = [];
  class StubNotification {
    onclick: (() => void) | null = null;
    static permission = permission;
    constructor(title: string, options?: NotificationOptions) {
      raised.push({ title, options });
    }
    close() {}
  }
  vi.stubGlobal("Notification", StubNotification);
  return raised;
}

function setHidden(hidden: boolean) {
  Object.defineProperty(document, "hidden", { value: hidden, configurable: true });
  document.dispatchEvent(new Event("visibilitychange"));
}

it("announces a decision to the desktop when Raiker is not the window on screen", async () => {
  uiPrefs.desktop = true;
  const raised = stubNotifications("granted");
  setHidden(true);
  vi.spyOn(api, "approvals").mockResolvedValue([approval()]);

  render(ApprovalPrompt);

  await waitFor(() => expect(raised).toHaveLength(1));
  expect(raised[0].title).toBe("Raiker needs a decision");
  expect(raised[0].options?.body).toContain("Write file");
  // One subject, one banner, however many times the poll sees it.
  expect(raised[0].options?.tag).toBe("raiker-approval");
});

it("says nothing to the desktop about a decision the owner can already see", async () => {
  uiPrefs.desktop = true;
  const raised = stubNotifications("granted");
  setHidden(false);
  vi.spyOn(api, "approvals").mockResolvedValue([approval()]);

  render(ApprovalPrompt);

  expect(await screen.findByText("Approval needed")).toBeInTheDocument();
  expect(raised).toHaveLength(0);
});

it("respects the owner's preference even when the browser would allow it", async () => {
  uiPrefs.desktop = false;
  const raised = stubNotifications("granted");
  setHidden(true);
  vi.spyOn(api, "approvals").mockResolvedValue([approval()]);

  render(ApprovalPrompt);

  await new Promise((resolve) => setTimeout(resolve, 20));
  expect(raised).toHaveLength(0);
});
