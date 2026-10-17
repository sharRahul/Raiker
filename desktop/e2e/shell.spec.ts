// SPDX-License-Identifier: Apache-2.0
/**
 * The desktop shell, driven as an owner would meet it — without a Raiker host.
 *
 * The page it shows is a fixture served on a loopback port, so this suite needs
 * only `npm run build` and runs in CI. What it proves is the shell's own
 * contract: the bridge is the only thing the page can reach, navigation stays on
 * the Raiker origin, menu commands arrive, permissions are narrow, a bad address
 * is refused by name, and the window remembers where it was.
 */
import { spawnSync } from "node:child_process";
import { createServer, type Server } from "node:http";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { _electron as electron, expect, test, type ElectronApplication, type Page } from "@playwright/test";

const SHELL_DIR = join(__dirname, "..");
// The `electron` package's main export is the path to its binary.
// eslint-disable-next-line @typescript-eslint/no-require-imports
const electronBinary: string = require("electron");

const FIXTURE = `<!doctype html><html><head><title>Fixture Raiker</title></head><body>
<h1>Fixture Raiker</h1><ul id="commands"></ul>
<script>
  window.received = [];
  if (window.raikerDesktop) {
    window.raikerDesktop.onCommand((command) => {
      window.received.push(command);
      const item = document.createElement("li");
      item.textContent = command;
      document.getElementById("commands").append(item);
    });
  }
</script></body></html>`;

let server: Server;
let base: string;

