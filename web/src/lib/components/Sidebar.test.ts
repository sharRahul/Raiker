// The full route list lives in the adaptive drawer so every governed route
// stays available when phone and tablet controls take over.
import { fireEvent, render, screen, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import Sidebar from "./Sidebar.svelte";
import { NAV_ITEMS, SIDEBAR_GROUPS } from "../nav";
import { stubFetch } from "../test-helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("Sidebar navigation", () => {
  it("keeps every route labelled in the adaptive drawer", () => {
    render(Sidebar, { current: "new-chat" });
    const nav = screen.getByRole("navigation", { name: "All navigation" });
    expect(nav).toBeInTheDocument();
    // The rail carries the work you open many times an hour. Manage, Observe
    // and Support moved behind the gear — `NAV_GROUPS` still holds every one of
    // them, because routing resolves against that list, but a link to them is
    // drawn in the window rather than here.
    for (const item of SIDEBAR_GROUPS.flatMap((group) => group.items)) {
      expect(within(nav).getByRole("link", { name: item.label })).toBeInTheDocument();
    }
    const moved = NAV_ITEMS.filter(
      (item) => !SIDEBAR_GROUPS.some((g) => g.items.some((i) => i.id === item.id)),
    );
    expect(moved.map((item) => item.id)).toContain("models");
    for (const item of moved) {
      expect(within(nav).queryByRole("link", { name: item.label })).toBeNull();
    }
  });

  it("marks the active route for assistive tech", () => {
    render(Sidebar, { current: "memory" });
    const active = within(screen.getByRole("navigation", { name: "All navigation" })).getByRole("link", { name: "Memory" });
    expect(active).toHaveAttribute("aria-current", "page");
  });

  it("is one quiet list of the six places work happens", () => {
    render(Sidebar, { current: "memory" });
    const nav = screen.getByRole("navigation", { name: "All navigation" });
    expect(within(nav).getAllByRole("link").map((a) => a.getAttribute("aria-label")).filter(Boolean)).toEqual([
      "Home", "Chat", "Build", "Design", "Work", "Memory",
    ]);
    expect(within(nav).getByRole("link", { name: "Memory" })).toHaveAttribute("aria-current", "page");
    // No disclosure groups, and no subtitle under the name.
    expect(within(nav).queryByRole("button", { name: "Knowledge" })).toBeNull();
    expect(within(nav).queryByText("Governed agent")).toBeNull();
  });

  // Collapsed used to mean gone. It is a rail now, so every destination the
  // sidebar carries is still reachable without bringing the labels back.
  it("keeps every link reachable at rail width", () => {
    render(Sidebar, { current: "memory", desktopOpen: false });
    const nav = screen.getByRole("navigation", { name: "All navigation" });
    expect(nav).not.toHaveAttribute("inert");
    for (const item of SIDEBAR_GROUPS.flatMap((group) => group.items)) {
      expect(within(nav).getByRole("link", { name: item.label })).toBeInTheDocument();
    }
  });

  // The rail carried two lines of standing prose: where the workspace
  // runs, and which licence the project ships under. Both are facts about the
  // installation, read once and never again, and both were repeated on every
  // page of the product. Locality is on the host panel; the licence is in
  // Settings → Updates with the version and channel it belongs beside.
  it("carries no licence or runtime prose in its footer", () => {
    render(Sidebar, { current: "new-chat" });
    const nav = screen.getByRole("navigation", { name: "All navigation" });
    expect(within(nav).queryByText("Local & loopback-only")).not.toBeInTheDocument();
    expect(within(nav).queryByText("Apache License, Version 2.0")).not.toBeInTheDocument();
  });

  // Design is a Work mode, so it has a permanent row beside its two
  // peers rather than being reachable only from the gear's window.
  it("gives all three Work modes a permanent row", () => {
    render(Sidebar, { current: "design" });
    const nav = screen.getByRole("navigation", { name: "All navigation" });
    for (const label of ["Chat", "Build", "Design"]) {
      expect(within(nav).getByRole("link", { name: label })).toBeInTheDocument();
    }
  });

  // At most two cues say which row is current. The gutter bar, the
  // accent text, the heavier weight and the word "Current" beside the group
  // name are gone; the tinted row and the filled glyph are what is left, and
  // they are the two that survive a rail with no labels.
  it("marks the current row with no more than two cues", () => {
    render(Sidebar, { current: "build" });
    const nav = screen.getByRole("navigation", { name: "All navigation" });
    expect(within(nav).queryByText("Current")).not.toBeInTheDocument();
    const active = within(nav).getByRole("link", { name: "Build" });
    expect(active.className).toContain("active");
    expect(active).toHaveAttribute("aria-current", "page");
  });

  it("closes controlled compact navigation with Escape", async () => {
    const onDrawerClose = vi.fn();
    render(Sidebar, { current: "new-chat", compact: true, drawerOpen: true, onDrawerClose });
    await Promise.resolve();
    await fireEvent.keyDown(document, { key: "Escape" });
    expect(onDrawerClose).toHaveBeenCalledOnce();
  });

  it("removes the closed compact drawer from keyboard navigation", async () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({
        matches: true,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }),
    );
    const { rerender } = render(Sidebar, { current: "new-chat", compact: true, drawerOpen: false });

    const drawer = document.getElementById("all-navigation");
    expect(drawer).not.toBeNull();
    expect((drawer as HTMLElement).inert).toBe(true);
    expect(drawer).toHaveAttribute("aria-hidden", "true");

    await rerender({ current: "new-chat", compact: true, drawerOpen: true });
    expect((drawer as HTMLElement).inert).toBe(false);
    expect(drawer).not.toHaveAttribute("aria-hidden");
  });

  it("does not load or render recent chats in navigation", async () => {
    const fetchMock = stubFetch({});
    render(Sidebar, { current: "new-chat" });
    await Promise.resolve();
    expect(screen.queryByLabelText("Recent chats")).toBeNull();
    const requested = fetchMock.mock.calls.map(([url]) => String(url));
    expect(requested.some((url) => url.startsWith("/api/sessions"))).toBe(false);
    expect(requested.some((url) => url.startsWith("/api/projects"))).toBe(false);
  });
});

