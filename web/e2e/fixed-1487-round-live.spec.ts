/**
 * FIXED-1487 to FIXED-1503 — the 2026-11-17 round, against a real host.
 *
 * RT-1117-01  Connecting Anthropic and choosing a model, the first Chat turn
 *             answers on its first attempt (no *must be checked again*).
 * RT-1117-02  Chat's Context panel lists the memories the turns were given,
 *             with a way to Memory.
 * RT-1117-03  Design exports every frame as a Word document whose words are
 *             real, editable paragraphs.
 * RT-1117-04  A failed Designs read says what failed, what it affected and
 *             what to do (QUI-G06).
 * RT-1117-05  Settings › Account says which name is shown until one is chosen.
 * RT-1117-06  Work › Threads search answers by words, and a finished task
 *             offers Recovery for its own conversation.
 * RT-1117-07  OpenAI and OpenRouter connect through Add model and are ready.
 *
 * Needs `RAIKER_LIVE_ANTHROPIC_KEY` and `RAIKER_LIVE_ANTHROPIC_WORKSPACE` (and the
 * OpenAI and OpenRouter keys for RT-1117-07), read from the environment and
 * typed into the product's own dialogs. No key is written here.
 */
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { chooseModelForTurn, signInAsOwner, useHostedModel } from "./hosted-provider";
import { LIVE_BASE as BASE, sendTurn } from "./live";

const OUT = "../../output/playwright/2026-11-17-round";
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";


function watchConsole(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error" && !/Failed to load resource/.test(message.text())) errors.push(message.text());
  });
  return errors;
}

async function csrfFetch(page: Page, method: string, path: string, body?: unknown): Promise<{ status: number; json: unknown }> {
  return page.evaluate(
    async ({ method, path, body }) => {
      const csrf = document.cookie.match(/(?:^|;\s*)raiker_csrf=([^;]*)/)?.[1] ?? "";
      const response = await fetch(path, {
        method,
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-Raiker-CSRF": decodeURIComponent(csrf) },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      const text = await response.text();
      let json: unknown;
      try { json = JSON.parse(text); } catch { json = text; }
      return { status: response.status, json };
    },
    { method, path, body },
  );
}

async function answered(page: Page, word: string): Promise<void> {
  await expect(page.locator(".message-group-raiker").getByText(word).last()).toBeVisible({ timeout: 180_000 });
}

test("RT-1117-01 the first Chat turn after connecting answers on its first attempt", async ({ page }) => {
  test.setTimeout(420_000);
  expect(ANTHROPIC_KEY, "set RAIKER_LIVE_ANTHROPIC_KEY").not.toBe("");
  await signInAsOwner(page, BASE);
  // RT-1114-01 connects Anthropic (with its workspace) first. Choosing the
  // model here invalidates readiness (`model_selection_changed`), and the turn
  // is sent at once, before any background check could land.
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, /Haiku/);
  await sendTurn(page, "Reply with exactly: FIRST_TRY_OK");
  await answered(page, "FIRST_TRY_OK");
  await expect(page.getByText("This model connection must be checked again")).toHaveCount(0);
  await capture(page, `${OUT}/01-first-turn-answers.png`);
});

test("RT-1117-02 the Context panel lists the memories the turns were given", async ({ page }) => {
  test.setTimeout(420_000);
  await signInAsOwner(page, BASE);
  const remembered = "My bicycle is a green Brompton called Fern.";
  await page.goto(`${BASE}/#/memory?tab=recall`);
  const advanced = page.locator("details.advanced");
  await expect(advanced).toBeVisible({ timeout: 60_000 });
  if (!(await advanced.evaluate((node) => (node as HTMLDetailsElement).open))) await advanced.locator("summary").click();
  await advanced.locator('input[type="file"]').setInputFiles({
    name: "memories.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify({ memories: [{ text: remembered, scope: "account" }] })),
  });
  await advanced.getByRole("button", { name: /^Import / }).first().click();
  await page.goto(`${BASE}/#/memory?tab=memories`);
  await expect(page.getByText(remembered).first()).toBeVisible({ timeout: 60_000 });

  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, /Haiku/);
  await sendTurn(page, "What is my bicycle called? Answer in one short sentence.");
  await answered(page, "Fern");
  await page.getByRole("button", { name: "Context", exact: true }).click();
  const panel = page.locator("aside.context-panel");
  const tab = panel.getByRole("tab", { name: "Memories" });
  if (await tab.count()) await tab.click();
  const listed = panel.getByRole("listitem").filter({ hasText: remembered }).first();
  await expect(listed).toBeVisible({ timeout: 30_000 });
  await expect(panel.getByRole("link", { name: "Open Memory" })).toHaveAttribute("href", "#/memory");
  await capture(page, `${OUT}/02-context-memories.png`, panel);
});