test.beforeAll(async () => {
  server = createServer((request, response) => {
    if (request.url === "/api/health") {
      response.writeHead(200, { "content-type": "application/json" }).end('{"status":"ok"}');
      return;
    }
    response.writeHead(200, { "content-type": "text/html" }).end(FIXTURE);
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  if (address === null || typeof address === "string") throw new Error("no port");
  base = `http://127.0.0.1:${address.port}/`;
});

test.afterAll(() => {
  server.close();
});

async function launch(args: string[], userData = mkdtempSync(join(tmpdir(), "raiker-shell-"))) {
  const app = await electron.launch({
    // The Chromium sandbox needs a setuid helper that node_modules cannot
    // provide on a CI runner; the window's own `sandbox: true` is asserted below.
    args: ["--no-sandbox", SHELL_DIR, ...args],
    env: { ...process.env, RAIKER_DESKTOP_USER_DATA: userData },
  });
  const page = await app.firstWindow();
  return { app, page, userData };
}

async function stubExternal(app: ElectronApplication): Promise<void> {
  await app.evaluate(({ shell }) => {
    const opened: string[] = [];
    (globalThis as unknown as { opened: string[] }).opened = opened;
    shell.openExternal = async (url: string) => {
      opened.push(url);
    };
  });
}

async function externalOpened(app: ElectronApplication): Promise<string[]> {
  return app.evaluate(() => (globalThis as unknown as { opened: string[] }).opened);
}

async function waitForFixture(page: Page) {
  await expect(page.getByRole("heading", { name: "Fixture Raiker" })).toBeVisible();
}

test("the window shows the Raiker origin with one frozen bridge and no Node", async () => {
  const { app, page } = await launch(["--raiker-url", base]);
  await waitForFixture(page);
  expect(page.url()).toBe(base);
  const surface = await page.evaluate(() => ({
    bridge: typeof window.raikerDesktop,
    version: (window as unknown as { raikerDesktop: { bridgeVersion: number } }).raikerDesktop.bridgeVersion,
    frozen: Object.isFrozen((window as unknown as { raikerDesktop: object }).raikerDesktop),
    keys: Object.keys((window as unknown as { raikerDesktop: object }).raikerDesktop).sort(),
    require: typeof (window as unknown as { require?: unknown }).require,
    process: typeof (window as unknown as { process?: unknown }).process,
  }));
  expect(surface).toEqual({
    bridge: "object",
    version: 1,
    frozen: true,
    keys: ["bridgeVersion", "focusWindow", "onCommand", "platform", "quitForUpdate", "setTitleBarColours"],
    require: "undefined",
    process: "undefined",
  });
  const preferences = await app.evaluate(({ BrowserWindow }) => {
    const prefs = BrowserWindow.getAllWindows()[0].webContents.getLastWebPreferences();
    return { sandbox: prefs?.sandbox, contextIsolation: prefs?.contextIsolation, nodeIntegration: prefs?.nodeIntegration };
  });
  expect(preferences).toEqual({ sandbox: true, contextIsolation: true, nodeIntegration: false });
  await app.close();
});

test("navigation stays on Raiker; web links go to the browser; files are refused", async () => {
  const { app, page } = await launch(["--raiker-url", base]);
  await waitForFixture(page);
  await stubExternal(app);
  await page.evaluate(() => window.open("https://example.com/docs", "_blank"));
  await page.evaluate(() => {
    window.location.href = "file:///etc/hostname";
  });
  await page.evaluate(() => {
    window.location.href = "https://example.org/";
  });
  await expect.poll(() => externalOpened(app)).toEqual(["https://example.com/docs", "https://example.org/"]);
  await page.waitForTimeout(300);
  expect(page.url()).toBe(base);
  expect(app.windows()).toHaveLength(1);
  await app.close();
});

test("menu commands reach the page, and only known ones", async () => {
  const { app, page } = await launch(["--raiker-url", base]);
  await waitForFixture(page);
  await app.evaluate(({ BrowserWindow }) => {
    const contents = BrowserWindow.getAllWindows()[0].webContents;
    contents.send("raiker:command", "go-approvals");
    contents.send("raiker:command", "rm-rf");
    contents.send("raiker:command", "open-palette");
  });
  await expect.poll(() => page.evaluate(() => (window as unknown as { received: string[] }).received)).toEqual([
    "go-approvals",
    "open-palette",
  ]);
  // The installed menu carries the Raiker items, not only Electron's defaults.
  const labels = await app.evaluate(({ Menu }) => {
    const found: string[] = [];
    const walk = (menu: Electron.Menu | null | undefined) => {
      for (const entry of menu?.items ?? []) {
        found.push(entry.label);
        walk(entry.submenu);
      }
    };
    walk(Menu.getApplicationMenu());
    return found;
  });
  expect(labels).toEqual(expect.arrayContaining(["New chat", "Command palette", "Approvals", "Raiker guide"]));
  await app.close();
});

test("permissions are the narrow set Raiker uses", async () => {
  const { app, page } = await launch(["--raiker-url", base]);
  await waitForFixture(page);
  const states = await page.evaluate(async () => {
    const query = async (name: string) =>
      (await navigator.permissions.query({ name: name as PermissionName })).state;
    return { notifications: await query("notifications"), geolocation: await query("geolocation") };
  });
  expect(states).toEqual({ notifications: "granted", geolocation: "denied" });
  await app.close();
});

test("an address that is not this computer's Raiker is refused by name", async () => {
  const { app, page } = await launch(["--raiker-url", "http://203.0.113.7:8765/"]);
  await expect(page.getByRole("heading", { name: "Raiker is not available" })).toBeVisible();
  await expect(page.getByText("http://203.0.113.7:8765/ is not a Raiker address on this computer")).toBeVisible();
  await app.close();
});

test("a host that stops answering shows why instead of a blank window", async () => {
  const { app, page } = await launch(["--raiker-url", "http://127.0.0.1:9/"]);
  await expect(page.getByRole("heading", { name: "Raiker is not available" })).toBeVisible();
  await expect(page.getByText(/Is the host still running\?/)).toBeVisible();
  await app.close();
});

test("the window opens where it was closed", async () => {
  const first = await launch(["--raiker-url", base]);
  await waitForFixture(first.page);
  await first.app.evaluate(({ BrowserWindow }) => {
    BrowserWindow.getAllWindows()[0].setBounds({ x: 40, y: 30, width: 900, height: 640 });
  });
  await first.app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].close());
  await first.app.waitForEvent("close").catch(() => undefined);
  const saved = JSON.parse(readFileSync(join(first.userData, "window-state.json"), "utf-8"));
  expect(saved.bounds).toMatchObject({ width: 900, height: 640 });

  const second = await launch(["--raiker-url", base], first.userData);
  await waitForFixture(second.page);
  const bounds = await second.app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].getBounds());
  expect(bounds).toMatchObject({ width: 900, height: 640 });
  await second.app.close();
});

test("closing the window says once that Raiker keeps running", async () => {
  const first = await launch(["--raiker-url", base]);
  await waitForFixture(first.page);
  const supported = await first.app.evaluate(({ Notification }) => Notification.isSupported());
  await first.app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].close());
  await first.app.waitForEvent("close").catch(() => undefined);
  const shell = () => JSON.parse(readFileSync(join(first.userData, "shell.json"), "utf-8"));
  if (!supported) {
    test.info().annotations.push({ type: "note", description: "no notification service on this runner" });
    return;
  }
  expect(shell()).toEqual({ backgroundNoticeShown: true });
});

test("a second launch brings the first window forward instead of opening another", async () => {
  const userData = mkdtempSync(join(tmpdir(), "raiker-shell-"));
  const first = await launch(["--raiker-url", base], userData);
  await waitForFixture(first.page);
  // Started the way a dock click or the tray's Open Raiker starts it — not
  // through the test runner, which expects a window the second copy never opens.
  const second = spawnSync(electronBinary, ["--no-sandbox", SHELL_DIR, "--raiker-url", base], {
    env: { ...process.env, RAIKER_DESKTOP_USER_DATA: userData },
    timeout: 20_000,
  });
  expect(second.status).toBe(0);
  expect(first.app.windows()).toHaveLength(1);
  await first.app.close();
});
