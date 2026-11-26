/**
 * RU-16 — a ChatGPT and a Claude `conversations.json`, chosen in Memory's
 * Review import, become one record per conversation to review. Against a
 * running host (no model or key needed):
 *
 *   raiker-web --workspace <ws> --port 8765 --no-browser
 *
 * Live case (docs/architecture/WEB_APP_LIVE_TEST.md): RT-IMPORT-01.
 */
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { capturePath } from "./capture";
import { dismissFirstRunModelSetup, signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const SHOTS = join(import.meta.dirname, "..", "..", "docs", "plans", "screenshots", "working");

const CHATGPT = [
  {
    title: "Weekly meal plan",
    create_time: 1767225600,
    mapping: {
      root: { message: null },
      u1: { message: { author: { role: "user" }, content: { parts: ["I am vegetarian; plan my week of dinners."] }, create_time: 2 } },
    },
  },
];
const CLAUDE = [
  {
    name: "Run club",
    created_at: "2026-02-10T08:00:00Z",
    chat_messages: [{ sender: "human", text: "I run 10k on Sundays; build me a training plan." }],
  },
];

test("RT-IMPORT-01 — ChatGPT and Claude conversation exports import as records to review", async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await signInAsOwner(page, BASE);
  await dismissFirstRunModelSetup(page).catch(() => undefined);
  await page.goto(`${BASE}/#/memory?tab=controls`);
  const advanced = page.locator("details.advanced");
  await expect(advanced).toBeVisible({ timeout: 60_000 });
  if (!(await advanced.evaluate((d) => (d as HTMLDetailsElement).open))) await advanced.locator("summary").click();
  const input = advanced.locator('input[type="file"]');

  for (const [name, data, expected] of [
    ["chatgpt-conversations.json", CHATGPT, "From ChatGPT, “Weekly meal plan” (2026-01-01): I am vegetarian; plan my week of dinners."],
    ["claude-conversations.json", CLAUDE, "From Claude, “Run club” (2026-02-10): I run 10k on Sundays; build me a training plan."],
  ] as const) {
    await input.setInputFiles({ name, mimeType: "application/json", buffer: Buffer.from(JSON.stringify(data)) });
    await expect(advanced).toContainText(expected, { timeout: 30_000 });
    await expect(advanced.getByRole("button", { name: /^Import/ })).toBeVisible();
    await page.screenshot({ path: capturePath(join(SHOTS, `ru-16-${name.replace(".json", "")}.png`)) });
  }
  // Nothing is stored before Import: the review only reads.
});
