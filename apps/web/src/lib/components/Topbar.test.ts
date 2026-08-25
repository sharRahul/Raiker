// The topbar is the shell's status strip: route identity, notification
// access, host and the stop switch — reachable on every route. It carries no
// project selector and no theme toggle: a global project silently retargeted
// every surface, and a theme is a preference, so both moved to where they are
// explained (Build and Settings respectively).
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import Topbar from "./Topbar.svelte";
import { stubFetch } from "../test-helpers";

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
