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

  it("keeps Core visible and exposes Knowledge as a disclosure", () => {
    render(Sidebar, { current: "memory" });
    const nav = screen.getByRole("navigation", { name: "All navigation" });
    expect(within(nav).getByRole("link", { name: "Threads" })).toBeVisible();
    expect(within(nav).getByRole("button", { name: "Knowledge" })).toHaveAttribute("aria-expanded", "true");
    expect(within(nav).getByRole("link", { name: "Memory" })).toHaveAttribute("aria-current", "page");
    // Manage was a group here and is not one any more.
    expect(within(nav).queryByRole("button", { name: "Manage" })).toBeNull();
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

  it("toggles and persists an inactive navigation group", async () => {
    render(Sidebar, { current: "new-chat" });
    const knowledge = screen.getByRole("button", { name: "Knowledge" });
    expect(knowledge).toHaveAttribute("aria-expanded", "true");
    await fireEvent.click(knowledge);
    expect(knowledge).toHaveAttribute("aria-expanded", "false");
    expect(localStorage.getItem("raiker.navigation.groups")).not.toContain("knowledge");
    await fireEvent.click(knowledge);
    expect(knowledge).toHaveAttribute("aria-expanded", "true");
    expect(localStorage.getItem("raiker.navigation.groups")).toContain("knowledge");
  });

  it("does not offer the Knowledge Map in compact navigation", () => {
    render(Sidebar, { current: "new-chat", compact: true, drawerOpen: true });
    const nav = screen.getByRole("navigation", { name: "All navigation" });
    expect(within(nav).queryByRole("link", { name: "Knowledge Map" })).not.toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Memory" })).toBeInTheDocument();
  });

  // VIS2-02 — the rail carried two lines of standing prose: where the workspace
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

  // VIS2-03 — Design is a Work mode, so it has a permanent row beside its two
  // peers rather than being reachable only from the gear's window.
  it("gives all three Work modes a permanent row", () => {
    render(Sidebar, { current: "design" });
    const nav = screen.getByRole("navigation", { name: "All navigation" });
    for (const label of ["Chat", "Build", "Design"]) {
      expect(within(nav).getByRole("link", { name: label })).toBeInTheDocument();
    }
  });

  // VIS2-08 — at most two cues say which row is current. The gutter bar, the
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
