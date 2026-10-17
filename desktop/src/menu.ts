// SPDX-License-Identifier: Apache-2.0
/**
 * The application menu, as data.
 *
 * Built as a plain template so the shortcuts and their commands can be tested
 * without starting Electron. Every Raiker-specific item sends a
 * {@link ShellCommand} to the page; the rest are Electron's standard roles, so
 * copy, paste, zoom and full screen behave the way each platform expects.
 */
import type { MenuItemConstructorOptions } from "electron";

import type { ShellCommand } from "./commands";

export interface MenuHandlers {
  send: (command: ShellCommand) => void;
  openInBrowser: () => void;
}

export function menuTemplate(
  platform: NodeJS.Platform,
  packaged: boolean,
  handlers: MenuHandlers,
): MenuItemConstructorOptions[] {
  const mac = platform === "darwin";
  const go = (label: string, command: ShellCommand, accelerator?: string): MenuItemConstructorOptions => ({
    label,
    ...(accelerator !== undefined ? { accelerator } : {}),
    click: () => handlers.send(command),
  });

  const appMenu: MenuItemConstructorOptions[] = mac
    ? [
        {
          label: "Raiker",
          submenu: [
            { role: "about" },
            { type: "separator" },
            go("Settings…", "open-settings", "CmdOrCtrl+,"),
            { type: "separator" },
            { role: "hide" },
            { role: "hideOthers" },
            { role: "unhide" },
            { type: "separator" },
            { role: "quit", label: "Close Raiker window" },
          ],
        },
      ]
    : [];

  return [
    ...appMenu,
    {
      label: "File",
      submenu: [
        go("New chat", "new-chat", "CmdOrCtrl+N"),
        go("Build", "open-build", "CmdOrCtrl+Shift+B"),
        go("Design", "open-design", "CmdOrCtrl+Shift+D"),
        { type: "separator" },
        ...(mac ? [] : [go("Settings…", "open-settings", "CmdOrCtrl+,"), { type: "separator" } as const]),
        { label: "Open in browser", click: handlers.openInBrowser },
        { type: "separator" },
        mac ? { role: "close" } : { role: "quit", label: "Close Raiker window" },
      ],
    },
    { role: "editMenu" },
    {
      label: "View",
      submenu: [
        go("Command palette", "open-palette", "CmdOrCtrl+K"),
        go("Toggle navigation", "toggle-navigation", "CmdOrCtrl+\\"),
        { type: "separator" },
        { role: "reload" },
        ...(packaged ? [] : [{ role: "toggleDevTools" } as const]),
        { type: "separator" },
        { role: "resetZoom" },
        { role: "zoomIn" },
        { role: "zoomOut" },
        { type: "separator" },
        { role: "togglefullscreen" },
      ],
    },
    {
      label: "Go",
      submenu: [
        go("Home", "go-home", "CmdOrCtrl+1"),
        go("Chat", "new-chat", "CmdOrCtrl+2"),
        go("Tasks", "go-tasks", "CmdOrCtrl+3"),
        go("Approvals", "go-approvals", "CmdOrCtrl+4"),
      ],
    },
    { role: "windowMenu" },
    {
      role: "help",
      submenu: [go("Raiker guide", "open-guide", "F1")],
    },
  ];
}

/** Every accelerator in a template, for the duplicate-shortcut test. */
export function accelerators(template: readonly MenuItemConstructorOptions[]): string[] {
  const found: string[] = [];
  const walk = (items: readonly MenuItemConstructorOptions[]) => {
    for (const item of items) {
      if (typeof item.accelerator === "string") found.push(item.accelerator);
      if (Array.isArray(item.submenu)) walk(item.submenu);
    }
  };
  walk(template);
  return found;
}
