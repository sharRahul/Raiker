import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, setToken } from "../api";
import { delivery } from "../deliveryPolicy.svelte";
import type { NotificationDelivery, NotificationView } from "../generated/apiContract";
import { resetInlineDecisions, shownInline } from "../inlineDecisions.svelte";
import { stubFetch } from "../test-helpers";
import Notification from "../views/settings/Notification.svelte";
import ApprovalPrompt from "./ApprovalPrompt.svelte";
import NotificationCenter from "./NotificationCenter.svelte";

/**
 * DEC-21a — quiet hours, as the shell reads them. The server decides each
 * notice when it is written; these pin that every surface obeys the stored
 * decision rather than its own clock, that the end of the interval is one
 * summary acknowledged on the server, and BUG-317/320's placement rules.
 */

function notice(partial: Partial<NotificationView> = {}): NotificationView {
  return {
    notification_id: "ntf_1",
    kind: "task_finished",
    title: "Nightly digest",
    body: "Done.",
    finding_id: null,
    subject_id: null,
    read: false,
    created_at: "2026-10-05T22:30:00Z",
    in_app_presentation: "interrupt",
    desktop_presentation: "interrupt",
    quiet_until: null,
    summarised_at: null,
    ...partial,
  };
}

function policy(partial: Partial<NotificationDelivery> = {}): NotificationDelivery {
  return {
    quiet_hours: {
      enabled: true,
      start: "22:00",
      end: "07:00",
      timezone: "UTC",
      active: false,
      ends_at: null,
      next_starts_at: "2026-10-05T22:00:00Z",
      critical_in_app: false,
      critical_desktop: false,
    },
    decisions_interrupt: true,
    categories: [
      { category: "work", label: "Background work finished or paused", interrupts: true },
      { category: "security", label: "Security findings and containment", interrupts: true },
      { category: "extensions", label: "Extensions and MCP servers", interrupts: true },
    ],
    held: [],
    ...partial,
  };
}

