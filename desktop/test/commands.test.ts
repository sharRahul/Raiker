// SPDX-License-Identifier: Apache-2.0
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";

import { CHANNELS, isHexColour, isShellCommand, SHELL_COMMANDS } from "../src/commands";
import { accelerators, menuTemplate } from "../src/menu";

const ROOT = join(__dirname, "..", "..");

test("the preload accepts exactly the shell's commands and channels", () => {
  // A sandboxed preload cannot import commands.ts, so it repeats them.
  const preload = readFileSync(join(ROOT, "src", "preload.ts"), "utf-8");
  const listed = [...preload.matchAll(/^ {2}"([a-z-]+)",$/gm)].map((match) => match[1]);
  assert.deepEqual(listed, [...SHELL_COMMANDS]);
  for (const channel of Object.values(CHANNELS)) assert.ok(preload.includes(`"${channel}"`), channel);
});

test("the web app handles every shell command", () => {
  const web = readFileSync(join(ROOT, "..", "web", "src", "lib", "desktopShell.ts"), "utf-8");
  for (const command of SHELL_COMMANDS) assert.ok(web.includes(`"${command}"`), command);
});

test("command and colour validation refuse anything else", () => {
  assert.equal(isShellCommand("new-chat"), true);
  assert.equal(isShellCommand("rm -rf"), false);
  assert.equal(isShellCommand(7), false);
  assert.equal(isHexColour("#12161F"), true);
  for (const bad of ["red", "#fff", "#12161Fzz", "url(x)", 0]) assert.equal(isHexColour(bad), false);
});

test("menu shortcuts are unique on every platform, and DevTools ships only unpackaged", () => {
  for (const platform of ["darwin", "win32", "linux"] as const) {
    for (const packaged of [true, false]) {
      const template = menuTemplate(platform, packaged, { send: () => {}, openInBrowser: () => {} });
      const keys = accelerators(template);
      assert.equal(new Set(keys).size, keys.length, `${platform} duplicate accelerator`);
      const text = JSON.stringify(template);
      assert.equal(text.includes("toggleDevTools"), !packaged);
    }
  }
});

test("every Raiker menu item sends a known command", () => {
  const sent: string[] = [];
  const template = menuTemplate("linux", true, { send: (command) => sent.push(command), openInBrowser: () => {} });
  const click = (items: unknown[]) => {
    for (const item of items as { click?: () => void; submenu?: unknown }[]) {
      item.click?.();
      if (Array.isArray(item.submenu)) click(item.submenu);
    }
  };
  click(template);
  assert.ok(sent.length >= 10);
  assert.ok(sent.every(isShellCommand));
  assert.deepEqual(new Set(sent), new Set(SHELL_COMMANDS));
});
