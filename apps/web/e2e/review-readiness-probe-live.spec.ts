import { expect, test } from "@playwright/test";
import { join } from "node:path";

/**
 * What the **Test** control on a hosted provider card actually does.
 *
 * The card's readiness chip is the gate the composer reads, so "Not checked"
 * surviving a Test is the difference between a product that can send a turn and
 * one that cannot. This spec does not assert an outcome — it records the network
 * the click produces and the chip text over time, so the result is evidence
 * rather than a guess.
 */

const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "output", "playwright");
const PASSWORD = "Review-provider-matrix-1!";
const KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";

test("Test on a connected provider card resolves the pinned model's readiness", async ({
  page,
}) => {
  test.setTimeout(900_000);
  test.skip(KEY.length === 0, "no Anthropic key supplied");

  const calls: string[] = [];
  page.on("request", (r) => {
    if (r.url().includes("/api/")) calls.push(`→ ${r.method()} ${r.url().replace(BASE, "")}`);
  });
  page.on("response", (r) => {
    if (r.url().includes("/api/")) calls.push(`← ${r.status()} ${r.url().replace(BASE, "")}`);
  });

  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText(/Verifying runtime/)).toBeHidden({ timeout: 60_000 });
  await page.getByLabel("Username").fill("owner");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  const confirm = page.getByLabel("Confirm password");
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill(PASSWORD);
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await page.getByRole("button", { name: "Unlock Raiker" }).click();
  }
  for (const name of ["Skip for now", "Decide later", "Balanced", "Set up later", "Open Workbench"]) {
    const b = page.getByRole("button", { name, exact: true });
    if (await b.isVisible().catch(() => false)) await b.click();
  }

  await page.goto(`${BASE}/#/models?tab=hosted`);
  for (const name of ["Skip for now", "Decide later", "Balanced", "Set up later", "Open Workbench"]) {
    const b = page.getByRole("button", { name, exact: true });
    if (await b.isVisible().catch(() => false)) await b.click();
  }
  await expect(page.getByRole("tab", { name: "Hosted" })).toBeVisible({ timeout: 60_000 });

  const card = page.locator("article.provider-card").filter({ hasText: "Anthropic" }).first();
  await expect(card).toBeVisible({ timeout: 60_000 });

  const connect = card.getByRole("button", { name: /^(Connect|Reconnect)$/ });
  if (await connect.isVisible().catch(() => false)) {
    await connect.click();
    await page.getByLabel("Anthropic API key").fill(KEY);
    await page.locator(".signin-connect").click();
    await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 120_000 });
  }

  const pick = card.getByRole("button", { name: /Choose model|Change model/ });
  await pick.click();
  const catalogue = card.getByLabel("Available models");
  await expect(catalogue).toBeVisible({ timeout: 120_000 });
  const values = await catalogue
    .locator("option")
    .evaluateAll((n) => n.map((o) => (o as HTMLOptionElement).value));
  console.log("CATALOGUE:", JSON.stringify(values));
  const model = values.includes("claude-haiku-4-5-20251001")
    ? "claude-haiku-4-5-20251001"
    : values.find((v) => v.length > 0)!;
  await catalogue.selectOption(model);
  await card.getByRole("button", { name: "Use model" }).click();
  console.log("PINNED:", model);

  await page.goto(`${BASE}/#/models?tab=hosted`);
  const pinned = page.locator("article.provider-card").filter({ hasText: "Anthropic" }).first();
  await expect(pinned).toBeVisible({ timeout: 60_000 });

  console.log("BEFORE TEST:", (await pinned.innerText()).replace(/\s+/g, " "));
  calls.length = 0;
  await pinned.getByRole("button", { name: "Test", exact: true }).click();

  for (const wait of [3_000, 7_000, 15_000, 30_000, 60_000]) {
    await page.waitForTimeout(wait);
    console.log(`AFTER ${wait}ms:`, (await pinned.innerText()).replace(/\s+/g, " "));
  }
  console.log("NETWORK DURING TEST:\n" + calls.join("\n"));
  await page.screenshot({ path: join(SHOTS, "review-readiness-probe.png"), fullPage: true });
});