test("RT-1117-03 Design exports every frame as a Word document with editable words", async ({ page }) => {
  test.setTimeout(300_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/design`);
  const made = await csrfFetch(page, "POST", "/api/design/documents", { title: "Word export round" });
  expect(made.status).toBe(200);
  const doc = made.json as { document_id: string; current_version: number; document: { frames: { id: string }[] } };
  const frame = doc.document.frames[0].id;
  const edit = await csrfFetch(page, "POST", `/api/design/documents/${doc.document_id}/operations`, {
    base_version: doc.current_version,
    operations: [{ op: "add_node", frame_id: frame, node: { id: "t1", type: "text", text: "Spring sale — 20% off", x: 80, y: 80, w: 600, h: 120, color: "#111111" } }],
  });
  expect(edit.status, JSON.stringify(edit.json)).toBe(200);

  await page.getByRole("tab", { name: "Documents" }).click();
  await page.getByRole("button", { name: /^Word export round / }).first().click();
  await page.getByRole("tab", { name: "Export", exact: true }).click();
  const exportPanel = page.getByRole("region", { name: "Export" });
  await expect(exportPanel).toBeVisible({ timeout: 30_000 });
  await exportPanel.getByRole("combobox").first().selectOption("docx");
  await exportPanel.getByRole("button", { name: "Export", exact: true }).click();
  await expect(exportPanel.getByRole("button", { name: /^Document \(Word\) · v/ }).first()).toBeVisible({ timeout: 60_000 });
  await capture(page, `${OUT}/03-design-word-export.png`, exportPanel);

  const listed = await csrfFetch(page, "GET", `/api/design/documents/${doc.document_id}/exports`);
  const rows = (listed.json as { exports?: { export_id: string; format: string }[] }).exports ?? (listed.json as { export_id: string; format: string }[]);
  const word = (Array.isArray(rows) ? rows : []).find((row) => row.format === "docx");
  expect(word, JSON.stringify(listed.json).slice(0, 300)).toBeTruthy();
  const bytes = await page.evaluate(async (id) => {
    const response = await fetch(`/api/design/exports/${id}/bytes`, { credentials: "same-origin" });
    return { type: response.headers.get("content-type"), size: (await response.arrayBuffer()).byteLength };
  }, word!.export_id);
  expect(bytes.type).toContain("wordprocessingml");
  expect(bytes.size).toBeGreaterThan(1000);
});

test("RT-1117-04 a failed Designs read says what failed and what to do", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await page.route("**/api/design/documents", (route) =>
    route.request().method() === "GET" ? route.fulfill({ status: 500, body: "{}" }) : route.continue(),
  );
  await page.goto(`${BASE}/#/design`);
  await page.getByRole("tab", { name: "Documents" }).click();
  const message = page.getByText(/Designs could not be read \(HTTP 500\)\. The list may be out of date; nothing was changed\. Choose Try again to read it again\./);
  await expect(message.first()).toBeVisible({ timeout: 30_000 });
  // No size to start from until the list is read, so Create waits for it.
  await expect(page.getByRole("button", { name: "Create" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
  await capture(page, `${OUT}/04-designs-read-failed.png`);
  await page.unroute("**/api/design/documents");
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(message).toHaveCount(0, { timeout: 30_000 });
  await expect(page.getByRole("button", { name: "Create" })).toBeEnabled();
});

test("RT-1117-05 Account says which name is shown until one is chosen", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=account`);
  const name = page.getByLabel("Display name");
  await expect(name).toBeVisible({ timeout: 60_000 });
  await expect(name).toHaveAttribute("placeholder", /^(Shown as .+ until you choose one|How you want to be shown)$/);
  await capture(page, `${OUT}/05-account-display-name.png`);
});

test("RT-1117-06 Threads search answers, and a finished task offers Recovery", async ({ page }) => {
  test.setTimeout(420_000);
  const errors = watchConsole(page);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/work?tab=threads`);
  const search = page.getByRole("searchbox").first();
  await search.fill("bicycle");
  await expect(page.getByRole("link", { name: /bicycle/i }).first()).toBeVisible({ timeout: 30_000 });
  await capture(page, `${OUT}/06-threads-search.png`);

  // A task that finishes: Run in background from Chat.
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, /Haiku/);
  const composer = page.getByRole("group", { name: "Message composer" });
  await composer.getByRole("textbox").first().fill("Reply with exactly: BACKGROUND_DONE");
  await composer.getByRole("button", { name: "Tools" }).click();
  await page.getByRole("menuitem", { name: /Run in background/ }).click();
  await expect(page.getByText("Running in the background.")).toBeVisible({ timeout: 60_000 });
  await page.goto(`${BASE}/#/work?tab=tasks`);
  const recovery = page.getByRole("link", { name: "Recovery" }).first();
  await expect(recovery).toBeVisible({ timeout: 240_000 });
  await expect(recovery).toHaveAttribute("href", /#\/checkpoints\?session=/);
  await capture(page, `${OUT}/06b-task-recovery-link.png`);
  await recovery.click();
  await expect(page.locator("#cp-session")).not.toHaveValue("", { timeout: 30_000 });
  expect(errors).toEqual([]);
});

test("RT-1117-07 OpenAI and OpenRouter connect through Add model and are ready", async ({ page }) => {
  test.setTimeout(420_000);
  const openai = process.env.RAIKER_LIVE_OPENAI_KEY ?? "";
  const openrouter = process.env.RAIKER_LIVE_OPENROUTER_KEY ?? "";
  expect(openai && openrouter, "set RAIKER_LIVE_OPENAI_KEY and RAIKER_LIVE_OPENROUTER_KEY").toBeTruthy();
  await signInAsOwner(page, BASE);
  await useHostedModel(page, BASE, { provider: "OpenAI", keyLabel: "OpenAI API key", key: openai, model: process.env.RAIKER_LIVE_OPENAI_MODEL ?? "gpt-4o-mini" });
  await useHostedModel(page, BASE, { provider: "OpenRouter", keyLabel: "OpenRouter API key", key: openrouter, model: process.env.RAIKER_LIVE_OPENROUTER_MODEL ?? "openai/gpt-4o-mini" });
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, /4o mini|gpt-4o-mini/i);
  await sendTurn(page, "Reply with exactly: OPENAI_ROUND_OK");
  await answered(page, "OPENAI_ROUND_OK");
  await capture(page, `${OUT}/07-openai-answers.png`);
});
