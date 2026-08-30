import { chromium } from "@playwright/test";
import fs from "node:fs";

const BASE = "http://127.0.0.1:8765";
const USER = process.env.RAIKER_LIVE_USER ?? "Rahul";
const PASSWORD = process.env.RAIKER_LIVE_PASSWORD ?? "Ithink@10";
const OUT = process.env.SHOT_DIR ?? "/tmp/claude-0/-home-user-Raiker/70ddce1c-9929-5db9-adb5-d64dec3adabb/scratchpad/shots";

const pages = [
  ["01-workbench", "workbench"],
  ["02-chat", "new-chat"],
  ["03-build", "build"],
  ["04-search-chat", "search-chat"],
  ["05-tasks", "tasks"],
  ["06-projects", "projects"],
  ["07-memory", "memory"],
  ["08-brain", "brain"],
  ["09-approvals", "approvals"],
  ["10-permissions", "capabilities"],
  ["11-models", "models"],
  ["12-ext-connectors", "extensions?tab=connectors"],
  ["13-ext-mcp", "extensions?tab=mcp"],
  ["14-ext-skills", "extensions?tab=skills"],
  ["15-ext-hooks", "extensions?tab=hooks"],
  ["16-ext-plugins", "extensions?tab=plugins"],
  ["17-ext-channels", "extensions?tab=channels"],
  ["18-obs-overview", "observe?tab=overview"],
  ["19-obs-sessions", "observe?tab=sessions"],
  ["20-obs-activity", "observe?tab=activity"],
  ["21-obs-checkpoints", "observe?tab=checkpoints"],
  ["22-obs-diagnostics", "observe?tab=diagnostics"],
  ["23-obs-work", "observe?tab=work"],
  ["24-obs-notifications", "observe?tab=notifications"],
  ["25-settings", "settings"],
  ["26-guide", "guide"],
];

const viewports = (process.env.VIEWPORTS ?? "desktop").split(",");
const VP = {
  desktop: { width: 1440, height: 1000 },
  laptop: { width: 1280, height: 800 },
  tablet: { width: 834, height: 1112 },
  phone: { width: 390, height: 844 },
};

const report = { consoleErrors: [], overflow: [], missing: [] };

const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
const context = await browser.newContext({ viewport: VP[viewports[0]], colorScheme: "light" });
const page = await context.newPage();
page.on("console", (m) => {
  if (m.type() === "error") report.consoleErrors.push(m.text());
});
page.on("pageerror", (e) => report.consoleErrors.push("pageerror: " + e.message));

// sign in
await page.goto(`${BASE}/#/workbench`);
await page.getByText("Verifying runtime…").waitFor({ state: "hidden", timeout: 30000 }).catch(() => {});
const username = page.getByLabel("Username");
await username.waitFor({ state: "visible", timeout: 60000 });
await username.fill(USER);
await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
const confirm = page.getByLabel("Confirm password");
if (await confirm.isVisible().catch(() => false)) {
  await confirm.fill(PASSWORD);
  await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
} else {
  await page.getByRole("button", { name: /unlock|sign in/i }).click();
}
await page
  .getByRole("button", { name: "Decide later" })
  .or(page.getByRole("heading", { name: /Welcome (back|to your Work Dashboard)/ }))
  .first()
  .waitFor({ timeout: 60000 });
const skip = page.getByRole("button", { name: "Skip for now" });
if (await skip.isVisible().catch(() => false)) {
  await skip.click();
  await skip.waitFor({ state: "hidden", timeout: 30000 }).catch(() => {});
}
const later = page.getByRole("button", { name: "Decide later" });
if (await later.isVisible().catch(() => false)) {
  await later.click().catch(() => {});
}
console.log("signed in");

for (const vpName of viewports) {
  await page.setViewportSize(VP[vpName]);
  for (const [name, route] of pages) {
    await page.goto(`${BASE}/#/${route}`);
    await page.locator("main#main").waitFor({ timeout: 20000 }).catch(() => report.missing.push(`${vpName}/${name}: no main`));
    await page.waitForLoadState("networkidle").catch(() => {});
    await page
      .waitForFunction(
        () =>
          ![...document.querySelectorAll("main#main *")].some((el) => {
            const n = el;
            const vis = n.offsetWidth > 0 || n.offsetHeight > 0;
            return vis && /^(loading|reading|checking|verifying)\b/i.test((n.textContent ?? "").trim());
          }),
        undefined,
        { timeout: 15000 },
      )
      .catch(() => report.missing.push(`${vpName}/${name}: stuck loading`));
    await page.waitForTimeout(400);
    // horizontal overflow check
    const of = await page.evaluate(() => {
      const out = [];
      const docW = document.documentElement.clientWidth;
      if (document.documentElement.scrollWidth > docW + 1) out.push({ sel: "document", w: document.documentElement.scrollWidth, docW });
      for (const el of document.querySelectorAll("main#main *")) {
        const r = el.getBoundingClientRect();
        if (r.width === 0 && r.height === 0) continue;
        if (r.right > docW + 2) {
          out.push({
            sel: el.tagName.toLowerCase() + (el.className && typeof el.className === "string" ? "." + el.className.split(/\s+/).slice(0, 2).join(".") : ""),
            right: Math.round(r.right),
            docW,
            text: (el.textContent ?? "").trim().slice(0, 60),
          });
        }
      }
      return out.slice(0, 6);
    });
    if (of.length) report.overflow.push({ page: `${vpName}/${name}`, of });
    fs.mkdirSync(`${OUT}/${vpName}`, { recursive: true });
    await page.screenshot({ path: `${OUT}/${vpName}/${name}.png`, fullPage: true });
  }
  console.log("done viewport", vpName);
}

fs.writeFileSync(`${OUT}/report.json`, JSON.stringify(report, null, 2));
console.log("console errors:", report.consoleErrors.length);
console.log("overflow pages:", report.overflow.length);
console.log("missing:", report.missing);
await browser.close();
