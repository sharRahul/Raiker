// The sidebar is the primary navigation at every breakpoint: on narrow
// screens it collapses to an icon rail, so every link must keep an accessible
// label that does not depend on the visible text.
import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import Sidebar from "./Sidebar.svelte";
import { NAV_ITEMS } from "../nav";

describe("Sidebar navigation", () => {
  it("labels every route link so the mobile icon rail stays navigable", () => {
    render(Sidebar, { current: "new-chat" });
    const nav = screen.getByRole("navigation", { name: "Primary" });
    expect(nav).toBeInTheDocument();
    for (const item of NAV_ITEMS) {
      expect(screen.getByRole("link", { name: item.label })).toBeInTheDocument();
    }
  });

  it("marks the active route for assistive tech", () => {
    render(Sidebar, { current: "sessions" });
    const active = screen.getByRole("link", { name: "Sessions" });
    expect(active).toHaveAttribute("aria-current", "page");
  });
});
