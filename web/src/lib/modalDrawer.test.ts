import { afterEach, describe, expect, it, vi } from "vitest";
import { activateModalDrawer } from "./modalDrawer";

afterEach(() => { document.body.replaceChildren(); document.body.style.overflow = ""; });

describe("modal drawer", () => {
  it("traps focus, makes the background inert, and restores state", async () => {
    const trigger = document.body.appendChild(document.createElement("button"));
    const background = document.body.appendChild(document.createElement("main"));
    const drawer = document.body.appendChild(document.createElement("aside"));
    drawer.tabIndex = -1;
    const first = drawer.appendChild(document.createElement("button"));
    const last = drawer.appendChild(document.createElement("button"));
    const dismiss = vi.fn();
    trigger.focus();
    const cleanup = activateModalDrawer({ id: "navigation", container: drawer, returnFocusTo: trigger, backgroundElements: [background], onDismiss: dismiss });
    await Promise.resolve();
    expect(first).toHaveFocus();
    expect(background.inert).toBe(true);
    last.focus();
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", bubbles: true, cancelable: true }));
    expect(first).toHaveFocus();
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    expect(dismiss).toHaveBeenCalledOnce();
    cleanup();
    expect(background.inert).toBe(false);
    expect(trigger).toHaveFocus();
  });

  it("supports no-restore cleanup and replaces an active drawer", () => {
    const firstDrawer = document.body.appendChild(document.createElement("aside"));
    const secondDrawer = document.body.appendChild(document.createElement("aside"));
    const dismissFirst = vi.fn();
    const firstCleanup = activateModalDrawer({ id: "navigation", container: firstDrawer, returnFocusTo: null, backgroundElements: [], onDismiss: dismissFirst });
    const secondCleanup = activateModalDrawer({ id: "build-background", container: secondDrawer, returnFocusTo: null, backgroundElements: [], onDismiss: vi.fn() });
    expect(dismissFirst).toHaveBeenCalledOnce();
    firstCleanup(false);
    secondCleanup(false);
  });
});
