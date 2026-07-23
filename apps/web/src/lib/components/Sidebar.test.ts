// The full route list lives in the adaptive drawer so every governed route
// stays available when phone and tablet controls take over.
import { fireEvent, render, screen, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import Sidebar from "./Sidebar.svelte";
import { NAV_ITEMS } from "../nav";

afterEach(() => {
  vi.unstubAllGlobals();
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
    render(Sidebar, { current: "sessions" });
    const active = within(screen.getByRole("navigation", { name: "All navigation" })).getByRole("link", { name: "Sessions" });
    expect(active).toHaveAttribute("aria-current", "page");
  });

  it("opens More navigation and closes it with Escape", async () => {
    render(Sidebar, { current: "new-chat" });
    const more = screen.getByRole("button", { name: "More navigation" });
    expect(more).toHaveAttribute("aria-expanded", "false");

    await fireEvent.click(more);
    expect(more).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("navigation", { name: "All navigation" })).toBeInTheDocument();

    await fireEvent.keyDown(window, { key: "Escape" });
    expect(more).toHaveAttribute("aria-expanded", "false");
    expect(more).toHaveFocus();
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
    render(Sidebar, { current: "new-chat" });

    const drawer = document.getElementById("all-navigation");
    expect(drawer).not.toBeNull();
    expect((drawer as HTMLElement).inert).toBe(true);
    expect(drawer).toHaveAttribute("aria-hidden", "true");

    await fireEvent.click(screen.getByRole("button", { name: "More navigation" }));
    expect((drawer as HTMLElement).inert).toBe(false);
    expect(drawer).not.toHaveAttribute("aria-hidden");
  });
});
