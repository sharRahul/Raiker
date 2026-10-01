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

// Found live on 2026-09-28: docked bottom-right, the card covered the model
// picker and Send of a composer on the same corner of the screen.
it("rises above a composer it would cover, and stays in its corner otherwise", async () => {
  vi.spyOn(api, "approvals").mockResolvedValue([approval()]);
  Object.defineProperty(window, "innerWidth", { value: 1440, configurable: true });
  Object.defineProperty(window, "innerHeight", { value: 1000, configurable: true });
  render(ApprovalPrompt);
  const card = (await screen.findByText("Approval needed")).closest("section") as HTMLElement;
  expect(card.style.bottom).toBe("18px");

  const composer = document.createElement("div");
  composer.className = "composer-card";
  composer.getBoundingClientRect = () =>
    ({ top: 800, bottom: 980, left: 286, right: 1410, width: 1124, height: 180 }) as DOMRect;
  document.body.appendChild(composer);
  window.dispatchEvent(new Event("resize"));

  // 1000 − 800 + 12 = 212 above the bottom edge: clear of the composer.
  await waitFor(() => expect(card.style.bottom).toBe("212px"));
  composer.remove();
  window.dispatchEvent(new Event("resize"));
  await waitFor(() => expect(card.style.bottom).toBe("18px"));
});

// Found live on 2026-10-01: arriving on Chat with an approval waiting, the card
// was drawn before the composer mounted and covered its Send until the next
// one-second measurement.
it("rises above a composer that mounts after it, without waiting for a tick", async () => {
  vi.spyOn(api, "approvals").mockResolvedValue([approval()]);
  Object.defineProperty(window, "innerWidth", { value: 1440, configurable: true });
  Object.defineProperty(window, "innerHeight", { value: 1000, configurable: true });
  render(ApprovalPrompt);
  const card = (await screen.findByText("Approval needed")).closest("section") as HTMLElement;
  expect(card.style.bottom).toBe("18px");

  const composer = document.createElement("div");
  composer.className = "composer-card";
  composer.getBoundingClientRect = () =>
    ({ top: 800, bottom: 980, left: 286, right: 1410, width: 1124, height: 180 }) as DOMRect;
  // No resize: the page simply grows a composer, as a route does when it mounts.
  document.body.appendChild(composer);

  await waitFor(() => expect(card.style.bottom).toBe("212px"), { timeout: 300 });
  composer.remove();
});

// Found by the third 2026-09-28 round: the card covered Settings' Save changes,
// so a settings change could not be saved while an approval waited elsewhere.
it("rises above any bottom action bar that asks to be kept clear", async () => {
  vi.spyOn(api, "approvals").mockResolvedValue([approval()]);
  Object.defineProperty(window, "innerWidth", { value: 1440, configurable: true });
  Object.defineProperty(window, "innerHeight", { value: 1000, configurable: true });
  render(ApprovalPrompt);
  const card = (await screen.findByText("Approval needed")).closest("section") as HTMLElement;
  expect(card.style.bottom).toBe("18px");

  const saveBar = document.createElement("div");
  saveBar.setAttribute("data-dock-clear", "");
  saveBar.getBoundingClientRect = () =>
    ({ top: 900, bottom: 970, left: 540, right: 1410, width: 870, height: 70 }) as DOMRect;
  document.body.appendChild(saveBar);
  window.dispatchEvent(new Event("resize"));

  // 1000 − 900 + 12 = 112 above the bottom edge: clear of the save bar.
  await waitFor(() => expect(card.style.bottom).toBe("112px"));
  saveBar.remove();
  window.dispatchEvent(new Event("resize"));
  await waitFor(() => expect(card.style.bottom).toBe("18px"));
});

// Found live on 2026-09-28: the card stayed on screen over the Approvals page
// when the owner arrived there by a link, because the address was read once.
it("leaves the screen when the owner navigates to Approvals, and returns after", async () => {
  vi.spyOn(api, "approvals").mockResolvedValue([approval()]);
  window.location.hash = "#/new-chat";
  render(ApprovalPrompt);
  expect(await screen.findByText("Approval needed")).toBeTruthy();

  window.location.hash = "#/approvals";
  window.dispatchEvent(new HashChangeEvent("hashchange"));
  await waitFor(() => expect(screen.queryByText("Approval needed")).toBeNull());

  window.location.hash = "#/new-chat";
  window.dispatchEvent(new HashChangeEvent("hashchange"));
  expect(await screen.findByText("Approval needed")).toBeTruthy();
});
