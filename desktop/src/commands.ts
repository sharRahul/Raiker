// SPDX-License-Identifier: Apache-2.0
/**
 * The commands the desktop menu can send to the Raiker page.
 *
 * A command names a place or a shell action, never data: the page decides what
 * it means and does it through the same routes and controls a click would use.
 * The preload script accepts only these names, so a compromised main-process
 * message cannot invent a new one. `web/src/lib/desktopShell.ts` holds the
 * matching handler table, and `test/commands.test.ts` keeps the two in step.
 */
export const SHELL_COMMANDS = [
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
] as const;

export type ShellCommand = (typeof SHELL_COMMANDS)[number];

export function isShellCommand(value: unknown): value is ShellCommand {
  return typeof value === "string" && (SHELL_COMMANDS as readonly string[]).includes(value);
}

/** IPC channel names, shared by main and preload. */
export const CHANNELS = {
  command: "raiker:command",
  titleBar: "raiker:title-bar",
  focus: "raiker:focus",
  quitForUpdate: "raiker:quit-for-update",
  // Quiet UI 06 — the tray's attention dot and preference (QUI-F11), a place
  // in its own window (QUI-F13), and closing Quick Entry (QUI-F01).
  attention: "raiker:attention",
  trayPreference: "raiker:tray-preference",
  openWindow: "raiker:open-window",
  closeWindow: "raiker:close-window",
  // Quick Entry before sign-in: bring the main window forward to sign in there.
  showMain: "raiker:show-main",
} as const;

/** A `#rrggbb` colour; the only form the title-bar overlay accepts from the page. */
export function isHexColour(value: unknown): value is string {
  return typeof value === "string" && /^#[0-9a-fA-F]{6}$/.test(value);
}
