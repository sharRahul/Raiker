// The topbar is the shell's status strip: route identity, notification
// access, host and the stop switch — reachable on every route. It carries no
// project selector and no theme toggle: a global project silently retargeted
// every surface, and a theme is a preference, so both moved to where they are
// explained (Build and Settings respectively).
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import Topbar from "./Topbar.svelte";
import { stubFetch } from "../test-helpers";
import { announceBackupsChanged } from "../backupReminder";

afterEach(() => {
  vi.unstubAllGlobals();
});

const NOTIFICATIONS = [
  {
    notification_id: "ntf_1",
    kind: "security_alert",
    title: "MCP anomaly detected",
    body: "Tool set changed on a monitored server.",
    finding_id: null,
    subject_id: null,
    read: false,
    created_at: "2026-07-18T00:00:00Z",
  },
  {
    notification_id: "ntf_2",
    kind: "security_alert",
    title: "Old alert",
    body: "Already handled.",
    finding_id: null,
    subject_id: null,
    read: true,
    created_at: "2026-07-17T00:00:00Z",
  },
];

describe("Topbar scope", () => {
  it("keeps project and theme choices out of the top bar", async () => {
    stubFetch({ "GET /api/notifications": [] });
    render(Topbar, { title: "Chat", hint: "Ask anything" });

    await screen.findByRole("button", { name: "Notifications" });
    // The project selector belongs to Build, where the boundary it sets is
    // visible for the whole session; the theme toggle belongs to Settings.
    expect(screen.queryByLabelText("Active project")).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/theme/i)).not.toBeInTheDocument();
  });

  it("keeps the beta feedback route reachable from every page", async () => {
    stubFetch({ "GET /api/notifications": [], "GET /api/approvals": [] });
    render(Topbar, { title: "Chat", hint: "Ask anything" });

    const beta = await screen.findByRole("link", { name: "Beta — send feedback" });
    expect(beta).toHaveAttribute("href", "#/settings?tab=general#beta-feedback");
    expect(beta).toHaveAttribute("title", "Beta — send feedback");
  });
});

