/** RU-11 / RT-MEM-SUMMARY-01: real host and encrypted store; no API mocks. */
import { join } from "node:path";
import { execFileSync } from "node:child_process";
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { chooseModelForTurn, keepOffered, signInAsOwner } from "./hosted-provider";
import { armConfirm, LIVE_BASE as BASE, sendTurn } from "./live";

const SHOTS = join(import.meta.dirname, "..", "..", "output", "playwright", "ru-11");

test("RT-MEM-SUMMARY-01 — read, edit, forget and control memory without leaving Memory", async ({ page }) => {
  test.setTimeout(600_000);
  page.setDefaultTimeout(30_000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.emulateMedia({ reducedMotion: "reduce" });
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/memory?tab=controls`);
  const advanced = page.locator("details.advanced");
  await advanced.locator("summary").click();
  await advanced.locator('input[type="file"]').setInputFiles({
    name: "ru11-facts.json", mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify({ memories: [
      { text: "My favourite tea is Assam.", memory_type: "preference", scope: "account" },
      { text: "The alpha project deploys on Thursday.", memory_type: "project", scope: "project:alpha" },
      { text: "Forget this temporary fact after review.", memory_type: "fact", scope: "account" },
    ] })),
  });
  await expect(advanced.getByRole("button", { name: "Import 3 records", exact: true })).toBeVisible();
  await advanced.getByRole("button", { name: "Import 3 records", exact: true }).click();
  await expect(advanced).toContainText("Imported 3 records");
  await page.goto(`${BASE}/#/memory`);
  await expect(page.getByRole("heading", { name: "What Raiker knows about you" })).toBeVisible();
  const summary = page.getByRole("region", { name: "What Raiker knows about you", exact: true });
  await expect(summary.getByText("My favourite tea is Assam.", { exact: true })).toBeVisible();
  await expect(summary.getByRole("heading", { name: "Preferences" })).toBeVisible();
  await expect(summary.getByText("project:alpha", { exact: true })).toBeVisible();
  await summary.getByRole("button", { name: "Edit My favourite tea is Assam.", exact: true }).click();
  await summary.getByRole("textbox", { name: "Memory text" }).fill("My favourite tea is Darjeeling.");
  await summary.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect(summary.getByText("My favourite tea is Darjeeling.", { exact: true })).toBeVisible();
  armConfirm(page);
  await summary.getByRole("button", { name: "Forget Forget this temporary fact after review.", exact: true }).click();
  await expect(summary.getByText("Forget this temporary fact after review.", { exact: true })).toBeHidden();
  const useMemory = page.getByRole("switch", { name: "Use memory", exact: true });
  await expect(useMemory).toHaveAttribute("aria-checked", "true");
  await useMemory.click();
  await expect(useMemory).toHaveAttribute("aria-checked", "false");
  await page.reload();
  await expect(useMemory).toHaveAttribute("aria-checked", "false");
  await expect(summary.getByText("My favourite tea is Darjeeling.", { exact: true })).toBeVisible();
  await useMemory.click();
  await expect(useMemory).toHaveAttribute("aria-checked", "true");
  await expect(useMemory).toBeEnabled();

  for (const theme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: theme });
    await page.evaluate((value) => document.documentElement.setAttribute("data-theme", value), theme);
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      const navigationToggle = page.getByRole("banner").getByRole("button", { name: /navigation/, exact: false });
      await expect(navigationToggle).toHaveAttribute("aria-label", width === 390 ? /^(Open|Close) navigation$/ : /^(Collapse|Expand) navigation$/);
      const closeNavigation = page.getByRole("banner").getByRole("button", { name: "Close navigation", exact: true });
      if (await closeNavigation.isVisible()) await closeNavigation.click();
      await expect(page.locator(".drawer-scrim")).toBeHidden();
      await page.waitForFunction(() => document.getAnimations().every((animation) => animation.playState !== "running"));
      await expect(summary).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(0);
      await capture(page, join(SHOTS, `summary-${theme}-${width}.png`));
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`${BASE}/#/settings?tab=advanced&kind=memory-engine`);
  await expect(page).toHaveURL(/#\/memory\?tab=controls/);
  await expect(page.getByRole("heading", { name: "Find by meaning", exact: true })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Recall backend", exact: true })).toBeVisible();
  await capture(page, join(SHOTS, "controls.png"));

  // Optional real embedding qualification. Authorization is fixture setup,
  // through public control services, in this run's disposable workspace only.
  const workspace = process.env.RAIKER_RU11_SEMANTIC_WORKSPACE;
  if (workspace) {
    const fixture = (operation: "authorize" | "search" | "unavailable" | "restore") => JSON.parse(execFileSync(
      process.env.RAIKER_LIVE_PYTHON ?? "python",
      ["-m", "scripts.live_memory_summary_harness", workspace, operation],
      { cwd: join(import.meta.dirname, "..", ".."), encoding: "utf8" },
    ));
    await page.getByRole("combobox", { name: "Local embedding model", exact: true }).selectOption("ollama:nomic-embed-text");
    await page.getByRole("button", { name: "Find by meaning (stays on this computer)", exact: true }).click();
    await expect(page.getByRole("alert")).toContainText("Could not prepare meaning search");
    await capture(page, join(SHOTS, "local-meaning-refused.png"));
    expect(fixture("authorize")).toEqual({ authorized: true });
    expect(fixture("unavailable")).toEqual({ unavailable: true });
    await page.getByRole("button", { name: "Find by meaning (stays on this computer)", exact: true }).click();
    await expect(page.getByRole("alert")).toContainText("Could not prepare meaning search");
    await expect(page.getByRole("button", { name: "Find by meaning (stays on this computer)", exact: true })).toBeEnabled();
    await capture(page, join(SHOTS, "local-meaning-unavailable.png"));
    expect(fixture("restore")).toEqual({ restored: true });
    await page.reload();
    await page.getByRole("combobox", { name: "Local embedding model", exact: true }).selectOption("ollama:nomic-embed-text");
    await page.getByRole("button", { name: "Find by meaning (stays on this computer)", exact: true }).click();
    await expect(page.getByRole("status", { name: "Meaning search result" })).toHaveText(/ready on this computer/, { timeout: 90_000 });
    await expect(page.getByText(/Searching.*nomic-embed-text.*matches meaning/)).toBeVisible();
    const recalled = fixture("search");
    expect(recalled.status).toBe("success");
    expect(recalled.results.some((row: { text: string; sources: string[] }) => row.text.includes("Darjeeling") && row.sources.includes("vector"))).toBe(true);
    await page.getByRole("switch", { name: "Use memory", exact: true }).click();
    await expect(page.getByRole("switch", { name: "Use memory", exact: true })).toHaveAttribute("aria-checked", "false");
    expect(fixture("search")).toMatchObject({ status: "withheld", reason: "incognito", count: 0 });
    await page.getByRole("switch", { name: "Use memory", exact: true }).click();
    await expect(page.getByRole("switch", { name: "Use memory", exact: true })).toHaveAttribute("aria-checked", "true");
    expect(fixture("search").status).toBe("success");
    await capture(page, join(SHOTS, "local-meaning-ready.png"));

    await page.goto(`${BASE}/#/models?tab=add&source=local`);
    await capture(page, join(SHOTS, "chat-model-setup.png"));
    const ollama = page.locator(".local-row", { has: page.getByRole("heading", { name: "Ollama", exact: true }) });
    await ollama.getByRole("button", { name: /^(Choose a model|Select models…|Change model)$/ }).first().click();
    await keepOffered(page.getByRole("dialog", { name: "Ollama models" }), "qwen2.5-coder:7b");

    const chat = async (incognito: boolean, expectedMode: "off" | "search_when_relevant", filename: string) => {
      await page.goto(`${BASE}/#/new-chat`);
      const newChat = page.getByRole("button", { name: "New chat", exact: true });
      if (await newChat.isVisible()) await newChat.click();
      const privacy = page.getByRole("switch", { name: "Incognito for this conversation" });
      await expect(privacy).toHaveAttribute("aria-checked", "false");
      if (incognito) {
        await privacy.click();
        await expect(privacy).toHaveAttribute("aria-checked", "true");
        await expect(page).toHaveURL(/session=sess_/);
        await capture(page, join(SHOTS, "incognito-before-reload.png"));
        await page.reload();
        await expect(privacy).toHaveAttribute("aria-checked", "true");
      }
      await chooseModelForTurn(page, /Qwen 2.5 Coder.*7B/i);
      await sendTurn(page, "What is my favourite tea? Use only my saved memories if available. Otherwise say you do not know. Answer in one short sentence.");
      const answer = page.locator(".message-bubble-raiker").last();
      await expect(answer).toHaveText(/\S/, { timeout: 180_000 });
      await expect(privacy).toBeEnabled({ timeout: 180_000 });
      await expect(answer).not.toContainText(/could not finish|provider refused/i);
      const sessionId = new URLSearchParams(page.url().split("?")[1]).get("session");
      expect(sessionId).toBeTruthy();
      const recall = await page.evaluate(async (id) => {
        const response = await fetch(`/api/sessions/${id}/recall`);
        if (!response.ok) throw new Error(`recall ${response.status}`);
        return response.json();
      }, sessionId);
      expect(recall.disclosures).toHaveLength(1);
      expect(recall.disclosures[0]).toMatchObject({ effective_mode: expectedMode, incognito: expectedMode === "off" });
      if (expectedMode === "off") {
        expect(recall.memories).toHaveLength(0);
        await expect(answer).not.toContainText(/Darjeeling/i);
        await expect(page.getByRole("complementary", { name: "Suggested goal" })).toBeHidden();
      } else {
        expect(recall.disclosures[0].brief_count + recall.disclosures[0].recall_count).toBeGreaterThan(0);
        await expect(answer).toContainText(/Darjeeling/i);
      }
      await capture(page, join(SHOTS, filename));
      if (incognito) {
        for (const theme of ["light", "dark"] as const) {
          await page.emulateMedia({ colorScheme: theme });
          await page.evaluate((value) => document.documentElement.setAttribute("data-theme", value), theme);
          for (const width of [1440, 390]) {
            await page.setViewportSize({ width, height: 1000 });
            const toggle = page.getByRole("banner").getByRole("button", { name: /navigation/ });
            await expect(toggle).toHaveAttribute("aria-label", width === 390 ? /^(Open|Close) navigation$/ : /^(Collapse|Expand) navigation$/);
            const close = page.getByRole("button", { name: "Close navigation", exact: true });
            if (await close.isVisible()) await close.click();
            await expect(page.locator(".drawer-scrim")).toBeHidden();
            await page.waitForFunction(() => document.getAnimations().every((animation) => animation.playState !== "running"));
            expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(0);
            await capture(page, join(SHOTS, `incognito-${theme}-${width}.png`));
          }
        }
        await page.setViewportSize({ width: 1440, height: 1000 });
      }
    };
    await chat(false, "search_when_relevant", "chat-memory-on.png");
    await chat(true, "off", "chat-incognito.png");
    await page.goto(`${BASE}/#/memory`);
    await page.getByRole("switch", { name: "Use memory", exact: true }).click();
    await expect(page.getByRole("switch", { name: "Use memory", exact: true })).toHaveAttribute("aria-checked", "false");
    await chat(false, "off", "chat-global-memory-off.png");
    await page.goto(`${BASE}/#/memory`);
    await page.getByRole("switch", { name: "Use memory", exact: true }).click();
    await expect(page.getByRole("switch", { name: "Use memory", exact: true })).toHaveAttribute("aria-checked", "true");
    await chat(false, "search_when_relevant", "chat-memory-restored.png");
  }
  expect(errors).toEqual([]);
});
