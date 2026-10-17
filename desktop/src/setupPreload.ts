// SPDX-License-Identifier: Apache-2.0
/**
 * What the Setup page can ask of the shell — and nothing more.
 *
 * The Setup window shows a page packaged inside the application, not a Raiker
 * origin, so it gets its own bridge instead of `window.raikerDesktop`: one way
 * to hear progress, and one way to ask for a named action (begin, retry, open
 * Raiker, show the logs, quit). The shell ignores any other action, and any
 * message not from its Setup window.
 *
 * A sandboxed preload cannot `require` sibling modules, so the channel and
 * action names repeat `setup.ts`; `test/setup.test.ts` fails if they drift.
 */
import { contextBridge, ipcRenderer, type IpcRendererEvent } from "electron";

const EVENT_CHANNEL = "raiker-setup:event";
const ACTION_CHANNEL = "raiker-setup:action";
const ACTIONS: readonly string[] = ["start", "retry", "open", "logs", "quit"];

contextBridge.exposeInMainWorld(
  "raikerSetup",
  Object.freeze({
    onEvent(listener: (event: unknown) => void): void {
      ipcRenderer.on(EVENT_CHANNEL, (_event: IpcRendererEvent, payload: unknown) => listener(payload));
    },
    send(action: string): void {
      if (ACTIONS.includes(action)) ipcRenderer.send(ACTION_CHANNEL, action);
    },
  }),
);
