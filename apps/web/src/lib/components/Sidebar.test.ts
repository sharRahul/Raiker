// The full route list lives in the adaptive drawer so every governed route
// stays available when phone and tablet controls take over.
import { fireEvent, render, screen, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import Sidebar from "./Sidebar.svelte";
import { NAV_ITEMS } from "../nav";
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
    for (const item of NAV_ITEMS) {
      expect(within(nav).getByRole("link", { name: item.label })).toBeInTheDocument();
    }
  });

  it("marks the active route for assistive tech", () => {
    render(Sidebar, { current: "observe" });
    const active = within(screen.getByRole("navigation", { name: "All navigation" })).getByRole("link", { name: "Observability" });
    expect(active).toHaveAttribute("aria-current", "page");
  });

  it("keeps Core visible and exposes the other sections as disclosures", () => {
    render(Sidebar, { current: "models" });
    const nav = screen.getByRole("navigation", { name: "All navigation" });
    expect(within(nav).getByRole("link", { name: "Search chats" })).toBeVisible();
    expect(within(nav).getByRole("button", { name: "Manage" })).toHaveAttribute("aria-expanded", "true");
    expect(within(nav).getByRole("button", { name: "Knowledge" })).toHaveAttribute("aria-expanded", "true");
    expect(within(nav).getByRole("link", { name: "Models" })).toHaveAttribute("aria-current", "page");
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

  it("shows the runtime scope and project license in the footer", () => {
    render(Sidebar, { current: "new-chat" });
    const nav = screen.getByRole("navigation", { name: "All navigation" });
    expect(within(nav).getByText("Local & loopback-only")).toBeInTheDocument();
    expect(within(nav).getByText("Apache License, Version 2.0")).toBeInTheDocument();
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