// QUI-C06 — the owner's five most recent chats sit under the Chat row.
describe("Sidebar recent chats", () => {
  const thread = (id: string, title: string, updated: string, kind = "chat") => ({
    session_id: id, title, kind, updated_at: updated, turn_count: 1, origin: "web", project_id: null,
    project_name: null, task_id: null, task_status: null, cadence: null, next_run_at: null,
    waiting_on: null, pinned: false, archived: false, tags: [],
  });

  it("lists the five newest chats, and no routine threads", async () => {
    stubFetch({
      "GET /api/work-threads": [
        thread("s1", "Oldest", "2026-10-01T00:00:00Z"),
        thread("s2", "Trip plan", "2026-10-02T00:00:00Z"),
        thread("s3", "Login bug", "2026-10-03T00:00:00Z"),
        thread("s4", "Proposal", "2026-10-04T00:00:00Z"),
        thread("s5", "Week plan", "2026-10-05T00:00:00Z"),
        thread("s6", "Newest", "2026-10-06T00:00:00Z"),
        thread("r1", "Overnight research", "2026-10-07T00:00:00Z", "routine"),
      ],
    });
    render(Sidebar, { current: "home" });
    const list = await screen.findByRole("list", { name: "Recent chats" });
    const links = within(list).getAllByRole("link");
    expect(links.map((link) => link.textContent)).toEqual(["Newest", "Week plan", "Proposal", "Login bug", "Trip plan"]);
    expect(links[0]).toHaveAttribute("href", "#/new-chat?session=s6");
  });

  it("draws no list at rail width", async () => {
    stubFetch({ "GET /api/work-threads": [thread("s1", "Proposal", "2026-10-01T00:00:00Z")] });
    render(Sidebar, { current: "home", desktopOpen: false });
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(screen.queryByRole("list", { name: "Recent chats" })).toBeNull();
  });
});
