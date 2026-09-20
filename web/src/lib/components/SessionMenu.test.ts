import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
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
    render(SessionMenu, { sessionId: "ses_1", title: "Brief", onDelete: vi.fn() });
    const trigger = screen.getByRole("button", { name: /session actions/i });
    await fireEvent.click(trigger);
    const menu = screen.getByRole("menu", { name: /actions for brief/i });
    screen.getByRole("menuitem", { name: /copy local link/i }).focus();

    await fireEvent.keyDown(menu, { key: "Escape" });

    expect(screen.queryByRole("menu", { name: /actions for brief/i })).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("keeps sharing local and deleting, and offers nothing that files a chat", async () => {
    // BUG-303 — rename, move, pin and archive were here. They are how somebody
    // organises the conversations they work in, and this is the evidence
    // inspector. Delete stays because it removes the audit record itself.
    const writeText = vi.fn(async () => undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    const onDelete = vi.fn();
    render(SessionMenu, { sessionId: "ses_1", title: "Brief", onDelete });

    await fireEvent.click(screen.getByRole("button", { name: /session actions/i }));
    await fireEvent.click(screen.getByRole("menuitem", { name: /copy local link/i }));
    await fireEvent.click(screen.getByRole("menuitem", { name: /delete/i }));

    expect(writeText).toHaveBeenCalledWith(expect.stringContaining("/#/new-chat?session=ses_1"));
    expect(onDelete).toHaveBeenCalledOnce();
    for (const gone of [/^rename$/i, /move to project/i, /^pin$/i, /^archive$/i]) {
      expect(screen.queryByRole("menuitem", { name: gone })).not.toBeInTheDocument();
    }
    // And it says where they went, rather than leaving that to be discovered.
    expect(screen.getByRole("menuitem", { name: /organise in threads/i })).toHaveAttribute(
      "href",
      "#/search-chat",
    );
  });

  it("positions itself against the viewport, so a scrolling card cannot clip it", async () => {
    // Found live on 2026-09-20: the session table's card scrolls horizontally,
    // which makes the browser clip vertically too, and the menu opened 131px
    // below the bottom of it — with Delete, the only destructive control on
    // the page, off-screen.
    render(SessionMenu, { sessionId: "ses_1", title: "Brief", onDelete: vi.fn() });
    const trigger = screen.getByRole("button", { name: /session actions/i });
    await fireEvent.click(trigger);

    // The stylesheet makes it `position: fixed`; what the component supplies,
    // and what this asserts, is the pair of viewport coordinates that makes
    // fixed positioning land in the right place. jsdom does not resolve Svelte's
    // scoped CSS, so the rule itself is asserted by the live capture.
    const menu = screen.getByRole("menu", { name: /actions for brief/i });
    expect(menu.getAttribute("style")).toMatch(/top:\s*-?\d+(\.\d+)?px/);
    expect(menu.getAttribute("style")).toMatch(/right:\s*-?\d+(\.\d+)?px/);
  });

  it("closes when the page moves under it", async () => {
    render(SessionMenu, { sessionId: "ses_1", title: "Brief", onDelete: vi.fn() });
    await fireEvent.click(screen.getByRole("button", { name: /session actions/i }));
    expect(screen.getByRole("menu", { name: /actions for brief/i })).toBeVisible();

    await fireEvent.scroll(window);

    expect(screen.queryByRole("menu", { name: /actions for brief/i })).not.toBeInTheDocument();
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
  it("shows the newest unread notice wherever the owner is", async () => {
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
    // One unread: the count link would be a link to a page saying the same
    // thing this card already says.
    expect(screen.queryByRole("link", { name: /unread notices/ })).not.toBeInTheDocument();
  });

  // A docked notice nothing dismisses is a permanent obstruction, which is a
  // worse defect than the banner nobody could see. Reading it clears it.
  it("marks a notice read when it is opened, and counts the rest", async () => {
    setToken("control-token");
    const fetchMock = stubFetch({
      "GET /api/notifications": [
        { notification_id: "ntf_1", kind: "task_finished", title: "Nightly digest", body: "Done.", finding_id: null, subject_id: null, read: false, created_at: "2026-07-18T00:00:00Z" },
        { notification_id: "ntf_2", kind: "security_alert", title: "Security finding", body: "Review it.", finding_id: null, subject_id: null, read: false, created_at: "2026-07-18T00:00:00Z" },
      ],
      "POST /api/notifications/ntf_1/read": { ok: true },
    });
    render(NotificationCenter);

    expect(await screen.findByRole("link", { name: "2 unread notices" })).toHaveAttribute(
      "href",
      "#/observe?tab=notifications",
    );
    await fireEvent.click(await screen.findByRole("button", { name: /Nightly digest/ }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/api/notifications/ntf_1/read"),
        expect.objectContaining({ method: "POST" }),
      ),
    );
    // A finished run lands on the work, not on a list about it.
    expect(window.location.hash).toBe("#/tasks");
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
