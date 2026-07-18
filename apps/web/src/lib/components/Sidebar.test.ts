// The full route list lives in the adaptive drawer so every governed route
// stays available when phone and tablet controls take over.
import { fireEvent, render, screen, within } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import Sidebar from "./Sidebar.svelte";
import { NAV_ITEMS } from "../nav";

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
});