beforeEach(() => {
  setToken("test-token");
  window.location.hash = "#/home";
});
afterEach(() => {
  setToken(null);
  delivery.current = null;
  resetInlineDecisions();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("the notice dock", () => {
  it("never docks a notice the server held for quiet hours or a muted category", async () => {
    stubFetch({
      "GET /api/notifications": [
        notice({ notification_id: "ntf_held", title: "Held one", in_app_presentation: "quiet_hours" }),
        notice({ notification_id: "ntf_muted", title: "Muted one", in_app_presentation: "muted" }),
        notice({ notification_id: "ntf_shown", title: "Shown one" }),
      ],
      "GET /api/notifications/delivery": policy(),
    });
    render(NotificationCenter);
    const dock = await screen.findByRole("region", { name: "Notifications" });
    expect(dock).toHaveTextContent("Shown one");
    expect(dock).not.toHaveTextContent("Held one");
    expect(dock).not.toHaveTextContent("Muted one");
    // One shown: no count link pretending three are waiting here.
    expect(screen.queryByRole("link", { name: /unread notices/ })).not.toBeInTheDocument();
  });

  it("offers one summary when quiet hours end, and acknowledges it on the server", async () => {
    const held = [
      notice({ notification_id: "ntf_a", title: "A routine was paused", in_app_presentation: "quiet_hours", quiet_until: "2026-10-06T07:00:00Z" }),
      notice({ notification_id: "ntf_b", title: "Background task finished", in_app_presentation: "quiet_hours", quiet_until: "2026-10-06T07:00:00Z" }),
    ];
    const routes: Record<string, unknown> = {
      "GET /api/notifications": held,
      "GET /api/notifications/delivery": policy({ held }),
      "POST /api/notifications/held/acknowledge": { acknowledged: 2 },
    };
    const fetchMock = stubFetch(routes);
    render(NotificationCenter);
    const summary = await screen.findByRole("region", { name: "Held during quiet hours" });
    expect(summary).toHaveTextContent("2 notices were held until 07:00");
    expect(summary).toHaveTextContent("A routine was paused");
    // Not the night replayed as toasts.
    expect(screen.queryByRole("region", { name: "Notifications" })).not.toBeInTheDocument();

    // What the server answers once the summary is acknowledged.
    routes["GET /api/notifications/delivery"] = policy();
    await fireEvent.click(screen.getByRole("button", { name: "Later" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/api/notifications/held/acknowledge"),
        expect.objectContaining({ method: "POST", body: JSON.stringify({ notification_ids: ["ntf_a", "ntf_b"] }) }),
      ),
    );
    expect(screen.queryByRole("region", { name: "Held during quiet hours" })).not.toBeInTheDocument();
  });

  it("does not summarise while quiet hours are still on", async () => {
    const held = [notice({ in_app_presentation: "quiet_hours", quiet_until: "2026-10-06T07:00:00Z" })];
    stubFetch({
      "GET /api/notifications": held,
      "GET /api/notifications/delivery": policy({
        held,
        quiet_hours: { ...policy().quiet_hours, active: true, ends_at: "2026-10-06T07:00:00Z", next_starts_at: null },
      }),
    });
    render(NotificationCenter);
    await waitFor(() => expect(delivery.current).not.toBeNull());
    expect(screen.queryByRole("region", { name: "Held during quiet hours" })).not.toBeInTheDocument();
  });

  it("folds into the bell on a work surface instead of covering the conversation (BUG-320)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    window.location.hash = "#/new-chat";
    stubFetch({
      "GET /api/notifications": [notice({ title: "Shown one" })],
      "GET /api/notifications/delivery": policy(),
    });
    render(NotificationCenter);
    expect(await screen.findByRole("region", { name: "Notifications" })).toBeInTheDocument();
    await vi.advanceTimersByTimeAsync(6500);
    await waitFor(() => expect(screen.queryByRole("region", { name: "Notifications" })).not.toBeInTheDocument());
  });

  it("stays until read on a page that is not a work surface", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    stubFetch({
      "GET /api/notifications": [notice({ title: "Shown one" })],
      "GET /api/notifications/delivery": policy(),
    });
    render(NotificationCenter);
    expect(await screen.findByRole("region", { name: "Notifications" })).toBeInTheDocument();
    await vi.advanceTimersByTimeAsync(6500);
    expect(screen.getByRole("region", { name: "Notifications" })).toBeInTheDocument();
  });
});

describe("the approval card", () => {
  const pending = {
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
    proposed_by: null,
    approved_by: null,
    machine_identity: null,
    executes_action: false,
    critical: false,
    resolved_by: null,
    queue_position: 1,
    queue_total: 1,
  } as never;

  it("does not float a decision during quiet hours", async () => {
    vi.spyOn(api, "approvals").mockResolvedValue([pending]);
    vi.spyOn(api, "notificationDelivery").mockResolvedValue(
      policy({ decisions_interrupt: false, quiet_hours: { ...policy().quiet_hours, active: true } }),
    );
    render(ApprovalPrompt);
    await waitFor(() => expect(delivery.current?.decisions_interrupt).toBe(false));
    expect(screen.queryByText("Approval needed")).not.toBeInTheDocument();
  });

  it("leaves alone a decision the page shows inline, and floats it once that page is hidden (BUG-317)", async () => {
    vi.spyOn(api, "approvals").mockResolvedValue([pending]);
    vi.spyOn(api, "notificationDelivery").mockResolvedValue(policy());
    // Build's *Waiting on you* row: on screen, then hidden by a route change
    // while Build stays mounted.
    const row = document.createElement("div");
    document.body.append(row);
    let onScreen = true;
    row.getClientRects = () => (onScreen ? [{} as DOMRect] : []) as unknown as DOMRectList;
    const mark = shownInline(row, "ap_1");
    window.location.hash = "#/build";
    render(ApprovalPrompt);
    await waitFor(() => expect(delivery.current).not.toBeNull());
    await new Promise((resolve) => setTimeout(resolve, 120));
    expect(screen.queryByText("Approval needed")).not.toBeInTheDocument();

    onScreen = false;
    window.location.hash = "#/home";
    window.dispatchEvent(new HashChangeEvent("hashchange"));
    expect(await screen.findByText("Approval needed")).toBeInTheDocument();
    mark.destroy();
    row.remove();
  });
});

describe("Settings → Notifications, quiet hours", () => {
  it("is off until the owner turns it on, with both exceptions off", () => {
    render(Notification, { settings: {}, save: vi.fn() });
    expect(screen.getByLabelText("Use quiet hours")).not.toBeChecked();
    expect(screen.queryByLabelText("Quiet hours start")).not.toBeInTheDocument();
  });

  it("saves the interval and each exception under the keys the server evaluates", async () => {
    const save = vi.fn();
    render(Notification, { settings: { "notification.quiet_hours.enabled": true }, save });
    expect(screen.getByLabelText("Quiet hours start")).toHaveValue("22:00");
    expect(screen.getByLabelText("Let security alerts through inside Raiker")).not.toBeChecked();
    expect(screen.getByLabelText("Let security alerts through outside Raiker")).not.toBeChecked();
    await fireEvent.change(screen.getByLabelText("Quiet hours end"), { target: { value: "06:30" } });
    expect(save).toHaveBeenCalledWith({ "notification.quiet_hours.end": "06:30" });
    await fireEvent.click(screen.getByLabelText("Let security alerts through outside Raiker"));
    expect(save).toHaveBeenCalledWith({ "notification.quiet_hours.critical_desktop": true });
  });

  it("says when an interval would be empty", () => {
    render(Notification, {
      settings: {
        "notification.quiet_hours.enabled": true,
        "notification.quiet_hours.start": "07:00",
        "notification.quiet_hours.end": "07:00",
      },
      save: vi.fn(),
    });
    expect(screen.getByRole("alert")).toHaveTextContent("cannot start and end at the same time");
  });

  it("offers interrupt switches for every category but decisions", async () => {
    const save = vi.fn();
    render(Notification, { settings: {}, save });
    expect(screen.getByLabelText("Background work finished or paused")).toBeChecked();
    expect(screen.queryByLabelText(/approval/i)).not.toBeInTheDocument();
    await fireEvent.click(screen.getByLabelText("Extensions and MCP servers"));
    expect(save).toHaveBeenCalledWith({ "notification.interrupt.extensions": false });
  });

  it("reports a test notice the way the server decided it", async () => {
    vi.spyOn(api, "notificationDelivery").mockResolvedValue(policy());
    vi.spyOn(api, "sendTestNotice").mockResolvedValue({
      notification: notice({
        kind: "test_notice",
        in_app_presentation: "quiet_hours",
        quiet_until: "2026-10-06T07:00:00Z",
      }),
    });
    render(Notification, { settings: {}, save: vi.fn() });
    await waitFor(() => expect(delivery.current).not.toBeNull());
    await fireEvent.click(screen.getByRole("button", { name: "Send a test notice" }));
    expect(await screen.findByTestId("test-notice-result")).toHaveTextContent(
      "Sent and held: quiet hours are on until 07:00",
    );
  });
});

describe("the bell and the dock agree", () => {
  it("announces a change in unread notices so the bell re-reads instead of waiting for a reload", async () => {
    stubFetch({
      "GET /api/notifications": [notice({ title: "Arrived later" })],
      "GET /api/notifications/delivery": policy(),
    });
    const heard = vi.fn();
    window.addEventListener("raiker:notices-changed", heard);
    render(NotificationCenter);
    await waitFor(() => expect(heard).toHaveBeenCalled());
    window.removeEventListener("raiker:notices-changed", heard);
  });
});
