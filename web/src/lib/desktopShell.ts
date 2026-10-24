/**
 * Raiker in its desktop window.
 *
 * The Electron shell (`desktop/`) exposes one small bridge, `window.raikerDesktop`,
 * and nothing else: the page keeps talking to its host over HTTP exactly as it
 * does in a browser, so every action still goes through the server's
 * governance. This module is the page's half of that bridge. In a browser the
 * bridge is absent and every function here is a no-op, so the same build serves
 * both.
 *
 * Three things change in the window:
 *
 * * **Chrome.** The window has no native title bar; the top bar is the drag
 *   region and the platform's window controls sit over its end
 *   (`data-desktop-shell` on `<html>` drives the CSS in `app.css`).
 * * **Commands.** The native menu and its shortcuts send a command name; the
 *   page answers with the same route change or control a click would make.
 * * **Colours.** The native window controls follow the page's theme.
 */

/** The menu commands the shell can send; `desktop/src/commands.ts` holds the same list. */
export type DesktopCommand =
  | "new-chat"
  | "open-build"
  | "open-design"
  | "go-home"
  | "go-tasks"
  | "go-approvals"
  | "open-settings"
  | "open-palette"
  | "toggle-navigation"
  | "open-guide";

export interface DesktopBridge {
  readonly bridgeVersion: number;
  readonly platform: string;
  onCommand(callback: (command: string) => void): () => void;
  setTitleBarColours(background: string, symbol: string): void;
  focusWindow(): void;
  /** DIST-10 — absent from shells built before it; check before calling. */
  quitForUpdate?(): void;
  /** QUI-F11 — the tray's attention dot; absent from older shells. */
  setAttention?(count: number): void;
  /** QUI-F11 — keep running in the tray when the window closes. */
  setMinimizeToTray?(enabled: boolean): void;
  /** QUI-F13 — open one of Raiker's own places in a new window. */
  openWindow?(hash: string): void;
  /** QUI-F01 — close this window (Quick Entry). */
  closeWindow?(): void;
}

declare global {
  interface Window {
    raikerDesktop?: DesktopBridge;
  }
}

/** Commands that are a place: the route hash they open. */
export const COMMAND_ROUTES: Partial<Record<DesktopCommand, string>> = {
  "new-chat": "#/new-chat",
  "open-build": "#/build",
  "open-design": "#/design",
  "go-home": "#/home",
  "go-tasks": "#/tasks",
  "go-approvals": "#/approvals",
  "open-settings": "#/settings",
  "open-guide": "#/guide",
};

/** Commands that are a shell control, raised as this event for `App.svelte`. */
export const DESKTOP_COMMAND_EVENT = "raiker:desktop-command";

export function desktopBridge(): DesktopBridge | null {
  if (typeof window === "undefined") return null;
  const bridge = window.raikerDesktop;
  return bridge !== undefined && bridge.bridgeVersion === 1 ? bridge : null;
}

/** True when this page is running in Raiker's desktop window. */
export function inDesktopShell(): boolean {
  return desktopBridge() !== null;
}

/** Act on one command; returns whether it was recognised. */
export function handleDesktopCommand(command: string): boolean {
  const route = COMMAND_ROUTES[command as DesktopCommand];
  if (route !== undefined) {
    window.location.hash = route;
    return true;
  }
  if (command === "open-palette" || command === "toggle-navigation") {
    window.dispatchEvent(new CustomEvent(DESKTOP_COMMAND_EVENT, { detail: command }));
    return true;
  }
  return false;
}

const HEX = /^#[0-9a-fA-F]{6}$/;

/** `rgb(…)`/`#rrggbb` as `#rrggbb`, or null for anything else. */
export function toHex(colour: string): string | null {
  const value = colour.trim();
  if (HEX.test(value)) return value.toLowerCase();
  const match = /^rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)/.exec(value);
  if (match === null) return null;
  return `#${match.slice(1, 4).map((part) => Number(part).toString(16).padStart(2, "0")).join("")}`;
}

/** Tell the shell the top bar's colours, so the window controls match it. */
export function syncTitleBar(bridge: DesktopBridge): void {
  const style = getComputedStyle(document.documentElement);
  const background = toHex(style.getPropertyValue("--surface"));
  const symbol = toHex(style.getPropertyValue("--text-2"));
  if (background !== null && symbol !== null) bridge.setTitleBarColours(background, symbol);
}

interface WindowControlsOverlay extends EventTarget {
  readonly visible: boolean;
  getTitlebarAreaRect(): DOMRect;
}

/**
 * How wide the native window controls are at the top bar's right end.
 *
 * Read from the Window Controls Overlay API rather than CSS
 * `env(titlebar-area-*)`: Chromium does not re-evaluate those for an existing
 * element when the window is resized, so a top bar laid out at one width kept
 * the controls' room for another (found in the 2026-10-17 desktop round).
 */
export function controlsWidth(viewportWidth: number, area: { x: number; width: number }): number {
  return Math.max(0, Math.round(viewportWidth - area.x - area.width));
}

function watchWindowControls(root: HTMLElement): () => void {
  const overlay = (navigator as Navigator & { windowControlsOverlay?: WindowControlsOverlay })
    .windowControlsOverlay;
  if (overlay === undefined) return () => {};
  const sync = () => {
    const width = overlay.visible ? controlsWidth(window.innerWidth, overlay.getTitlebarAreaRect()) : 0;
    root.style.setProperty("--desktop-controls-w", `${width}px`);
  };
  overlay.addEventListener("geometrychange", sync);
  window.addEventListener("resize", sync);
  sync();
  return () => {
    overlay.removeEventListener("geometrychange", sync);
    window.removeEventListener("resize", sync);
  };
}

/**
 * Mark the document for the desktop window and wire the bridge.
 *
 * Returns the teardown. Called once from `main.ts` before the app mounts, so
 * the first frame already has the window chrome rather than jumping into it.
 */
export function startDesktopShell(): () => void {
  const bridge = desktopBridge();
  if (bridge === null) return () => {};
  const root = document.documentElement;
  root.dataset.desktopShell = ["darwin", "win32", "linux"].includes(bridge.platform) ? bridge.platform : "linux";
  const unsubscribe = bridge.onCommand((command) => {
    handleDesktopCommand(command);
  });
  const sync = () => syncTitleBar(bridge);
  // The theme is an attribute on <html> or the OS preference; follow both.
  const themeWatch = new MutationObserver(sync);
  themeWatch.observe(root, { attributes: true, attributeFilter: ["data-theme"] });
  const scheme = window.matchMedia?.("(prefers-color-scheme: dark)");
  scheme?.addEventListener("change", sync);
  requestAnimationFrame(sync);
  const stopControls = watchWindowControls(root);
  return () => {
    stopControls();
    unsubscribe();
    themeWatch.disconnect();
    scheme?.removeEventListener("change", sync);
  };
}

/**
 * DIST-10 — let a verified update replace this window. In a browser, or in a
 * shell built before the operation existed, this does nothing.
 */
export function quitDesktopForUpdate(): void {
  const bridge = desktopBridge();
  if (bridge !== null && typeof bridge.quitForUpdate === "function") bridge.quitForUpdate();
}
