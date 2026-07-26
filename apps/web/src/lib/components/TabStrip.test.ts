// The hubs put several destinations behind one route, so the tab strip has to
// carry the full ARIA tabs contract: roving tabindex, arrow/Home/End movement,
// and a selection that the URL owns rather than hidden client state.
import { render, screen } from "@testing-library/svelte";
import { fireEvent } from "@testing-library/dom";
import { describe, expect, it, vi } from "vitest";
import TabStrip from "./TabStrip.svelte";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "activity", label: "Audit log" },
  { id: "work", label: "Work in action", badge: 3 },
];

function setup(selected = "overview") {
  const onselect = vi.fn();
  render(TabStrip, { props: { tabs: TABS, selected, onselect, label: "Sections" } });
  return onselect;
}

describe("TabStrip", () => {
  it("keeps only the selected tab in the tab order", () => {
    setup();
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("tab", { name: "Audit log" })).toHaveAttribute("tabindex", "-1");
  });

  it("points each tab at the panel it controls", () => {
    setup();
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute(
      "aria-controls",
      "panel-overview",
    );
  });

  it("moves selection with the arrow keys", async () => {
    const onselect = setup();
    await fireEvent.keyDown(screen.getByRole("tab", { name: "Overview" }), { key: "ArrowRight" });
    expect(onselect).toHaveBeenCalledWith("activity");

    await fireEvent.keyDown(screen.getByRole("tab", { name: "Overview" }), { key: "ArrowLeft" });
    expect(onselect).toHaveBeenCalledWith("work");
  });

  it("jumps to the ends with Home and End", async () => {
    const onselect = setup("activity");
    await fireEvent.keyDown(screen.getByRole("tab", { name: "Audit log" }), { key: "End" });
    expect(onselect).toHaveBeenCalledWith("work");

    await fireEvent.keyDown(screen.getByRole("tab", { name: "Audit log" }), { key: "Home" });
    expect(onselect).toHaveBeenCalledWith("overview");
  });

  it("ignores keys that are not part of the tabs pattern", async () => {
    const onselect = setup();
    await fireEvent.keyDown(screen.getByRole("tab", { name: "Overview" }), { key: "a" });
    expect(onselect).not.toHaveBeenCalled();
  });

  it("shows a count only when a tab has something actionable", () => {
    setup();
    expect(screen.getByRole("tab", { name: /work in action 3/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveTextContent(/^Overview$/);
  });
});
