// SPDX-License-Identifier: Apache-2.0
/**
 * Raiker's desktop window.
 *
 * The shell is deliberately thin. Raiker's host — the governed runtime, its
 * authentication, its storage and every approval — is the same local service
 * the browser talks to; this process gives it a native window, menu, shortcuts
 * and notifications, and nothing in it can act on the workspace. The Hermes
 * Agent desktop app takes the same shape: an Electron window over the agent's
 * own core, sharing its sessions and configuration rather than copying them.
 *
 * What the window may show is fixed at start: one loopback Raiker origin.
 * Navigation elsewhere opens the owner's browser, another local Raiker instance
 * opens its own window, and everything else is refused (`origin.ts`).
 */
import { join } from "node:path";
import { existsSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";

import {
  app,
  BrowserWindow,
  ipcMain,
  Menu,
  nativeTheme,
  Notification,
  screen,
  session,
  shell,
  type BrowserWindowConstructorOptions,
  type WebContents,
} from "electron";

import { parseShellArgs } from "./args";
import { CHANNELS, isHexColour, type ShellCommand } from "./commands";
import { resolveHostCommand, startHost } from "./host";
import { menuTemplate } from "./menu";
import { classifyNavigation, decidePermission, loopbackOrigin } from "./origin";
import { loadState, MIN_SIZE, saveState } from "./windowState";

/** Must match `--topbar-h` in `web/src/app.css`: the overlay sits in the top bar. */
const TITLE_BAR_HEIGHT = 56;
const THEME = {
  light: { background: "#FFFFFF", symbol: "#475569", window: "#F8FAFC" },
  dark: { background: "#12161F", symbol: "#94A3B8", window: "#0B0D10" },
};

const args = parseShellArgs(process.argv.slice(1), process.env);
const stateFile = () => join(app.getPath("userData"), "window-state.json");
const shellFile = () => join(app.getPath("userData"), "shell.json");

/** The Raiker origin each window was opened for; status pages have none. */
const origins = new Map<number, string>();
let mainWindow: BrowserWindow | null = null;
let hostUrl: string | null = null;

app.setName("Raiker");
// A separate profile for a second copy of the shell — tests, or an owner who
// keeps two Raiker installs apart. Window geometry and the one-time notice live
// there; nothing from the workspace does.
if (process.env.RAIKER_DESKTOP_USER_DATA) app.setPath("userData", process.env.RAIKER_DESKTOP_USER_DATA);
if (process.platform === "win32") app.setAppUserModelId("org.raiker.desktop");

if (!app.requestSingleInstanceLock()) {
  // One window per signed-in desktop session. A second launch — a dock click, a
  // menu entry, the tray's Open Raiker — brings the existing window forward.
  app.quit();
} else {
  app.on("second-instance", () => showMainWindow());
  void app.whenReady().then(start);
}

function iconPath(): string | undefined {
  const candidates = [
    join(process.resourcesPath ?? "", "raiker-icon.png"),
    join(__dirname, "..", "..", "raiker", "assets", "raiker-icon.png"),
  ];
  return candidates.find((candidate) => existsSync(candidate));
}

function palette() {
  return nativeTheme.shouldUseDarkColors ? THEME.dark : THEME.light;
}

function readShellState(): Record<string, unknown> {
  try {
    const value: unknown = JSON.parse(readFileSync(shellFile(), "utf-8"));
    return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

function writeShellState(update: Record<string, unknown>): void {
  try {
    mkdirSync(app.getPath("userData"), { recursive: true });
    writeFileSync(shellFile(), `${JSON.stringify({ ...readShellState(), ...update })}\n`, "utf-8");
  } catch {
    // A remembered preference is a convenience, never a reason to fail.
  }
}

function originOf(contents: WebContents): string | null {
  return origins.get(contents.id) ?? null;
}

function hardenSession(): void {
  const defaults = session.defaultSession;
  defaults.setPermissionRequestHandler((contents, permission, callback, details) => {
    const origin = originOf(contents);
    const media = "mediaTypes" in details && Array.isArray(details.mediaTypes) ? details.mediaTypes : [];
    callback(origin !== null && decidePermission(permission, details.requestingUrl ?? contents.getURL(), origin, media));
  });
  defaults.setPermissionCheckHandler((contents, permission, requestingOrigin) => {
    const origin = contents === null ? null : originOf(contents);
    return origin !== null && decidePermission(permission, requestingOrigin, origin);
  });
  // Downloads go where the owner says, through the platform's own dialog.
  defaults.on("will-download", (_event, item) => {
    item.setSaveDialogOptions({ title: "Save from Raiker" });
  });
}

function route(contents: WebContents, target: string): "allow" | "handled" {
  const origin = originOf(contents);
  if (origin === null) return "handled";
  const decision = classifyNavigation(target, origin);
  if (decision === "same-window") return "allow";
  if (decision === "external") void shell.openExternal(target);
  if (decision === "app-window") openWindow(target, false);
  return "handled";
}

app.on("web-contents-created", (_event, contents) => {
  contents.on("will-attach-webview", (event) => event.preventDefault());
  contents.setWindowOpenHandler(({ url }) => {
    route(contents, url);
    return { action: "deny" };
  });
  contents.on("will-navigate", (event) => {
    if (route(contents, event.url) !== "allow") event.preventDefault();
  });
  contents.on("will-redirect", (event) => {
    if (route(contents, event.url) !== "allow") event.preventDefault();
  });
});

function windowOptions(main: boolean): BrowserWindowConstructorOptions {
  const colours = palette();
  const geometry = main
    ? loadState(stateFile(), screen.getAllDisplays().map((display) => display.workArea))
    : { bounds: { width: 1180, height: 780 }, maximized: false };
  const chrome: BrowserWindowConstructorOptions =
    process.platform === "darwin"
      ? { titleBarStyle: "hiddenInset", trafficLightPosition: { x: 18, y: 20 } }
      : {
          titleBarStyle: "hidden",
          titleBarOverlay: { color: colours.background, symbolColor: colours.symbol, height: TITLE_BAR_HEIGHT },
        };
  return {
    ...geometry.bounds,
    minWidth: MIN_SIZE.width,
    minHeight: MIN_SIZE.height,
    show: false,
    title: "Raiker",
    backgroundColor: colours.window,
    icon: iconPath(),
    ...chrome,
    webPreferences: {
      preload: join(__dirname, "preload.js"),
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
      nodeIntegrationInWorker: false,
      webviewTag: false,
      navigateOnDragDrop: false,
      spellcheck: true,
    },
  };
}

function createWindow(main: boolean): BrowserWindow {
  const window = new BrowserWindow(windowOptions(main));
  const contentsId = window.webContents.id;
  window.once("ready-to-show", () => {
    if (main && loadState(stateFile(), []).maximized) window.maximize();
    window.show();
  });
  window.webContents.on("did-fail-load", (_event, code, description, failedUrl, isMainFrame) => {
    if (!isMainFrame || code === -3) return; // -3: aborted by a newer navigation
    showStatus(window, "error", `Raiker did not answer at ${failedUrl} (${description}). Is the host still running?`);
  });
  if (main) {
    window.on("close", () => {
      saveState(stateFile(), { bounds: window.getNormalBounds(), maximized: window.isMaximized() });
      announceBackground();
    });
    window.on("closed", () => {
      mainWindow = null;
    });
  }
  window.on("closed", () => origins.delete(contentsId));
  return window;
}

/** Point `window` at a Raiker host; its origin becomes the only one it may show. */
function showRaiker(window: BrowserWindow, url: string): void {
  const origin = loopbackOrigin(url);
  if (origin === null) return;
  origins.set(window.webContents.id, origin);
  void window.loadURL(url);
}

function openWindow(url: string, main: boolean): BrowserWindow {
  const window = createWindow(main);
  showRaiker(window, url);
  return window;
}

/** A local status page — starting, or why the window cannot show Raiker. */
function showStatus(window: BrowserWindow, state: "starting" | "error", message: string): void {
  origins.delete(window.webContents.id);
  void window.loadFile(join(__dirname, "..", "static", "status.html"), { query: { state, message } });
  if (!window.isVisible()) window.show();
}

/**
 * Say once that closing the window did not stop Raiker.
 *
 * The host is a service: scheduled work, reminders and approvals carry on. An
 * owner who closes the window expecting everything to stop deserves to be told
 * the first time, not to discover it from a notification an hour later.
 */
function announceBackground(): void {
  if (hostUrl === null || readShellState().backgroundNoticeShown === true) return;
  if (!Notification.isSupported()) return;
  new Notification({
    title: "Raiker is still running",
    body: "Scheduled work and approvals continue. Open Raiker again from your applications menu or the tray; quit it from Host.",
    silent: true,
  }).show();
  writeShellState({ backgroundNoticeShown: true });
}

function showMainWindow(): void {
  if (mainWindow === null) {
    if (hostUrl !== null) mainWindow = openWindow(hostUrl, true);
    return;
  }
  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.show();
  mainWindow.focus();
}

function sendCommand(command: ShellCommand): void {
  const target = BrowserWindow.getFocusedWindow() ?? mainWindow;
  if (target !== null && originOf(target.webContents) !== null) target.webContents.send(CHANNELS.command, command);
}

function installMenu(): void {
  const template = menuTemplate(process.platform, app.isPackaged, {
    send: sendCommand,
    openInBrowser: () => {
      const target = BrowserWindow.getFocusedWindow() ?? mainWindow;
      const origin = target === null ? null : originOf(target.webContents);
      if (origin !== null) void shell.openExternal(`${origin}/`);
    },
  });
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

function installIpc(): void {
  ipcMain.on(CHANNELS.titleBar, (event, colours: unknown) => {
    if (originOf(event.sender) === null || process.platform === "darwin") return;
    const value = (colours ?? {}) as Record<string, unknown>;
    if (!isHexColour(value.background) || !isHexColour(value.symbol)) return;
    BrowserWindow.fromWebContents(event.sender)?.setTitleBarOverlay({
      color: value.background,
      symbolColor: value.symbol,
      height: TITLE_BAR_HEIGHT,
    });
  });
  ipcMain.on(CHANNELS.quitForUpdate, (event) => {
    // DIST-10 — the host has handed a verified update to its helper and is
    // stopping. The new version starts its own window; this one must release
    // the single-instance lock first, or the new window would only focus it.
    if (originOf(event.sender) === null) return;
    setTimeout(() => app.quit(), 1500);
  });
  ipcMain.on(CHANNELS.focus, (event) => {
    if (originOf(event.sender) === null) return;
    const window = BrowserWindow.fromWebContents(event.sender);
    if (window === null) return;
    if (window.isMinimized()) window.restore();
    window.show();
    window.focus();
  });
}

async function start(): Promise<void> {
  hardenSession();
  installMenu();
  installIpc();

  if (args.rejectedUrl !== null) {
    mainWindow = createWindow(true);
    showStatus(mainWindow, "error", `${args.rejectedUrl} is not a Raiker address on this computer, so the window will not open it.`);
    return;
  }
  if (args.url !== null) {
    hostUrl = args.url;
    mainWindow = openWindow(args.url, true);
    return;
  }

  const command = resolveHostCommand({
    explicit: args.hostCommand,
    resourcesPath: process.resourcesPath,
    platform: process.platform,
    packaged: app.isPackaged,
  });
  mainWindow = createWindow(true);
  if (command === null) {
    showStatus(mainWindow, "error", "No Raiker host was found to start. From a source checkout, run raiker-app.");
    return;
  }
  showStatus(mainWindow, "starting", "Starting Raiker…");
  try {
    const ready = await startHost(command, join(app.getPath("temp"), `raiker-ready-${process.pid}.json`));
    hostUrl = ready.url;
    // The same window goes from "Starting Raiker" to Raiker, without a flash.
    if (mainWindow !== null) showRaiker(mainWindow, ready.url);
    else mainWindow = openWindow(ready.url, true);
  } catch (error) {
    if (mainWindow !== null) showStatus(mainWindow, "error", error instanceof Error ? error.message : String(error));
  }
}

app.on("activate", () => showMainWindow());

app.on("window-all-closed", () => {
  // The host keeps running either way. On macOS the app stays in the Dock, as
  // every Mac app does; elsewhere the window was the app, so it exits.
  if (process.platform !== "darwin") app.quit();
});
