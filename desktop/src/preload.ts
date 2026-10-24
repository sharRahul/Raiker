// SPDX-License-Identifier: Apache-2.0
/**
 * The whole of what the Raiker page can ask of the desktop shell.
 *
 * Runs sandboxed with context isolation, so the page never touches Node,
 * Electron or `ipcRenderer` — it sees one frozen object, `window.raikerDesktop`,
 * with three narrow operations. Nothing here reads files, starts processes or
 * reaches the network: the page keeps talking to its host over HTTP exactly as
 * it does in a browser, so governance stays on the server.
 *
 * A sandboxed preload cannot `require` sibling modules, so the command names and
 * channels are repeated from `commands.ts`; `test/commands.test.ts` fails if the
 * two lists drift.
 */
import { contextBridge, ipcRenderer, type IpcRendererEvent } from "electron";

const COMMANDS: readonly string[] = [
  "new-chat",
  "open-build",
  "open-design",
  "go-home",
  "go-tasks",
  "go-approvals",
  "open-settings",
  "open-palette",
  "toggle-navigation",
  "open-guide",
];
const COMMAND_CHANNEL = "raiker:command";
const TITLE_BAR_CHANNEL = "raiker:title-bar";
const FOCUS_CHANNEL = "raiker:focus";
const QUIT_FOR_UPDATE_CHANNEL = "raiker:quit-for-update";
const ATTENTION_CHANNEL = "raiker:attention";
const TRAY_PREFERENCE_CHANNEL = "raiker:tray-preference";
const OPEN_WINDOW_CHANNEL = "raiker:open-window";
const CLOSE_WINDOW_CHANNEL = "raiker:close-window";
const HEX = /^#[0-9a-fA-F]{6}$/;

const bridge = Object.freeze({
  bridgeVersion: 1,
  platform: process.platform,
  /** Run `callback` for each menu command; returns the unsubscribe. */
  onCommand(callback: (command: string) => void): () => void {
    const listener = (_event: IpcRendererEvent, command: unknown) => {
      if (typeof command === "string" && COMMANDS.includes(command)) callback(command);
    };
    ipcRenderer.on(COMMAND_CHANNEL, listener);
    return () => {
      ipcRenderer.removeListener(COMMAND_CHANNEL, listener);
    };
  },
  /** Match the native window controls to the page's theme. */
  setTitleBarColours(background: string, symbol: string): void {
    if (HEX.test(String(background)) && HEX.test(String(symbol))) {
      ipcRenderer.send(TITLE_BAR_CHANNEL, { background, symbol });
    }
  },
  /** Bring this window forward — for a clicked notification. */
  focusWindow(): void {
    ipcRenderer.send(FOCUS_CHANNEL);
  },
  /**
   * DIST-10 — close this window so a verified update can start the new version.
   * It quits only the window; the host is already stopping on its own route.
   */
  quitForUpdate(): void {
    ipcRenderer.send(QUIT_FOR_UPDATE_CHANNEL);
  },
  /** QUI-F11 — how many decisions wait, for the tray's dot. A count, nothing else. */
  setAttention(count: number): void {
    if (Number.isInteger(count) && count >= 0) ipcRenderer.send(ATTENTION_CHANNEL, count);
  },
  /** QUI-F11 — keep running in the tray when the window is closed. */
  setMinimizeToTray(enabled: boolean): void {
    ipcRenderer.send(TRAY_PREFERENCE_CHANNEL, enabled === true);
  },
  /** QUI-F13 — open one of Raiker's own places (a route hash) in a new window. */
  openWindow(hash: string): void {
    if (typeof hash === "string" && hash.startsWith("#/")) ipcRenderer.send(OPEN_WINDOW_CHANNEL, hash);
  },
  /** QUI-F01 — close this window (Quick Entry's Esc and Send). */
  closeWindow(): void {
    ipcRenderer.send(CLOSE_WINDOW_CHANNEL);
  },
});

contextBridge.exposeInMainWorld("raikerDesktop", bridge);
