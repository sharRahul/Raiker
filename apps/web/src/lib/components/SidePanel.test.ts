// The inspector panel is the shared detail surface. It is a complementary
// landmark rather than a modal, so it must move focus in on open, return focus
// on close, and close on Escape — without trapping the keyboard away from the
// list it sits beside.
import { render, screen } from "@testing-library/svelte";
import { fireEvent } from "@testing-library/dom";
import { describe, expect, it, vi } from "vitest";
import SidePanelHarness from "./SidePanelHarness.test.svelte";

describe("SidePanel", () => {
  it("is a labelled complementary landmark, not a modal dialog", async () => {
    render(SidePanelHarness, { props: { open: true } });
    const panel = await screen.findByRole("complementary", { name: "Model detail" });
    expect(panel).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("renders nothing while closed", () => {
    render(SidePanelHarness, { props: { open: false } });
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
  });

  it("moves focus to its close control when it opens", async () => {
    render(SidePanelHarness, { props: { open: true } });
    const close = await screen.findByRole("button", { name: "Close details" });
    await vi.waitFor(() => expect(document.activeElement).toBe(close));
  });

  it("closes on Escape", async () => {
    const onclose = vi.fn();
    render(SidePanelHarness, { props: { open: true, onclose } });
    await screen.findByRole("complementary");
    await fireEvent.keyDown(window, { key: "Escape" });
    expect(onclose).toHaveBeenCalledTimes(1);
  });

  it("ignores other keys", async () => {
    const onclose = vi.fn();
    render(SidePanelHarness, { props: { open: true, onclose } });
    await screen.findByRole("complementary");
    await fireEvent.keyDown(window, { key: "Enter" });
    expect(onclose).not.toHaveBeenCalled();
  });

  it("still opens where the DOM has no scrollIntoView", async () => {
    // jsdom does not implement scrollIntoView, and neither do some embedded
    // browsers. Opening the panel must not throw past the focus move.
    expect(Element.prototype.scrollIntoView).toBeUndefined();
    render(SidePanelHarness, { props: { open: true, scrollIntoViewOnOpen: true } });
    const close = await screen.findByRole("button", { name: "Close details" });
    await vi.waitFor(() => expect(document.activeElement).toBe(close));
  });

  it("scrolls itself into view when asked and the DOM supports it", async () => {
    const scrollIntoView = vi.fn();
    Object.defineProperty(Element.prototype, "scrollIntoView", {
      value: scrollIntoView,
      configurable: true,
      writable: true,
    });
    try {
      render(SidePanelHarness, { props: { open: true, scrollIntoViewOnOpen: true } });
      await screen.findByRole("complementary");
      await vi.waitFor(() => expect(scrollIntoView).toHaveBeenCalledWith({ block: "nearest" }));
    } finally {
      Reflect.deleteProperty(Element.prototype, "scrollIntoView");
    }
  });

  it("does not scroll when the caller did not ask for it", async () => {
    const scrollIntoView = vi.fn();
    Object.defineProperty(Element.prototype, "scrollIntoView", {
      value: scrollIntoView,
      configurable: true,
      writable: true,
    });
    try {
      render(SidePanelHarness, { props: { open: true } });
      await screen.findByRole("complementary");
      await vi.waitFor(() =>
        expect(screen.getByRole("button", { name: "Close details" })).toBeInTheDocument(),
      );
      expect(scrollIntoView).not.toHaveBeenCalled();
    } finally {
      Reflect.deleteProperty(Element.prototype, "scrollIntoView");
    }
  });

  it("shows its subtitle and footer content", async () => {
    render(SidePanelHarness, { props: { open: true } });
    expect(await screen.findByText("local-default")).toBeInTheDocument();
    expect(screen.getByText("Panel body")).toBeInTheDocument();
  });
});
