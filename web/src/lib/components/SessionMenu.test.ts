import { fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, setToken } from "../api";
import { stubFetch } from "../test-helpers";
import SessionMenu from "./SessionMenu.svelte";
import ToolControlBoard from "./ToolControlBoard.svelte";
import PageState from "./PageState.svelte";
import NotificationCenter from "./NotificationCenter.svelte";
import { makeGate } from "../test-helpers";
import { isLoopbackHost } from "../loopback";

afterEach(() => {
  vi.unstubAllGlobals();
  setToken(null);
});

describe("SessionMenu", () => {
  it("dismisses with Escape and restores focus to the actions trigger", async () => {
    render(SessionMenu, {
      sessionId: "ses_1", title: "Brief", projects: [],
      onRename: vi.fn(), onMove: vi.fn(), onPin: vi.fn(), onArchive: vi.fn(), onDelete: vi.fn(),
    });
    const trigger = screen.getByRole("button", { name: /session actions/i });
    await fireEvent.click(trigger);
    const menu = screen.getByRole("menu", { name: /actions for brief/i });
    screen.getByRole("menuitem", { name: /copy local link/i }).focus();

    await fireEvent.keyDown(menu, { key: "Escape" });

    expect(screen.queryByRole("menu", { name: /actions for brief/i })).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("keeps sharing local and forwards the six session actions", async () => {
    const writeText = vi.fn(async () => undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    const onRename = vi.fn();
    const onMove = vi.fn();
    const onPin = vi.fn();
    const onArchive = vi.fn();
    const onDelete = vi.fn();
    render(SessionMenu, {
      sessionId: "ses_1", title: "Brief", projects: [{ project_id: "prj_1", name: "Alpha" }],
      onRename, onMove, onPin, onArchive, onDelete,
    });

    await fireEvent.click(screen.getByRole("button", { name: /session actions/i }));
    await fireEvent.click(screen.getByRole("menuitem", { name: /copy local link/i }));
    await fireEvent.click(screen.getByRole("menuitem", { name: /rename/i }));
    await fireEvent.input(screen.getByLabelText("Session title"), { target: { value: "Updated brief" } });
    await fireEvent.click(screen.getByRole("menuitem", { name: "Save name" }));
    await fireEvent.click(screen.getByRole("menuitem", { name: /move to project/i }));
    await fireEvent.click(screen.getByRole("menuitem", { name: "Alpha" }));
    await fireEvent.click(screen.getByRole("menuitem", { name: /pin/i }));
    await fireEvent.click(screen.getByRole("menuitem", { name: /archive/i }));
    await fireEvent.click(screen.getByRole("menuitem", { name: /delete/i }));

    expect(writeText).toHaveBeenCalledWith(expect.stringContaining("/#/new-chat?session=ses_1"));
    expect(onRename).toHaveBeenCalledWith("Updated brief");
    expect(onMove).toHaveBeenCalledWith("prj_1");
    expect(onMove).toHaveBeenCalledTimes(1);
    expect(onPin).toHaveBeenCalledOnce();
    expect(onArchive).toHaveBeenCalledOnce();
    expect(onDelete).toHaveBeenCalledOnce();
  });

  it("allows share only on loopback hosts", () => {
    expect(isLoopbackHost("localhost")).toBe(true);
    expect(isLoopbackHost("127.0.0.1")).toBe(true);
    expect(isLoopbackHost("::1")).toBe(true);
    expect(isLoopbackHost("example.test")).toBe(false);
  });
});

describe("ToolControlBoard", () => {
  it("omits a capability without an executor", () => {
    render(ToolControlBoard, {
      gates: [makeGate({ capability: "finance_runtime", blocked_reason_code: "activation_blocked:no_executor" })],
      onDecision: vi.fn(),
    });
    expect(screen.queryByRole("group", { name: /decision mode/i })).not.toBeInTheDocument();
  });
});

describe("shared page feedback", () => {
  it("renders a compact error state", () => {
    render(PageState, { state: "error", title: "Could not load sessions", detail: "Retry from the server." });
    expect(screen.getByRole("alert")).toHaveTextContent("Could not load sessions");
  });

  // REM-SET-NOTIFY — the strip reads its own notices now, because it lives in
  // the shell rather than on one page. It was mounted on the MCP destination
  // alone, so the account-wide "In-app popups" setting decided whether a banner
  // appeared somewhere the owner might never open.
  it("shows unread notices wherever the owner is, and links the full record", async () => {
    setToken("control-token");
    stubFetch({
      "GET /api/notifications": [
        { notification_id: "ntf_1", kind: "security_alert", title: "Security finding", body: "Review it.", finding_id: null, subject_id: null, read: false, created_at: "2026-07-18T00:00:00Z" },
        { notification_id: "ntf_2", kind: "task_finished", title: "Nightly digest", body: "Done.", finding_id: null, subject_id: null, read: true, created_at: "2026-07-18T00:00:00Z" },
      ],
    });
    render(NotificationCenter);

    const strip = await screen.findByRole("region", { name: "Notifications" });
    expect(strip).toHaveTextContent("Security finding");
    // A notice that has been read is a record, not an alert.
    expect(strip).not.toHaveTextContent("Nightly digest");
    expect(screen.getByRole("link", { name: "Open notifications" })).toHaveAttribute(
      "href",
      "#/observe?tab=notifications",
    );
  });
});

describe("session API contracts", () => {
  it("uses the existing rename and archive endpoints", async () => {
    setToken("control-token");
    const fetch = stubFetch({
      "PUT /api/sessions/ses_1/rename": { ok: true, session_id: "ses_1", title: "Brief" },
      "PUT /api/sessions/ses_1/archive": { ok: true, session_id: "ses_1", archived: true },
    });

    await api.renameSession("ses_1", "Brief");
    await api.archiveSession("ses_1");

    expect(fetch).toHaveBeenCalledTimes(2);
  });
});
