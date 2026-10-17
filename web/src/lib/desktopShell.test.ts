import { afterEach, describe, expect, it, vi } from "vitest";

import {
  COMMAND_ROUTES,
  DESKTOP_COMMAND_EVENT,
  type DesktopBridge,
  handleDesktopCommand,
  inDesktopShell,
  startDesktopShell,
  toHex,
} from "./desktopShell";

function fakeBridge(platform = "win32") {
  let listener: ((command: string) => void) | null = null;
  const bridge: DesktopBridge & { emit: (command: string) => void; colours: string[][] } = {
    bridgeVersion: 1,
    platform,
    colours: [],
    onCommand(callback) {
      listener = callback;
      return () => {
        listener = null;
      };
    },
    setTitleBarColours(background, symbol) {
      bridge.colours.push([background, symbol]);
    },
    focusWindow: vi.fn(),
    emit(command) {
      listener?.(command);
    },
  };
  return bridge;
}

afterEach(() => {
  delete window.raikerDesktop;
  delete document.documentElement.dataset.desktopShell;
  window.location.hash = "";
});

describe("desktop shell bridge", () => {
  it("is a no-op in a browser", () => {
    expect(inDesktopShell()).toBe(false);
    startDesktopShell()();
    expect(document.documentElement.dataset.desktopShell).toBeUndefined();
  });

  it("ignores a bridge of another version", () => {
    window.raikerDesktop = { ...fakeBridge(), bridgeVersion: 2 };
    expect(inDesktopShell()).toBe(false);
  });

  it("marks the document with the platform and routes menu commands", () => {
    const bridge = fakeBridge("darwin");
    window.raikerDesktop = bridge;
    const stop = startDesktopShell();
    expect(document.documentElement.dataset.desktopShell).toBe("darwin");
    bridge.emit("go-approvals");
    expect(window.location.hash).toBe("#/approvals");
    stop();
    bridge.emit("go-home");
    expect(window.location.hash).toBe("#/approvals");
  });

  it("raises shell controls as an event for the app", () => {
    const seen: string[] = [];
    const listener = (event: Event) => seen.push((event as CustomEvent<string>).detail);
    window.addEventListener(DESKTOP_COMMAND_EVENT, listener);
    expect(handleDesktopCommand("open-palette")).toBe(true);
    expect(handleDesktopCommand("toggle-navigation")).toBe(true);
    expect(handleDesktopCommand("format-disk")).toBe(false);
    window.removeEventListener(DESKTOP_COMMAND_EVENT, listener);
    expect(seen).toEqual(["open-palette", "toggle-navigation"]);
  });

  it("routes every place command to a real route", () => {
    for (const hash of Object.values(COMMAND_ROUTES)) expect(hash).toMatch(/^#\/[a-z-]+$/);
  });

  it("converts computed colours for the title bar", () => {
    expect(toHex("#12161F")).toBe("#12161f");
    expect(toHex(" rgb(255, 255, 255) ")).toBe("#ffffff");
    expect(toHex("rgba(18 22 31 / 1)")).toBe("#12161f");
    expect(toHex("var(--x)")).toBeNull();
  });
});

describe("window controls", () => {
  it("measures the room the native controls take at the right", async () => {
    const { controlsWidth } = await import("./desktopShell");
    expect(controlsWidth(1440, { x: 0, width: 1327 })).toBe(113);
    expect(controlsWidth(1440, { x: 0, width: 1440 })).toBe(0);
    expect(controlsWidth(800, { x: 0, width: 900 })).toBe(0);
  });
});