describe("Topbar tooltips", () => {
  // QUI-Q06 — every icon-only control says what it is on hover, in the same
  // words its accessible name uses.
  it("gives each icon-only control a tooltip matching its name", async () => {
    stubFetch({ "GET /api/notifications": NOTIFICATIONS, "GET /api/approvals": [] });
    render(Topbar, { title: "Chat", hint: "Ask anything" });

    const bell = await screen.findByRole("button", { name: /^Notifications/ });
    await waitFor(() => expect(bell).toHaveAttribute("title", "Notifications (1 unread)"));
    const approvals = screen.getByRole("link", { name: /^Approvals/ });
    expect(approvals).toHaveAttribute("title", approvals.getAttribute("aria-label"));
    const more = screen.getByRole("button", { name: "More pages and settings" });
    expect(more).toHaveAttribute("title", "More pages and settings");
    // The search tooltip shows the shortcut as printed on the key; its
    // accessible name spells it out for a screen reader.
    expect(screen.getByRole("button", { name: /^Search and commands/ }).getAttribute("title")).toMatch(
      /^Search and commands \(/,
    );
  });
});

describe("Topbar notifications", () => {
  it("shows the unread count on the notifications button", async () => {
    stubFetch({ "GET /api/notifications": NOTIFICATIONS });
    render(Topbar, { title: "New Chat", hint: "Start a conversation" });

    const bell = await screen.findByRole("button", { name: /notifications/i });
    await waitFor(() => expect(bell).toHaveTextContent("1"));
  });

  it("opens the panel, lists notifications, and marks them read", async () => {
    const fetchMock = stubFetch({
      "GET /api/notifications": NOTIFICATIONS,
      "POST /api/notifications/ntf_1/read": { ok: true },
    });
    render(Topbar, { title: "New Chat", hint: "Start a conversation" });

    await fireEvent.click(await screen.findByRole("button", { name: /notifications/i }));
    await waitFor(() => expect(screen.getByText("MCP anomaly detected")).toBeInTheDocument());

    await fireEvent.click(screen.getByRole("button", { name: /mark all read/i }));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/notifications/ntf_1/read",
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  it("closes the notification panel with Escape and restores focus to its trigger", async () => {
    stubFetch({ "GET /api/notifications": NOTIFICATIONS });
    render(Topbar, { title: "New Chat", hint: "Start a conversation" });

    const bell = await screen.findByRole("button", { name: /notifications/i });
    await fireEvent.click(bell);
    await waitFor(() => expect(screen.getByRole("region", { name: "Notification panel" })).toBeInTheDocument());

    await fireEvent.keyDown(window, { key: "Escape" });

    expect(screen.queryByRole("region", { name: "Notification panel" })).not.toBeInTheDocument();
    expect(bell).toHaveFocus();
  });
});

// FIXED-1128 — the count leaves out what can no longer be decided, and follows
// a decision made in this tab without a reload.
describe("Topbar approvals count", () => {
  it("counts only decidable approvals and re-reads when a decision is announced", async () => {
    let pending = [
      { approval_id: "a1", is_expired: false },
      { approval_id: "a2", is_expired: true },
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        const body = url.includes("/api/approvals") ? pending : [];
        return { ok: true, status: 200, json: async () => body } as Response;
      }),
    );
    render(Topbar, { title: "Chat", hint: "" });
    expect(await screen.findByRole("link", { name: "Approvals (1 waiting on you)" })).toBeInTheDocument();

    pending = [];
    const { publishApprovalResolved } = await import("../approvalResume");
    publishApprovalResolved({ approvalId: "a1", sessionId: null, turnId: null, approved: true });
    await waitFor(() => expect(screen.getByRole("link", { name: "Approvals" })).toBeInTheDocument());
  });
});

describe("Topbar live work line (QUI-F04)", () => {
  const task = (task_id: string, status: string, title: string, current_step: string | null) => ({
    task_id, status, title, current_step, updated_at: "2026-10-24T00:00:00Z", completed_at: null,
  });

  it("is absent while nothing runs", async () => {
    stubFetch({ "GET /api/notifications": [], "GET /api/tasks": [task("t0", "completed", "Done", null)] });
    render(Topbar, { title: "Home", hint: "" });
    await screen.findByRole("button", { name: "Notifications" });
    expect(screen.queryByTestId("live-work-line")).not.toBeInTheDocument();
  });

  it("links the one running task with its real step", async () => {
    stubFetch({ "GET /api/notifications": [], "GET /api/tasks": [task("t1", "running", "Morning brief", "Reading calendar")] });
    render(Topbar, { title: "Home", hint: "" });
    const line = await screen.findByRole("link", { name: "Morning brief · Reading calendar" });
    expect(line).toHaveAttribute("href", "#/tasks?task=t1");
  });

  it("opens a menu listing each when several run", async () => {
    stubFetch({
      "GET /api/notifications": [],
      "GET /api/tasks": [task("t1", "running", "Morning brief", null), task("t2", "waiting_for_approval", "Send reply", null)],
    });
    render(Topbar, { title: "Home", hint: "" });
    const button = await screen.findByRole("button", { name: "2 tasks running · 1 waiting for you" });
    await fireEvent.click(button);
    expect(screen.getByRole("link", { name: /Send reply\s*waiting for you/ })).toHaveAttribute("href", "#/tasks?task=t2");
  });
});

describe("Topbar backup reminder", () => {
  const daysAgo = (days: number) => new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();

  it("warns from every page when no verified backup is newer than 14 days", async () => {
    stubFetch({
      "GET /api/notifications": [],
      "GET /api/backups": {
        key_fingerprint: "kfp",
        backups: [
          { backup_id: "bkp_old", created_at: daysAgo(20), state: "verified" },
          { backup_id: "bkp_bad", created_at: daysAgo(1), state: "damaged" },
        ],
      },
    });
    render(Topbar, { title: "Chat", hint: "Ask anything" });

    const reminder = await screen.findByRole("link", { name: /The last backup was 20 days ago\. Make a backup/ });
    expect(reminder).toHaveAttribute("href", "#/settings?tab=backups");
    expect(reminder).toHaveAttribute("title", "The last backup was 20 days ago.");
  });

  it("warns when there is no backup at all", async () => {
    stubFetch({ "GET /api/notifications": [], "GET /api/backups": { key_fingerprint: "kfp", backups: [] } });
    render(Topbar, { title: "Chat", hint: "Ask anything" });

    await screen.findByRole("link", { name: /There is no backup of this workspace yet/ });
  });

  it("stays quiet with a recent verified backup, or when backups cannot be read", async () => {
    stubFetch({
      "GET /api/notifications": [],
      "GET /api/backups": { key_fingerprint: "kfp", backups: [{ backup_id: "bkp_new", created_at: daysAgo(10), state: "verified" }] },
    });
    const first = render(Topbar, { title: "Chat", hint: "Ask anything" });
    await screen.findByRole("button", { name: "Notifications" });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.queryByRole("link", { name: /Make a backup/ })).not.toBeInTheDocument();
    first.unmount();

    stubFetch({ "GET /api/notifications": [], "GET /api/backups": { __status: 500 } });
    render(Topbar, { title: "Chat", hint: "Ask anything" });
    await screen.findByRole("button", { name: "Notifications" });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.queryByRole("link", { name: /Make a backup/ })).not.toBeInTheDocument();
  });

  it("re-reads when a backup is made on this page", async () => {
    stubFetch({ "GET /api/notifications": [], "GET /api/backups": { key_fingerprint: "kfp", backups: [] } });
    render(Topbar, { title: "Chat", hint: "Ask anything" });
    await screen.findByRole("link", { name: /Make a backup/ });

    stubFetch({
      "GET /api/notifications": [],
      "GET /api/backups": { key_fingerprint: "kfp", backups: [{ backup_id: "bkp_now", created_at: daysAgo(0), state: "verified" }] },
    });
    announceBackupsChanged();
    await waitFor(() => expect(screen.queryByRole("link", { name: /Make a backup/ })).not.toBeInTheDocument());
  });
});
