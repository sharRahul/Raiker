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

  // The strip scrolls sideways when the tabs are wider than the screen. Landing
  // on `#/extensions?tab=plugins` at 390px rendered it at scrollLeft 0 with the
  // selected tab at 365px in a 364px viewport: the Plugins panel under a strip
  // that looked like Hooks was selected, and nothing on screen said otherwise.
  function scrollable(strip: HTMLElement, tabWidth = 200, visible = 364) {
    Object.defineProperty(strip, "clientWidth", { value: visible, configurable: true });
    Object.defineProperty(strip, "scrollWidth", {
      value: tabWidth * TABS.length,
      configurable: true,
    });
    for (const [index, tab] of Array.from(strip.querySelectorAll("button")).entries()) {
      Object.defineProperty(tab, "offsetLeft", { value: index * tabWidth, configurable: true });
      Object.defineProperty(tab, "offsetWidth", { value: tabWidth, configurable: true });
    }
  }

  it("scrolls the selected tab into view when the strip overflows", async () => {
    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;
    const { rerender } = render(TabStrip, {
      props: { tabs: TABS, selected: "overview", onselect: vi.fn(), label: "Sections" },
    });
    scrollable(screen.getByRole("tablist"));
    scrollIntoView.mockClear();

    await rerender({ tabs: TABS, selected: "work", onselect: vi.fn(), label: "Sections" });

    expect(scrollIntoView).toHaveBeenCalledWith({ inline: "nearest", block: "nearest" });
  });

  it("does not scroll a strip that already fits", async () => {
    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;
    const { rerender } = render(TabStrip, {
      props: { tabs: TABS, selected: "overview", onselect: vi.fn(), label: "Sections" },
    });
    // jsdom reports 0 for both, so `scrollWidth <= clientWidth` holds: a strip
    // with nothing to scroll must not fight the page for scroll position.
    scrollIntoView.mockClear();

    await rerender({ tabs: TABS, selected: "work", onselect: vi.fn(), label: "Sections" });

    expect(scrollIntoView).not.toHaveBeenCalled();
  });
});
