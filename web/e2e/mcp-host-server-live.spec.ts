/**
 * RT-1125-16 — MCP-HOST against a running host on Windows: a local stdio
 * server is added on Extensions › MCP by its command, the way Claude Desktop and
 * Codex add one, and **Test** starts it as the owner — no command sandbox — and
 * lists the tools it offers for the owner to accept. The server is written by
 * the spec (it reports which user and folder it runs in), so nothing is
 * downloaded. Needs `python` on the host's PATH.
 */
import { expect, test } from "@playwright/test";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { capture } from "./capture";
import { setPermission, signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";
import { roundName } from "./naming";

const SERVER = `
import json, os, sys, getpass
for line in sys.stdin:
    msg = json.loads(line)
    if "id" not in msg:
        continue
    if msg["method"] == "initialize":
        result = {"protocolVersion": msg["params"]["protocolVersion"], "capabilities": {"tools": {}},
                  "serverInfo": {"name": "host-probe", "version": "1"}}
    elif msg["method"] == "tools/list":
        result = {"tools": [{"name": "whoami", "description": "Runs as " + getpass.getuser(),
                             "inputSchema": {"type": "object", "properties": {}}}]}
    else:
        result = {}
    print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}), flush=True)
`;

test("a server added by its command runs as the owner and lists its tools (MCP-HOST)", async ({ page }) => {
  test.setTimeout(300_000);
  await signInAsOwner(page, BASE);
  await setPermission(page, BASE, "MCP connector", "Turn on", "Live validation of owner-run MCP servers");

  const name = roundName("hostprobe").replace(/\s+/g, "-");
  const folder = mkdtempSync(join(tmpdir(), "raiker-mcp-host-"));
  const script = join(folder, "server.py");
  writeFileSync(script, SERVER, "utf-8");
  await page.goto(`${BASE}/#/extensions?tab=mcp`);
  await page.waitForLoadState("networkidle");
  const local = page.getByTestId("mcp-local");
  await expect(local).toContainText("as you, on this computer");
  await local.getByLabel("Name", { exact: true }).fill(name);
  await local.getByLabel("Command").fill("python");
  await local.getByLabel("Arguments (one per line)").fill(script);
  await local.getByRole("button", { name: "Add this server" }).click();
  await expect(page.getByText(/It runs as you on this computer/)).toBeVisible({ timeout: 30_000 });

  const card = page.getByRole("listitem").filter({ hasText: name }).first();
  await card.getByRole("button", { name: "Test" }).click();
  await expect(page.getByText(/connected · \d+ tool\(s\)/).first()).toBeVisible({ timeout: 60_000 });
  await expect(card).toContainText("whoami");
  await capture(page, "../../output/playwright/mcp-host-server.png");
});
