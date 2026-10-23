/**
 * Quiet UI — visual answers (docs/plans/quiet-ui/04_VISUAL_ANSWERS.md), against
 * a running host and a real hosted model.
 *
 * Prerequisites:
 *   1. A fresh workspace served by
 *      `raiker-web --workspace <ws> --port 8765 --no-browser`.
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` (and, for an identity-linked key,
 *      `RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID`) in this run's environment only.
 *      The key is typed into the product's own dialog; none is written here.
 *
 * Most cases ask the model to repeat a block exactly, so what is checked is
 * the runtime's validation and the drawing rather than what a model chooses to
 * write. RT-QUI-37 and RT-QUI-43 are the two that let the model choose.
 *
 * Live cases (docs/architecture/WEB_APP_LIVE_TEST.md, "Quiet UI visual
 * answers"): RT-QUI-35 … RT-QUI-43.
 */
import { readFileSync } from "node:fs";

import { expect, test, type Locator, type Page } from "@playwright/test";

import { capture } from "./capture";
import { settled } from "./destinations";
import { chooseModelForTurn, keepModelAvailable, signInAsOwner } from "./hosted-provider";
import { ANTHROPIC_KEY as KEY, ANTHROPIC_MODEL as MODEL, LIVE_BASE as BASE } from "./live";

test.describe.configure({ mode: "serial" });

const WORKSPACE_ID = process.env.RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID ?? "";
const SHOTS = process.env.RAIKER_LIVE_SHOTS ?? "../../docs/screenshots/2026-10-23-quiet-ui-visual-answers";

async function open(page: Page, hash: string): Promise<void> {
  await page.goto(`${BASE}/${hash}`);
  await settled(page);
}

async function setAnswerStyle(page: Page, label: string): Promise<void> {
  await open(page, "#/settings?tab=general");
  const select = page.getByRole("combobox", { name: "Answer style" });
  await expect(select).toBeEnabled({ timeout: 30_000 });
  const chosen = await select.evaluate((element: HTMLSelectElement) => element.selectedOptions[0]?.textContent ?? "");
  if (chosen.trim() === label) return;
  await select.selectOption({ label });
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("You have unsaved changes")).toBeHidden({ timeout: 30_000 });
}

/** Send one prompt in a new chat and return the answer once it has finished. */
async function ask(page: Page, prompt: string): Promise<Locator> {
  await open(page, "#/new-chat");
  await chooseModelForTurn(page, /Haiku|claude/i);
  await page.getByLabel("Prompt", { exact: true }).fill(prompt);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const answer = page.locator(".message-group-raiker").last();
  await expect(answer).toBeVisible({ timeout: 180_000 });
  await expect(page.getByRole("button", { name: "Send", exact: true })).toBeVisible({ timeout: 240_000 });
  await expect(answer.locator(".message-bubble-raiker")).toBeVisible({ timeout: 240_000 });
  // The parts arrive with the final response; the streamed text before it is
  // prose. Wait for the turn's own copy action, which only a finished turn has.
  await expect(answer.locator(".response-actions")).toBeVisible({ timeout: 240_000 });
  return answer;
}

function verbatim(...fences: string[]): string {
  return (
    "I am checking how Raiker draws answer blocks, using my own data. Please show me these " +
    "blocks in this conversation by sending them back unchanged, with no other text:\n\n" +
    fences.join("\n\n")
  );
}

function fence(kind: string, payload: unknown): string {
  return "```raiker:" + kind + "\n" + JSON.stringify(payload) + "\n```";
}

const LAPTOPS = {
  caption: "Laptops for working on the move",
  items: ["MacBook Air 13", "Dell XPS 13", "ThinkPad X1 Carbon"],
  rows: [
    { label: "Battery", unit: "h", better: "higher", values: [18, 13, 15] },
    { label: "Weight", unit: "kg", better: "lower", values: [1.24, 1.19, 1.09] },
    { label: "Price", unit: "£", better: "lower", values: [999, 1099, 1399] },
  ],
  source: "Figures given in this conversation",
};

test("RT-QUI-35 — Anthropic connects through Add model and becomes the default", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(360_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await open(page, "#/models");
  await page.getByRole("button", { name: "Add model" }).first().click();
  const dialog = page.getByRole("dialog", { name: "Add model" });
  await dialog.getByRole("button", { name: /An account I have/ }).click();
  const card = dialog.locator("article.provider-card").filter({ hasText: "Anthropic" }).first();
  const connect = card.getByRole("button", { name: "Connect", exact: true });
  if (await connect.isVisible().catch(() => false)) {
    await connect.click();
    await page.getByLabel("Anthropic API key").fill(KEY);
    if (WORKSPACE_ID) {
      await page.getByRole("button", { name: "Advanced" }).last().click();
      await page.getByPlaceholder("wrkspc_…").fill(WORKSPACE_ID);
    }
    await page.locator(".signin-connect").click();
  }
  await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 90_000 });
  await keepModelAvailable(page, card, MODEL);
  const review = dialog.getByRole("region", { name: "3 · Review" });
  const makeDefault = review.getByRole("button", { name: "Make default" }).first();
  await expect(makeDefault.or(review.getByText("Default", { exact: true })).first()).toBeVisible({ timeout: 60_000 });
  if (await makeDefault.isVisible().catch(() => false)) await makeDefault.click();
  await expect(review.getByText("Default", { exact: true }).first()).toBeVisible({ timeout: 60_000 });
  await review.getByRole("button", { name: "Done" }).click();
  await expect(dialog).toBeHidden();
});

test("RT-QUI-36 — Settings › General: Answer style, Auto by default, kept across a reload", async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await open(page, "#/settings?tab=general");
  const select = page.getByRole("combobox", { name: "Answer style" });
  await expect(select).toHaveValue("auto", { timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "Answers" })).toBeVisible();
  await capture(page, `${SHOTS}/36-settings-answer-style.png`, page.locator("section.settings-card", { has: select }));
  await setAnswerStyle(page, "Visual where it helps");
  await page.reload();
  await settled(page);
  await expect(page.getByRole("combobox", { name: "Answer style" })).toHaveValue("visual", { timeout: 30_000 });
});

test("RT-QUI-37 — a comparison question answers with key figures, a comparison and Best marked by Raiker", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(420_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  const answer = await ask(
    page,
    "Compare three laptops for working on the move, using only these figures, which I am giving you: " +
      "MacBook Air 13 — battery 18 h, weight 1.24 kg, price £999. Dell XPS 13 — battery 13 h, " +
      "weight 1.19 kg, price £1,099. ThinkPad X1 Carbon — battery 15 h, weight 1.09 kg, price £1,399. " +
      "Show me here in this conversation the headline numbers, a comparison of all three, and a " +
      "one-line verdict. Do not create a file and do not search the web.",
  );
  const compare = answer.locator('.answer-block[data-block="compare"]');
  await expect(compare).toBeVisible({ timeout: 30_000 });
  // Raiker, not the model, chose these: higher battery, lower weight, lower price.
  await expect(compare.getByRole("row", { name: /Battery/ }).locator("td.best")).toContainText("18");
  await expect(compare.getByRole("row", { name: /Weight/ }).locator("td.best")).toContainText("1.09");
  await expect(compare.getByRole("row", { name: /Price/ }).locator("td.best")).toContainText("999");
  await expect(compare.getByText("Best")).toHaveCount(3);
  // At most three is guidance to the model; above it, the answer must offer a document.
  if ((await answer.locator(".answer-block").count()) > 3) {
    await expect(answer.getByRole("button", { name: "Create document" })).toBeVisible();
  }
  await capture(page, `${SHOTS}/37-comparison-answer.png`, answer);
});

test("RT-QUI-38 — every new block draws: figures, measure, callout, pros and cons, steps", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(420_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  const answer = await ask(
    page,
    verbatim(
      fence("figures", {
        items: [
          { label: "Longest battery", value: 18, unit: "h", of: "MacBook Air 13" },
          { label: "Lightest", value: 1.09, unit: "kg", of: "ThinkPad X1 Carbon" },
          { label: "Lowest price", value: 999, unit: "£", of: "MacBook Air 13", estimate: true },
        ],
        source: "Manufacturer spec pages, checked 23 Oct 2026",
      }),
      fence("measure", { label: "Checks passed", value: 31, max: 40, source: "This workspace's test run" }),
      fence("callout", { tone: "warning", text: "Battery figures are manufacturer claims." }),
    ),
  );
  const figures = answer.locator('.answer-block[data-block="figures"]');
  await expect(figures.getByText("Longest battery")).toBeVisible({ timeout: 30_000 });
  await expect(figures.getByText("≈ estimate")).toBeVisible();
  await expect(figures.getByText(/Source: Manufacturer spec pages/)).toBeVisible();
  await expect(answer.getByText("31 of 40")).toBeVisible();
  await expect(answer.getByRole("meter")).toHaveAttribute("aria-label", "Checks passed: 31 of 40");
  await expect(answer.locator(".callout").getByText("Warning.")).toBeVisible();
  await capture(page, `${SHOTS}/38-figures-measure-callout.png`, answer);

  const second = await ask(
    page,
    verbatim(
      fence("proscons", {
        options: [
          { name: "MacBook Air 13", pros: ["Longest battery", "Lowest price"], cons: ["Two ports"] },
          { name: "ThinkPad X1 Carbon", pros: ["Lightest"], cons: ["Highest price"] },
        ],
      }),
      fence("steps", {
        caption: "Getting a new laptop ready",
        steps: [
          { label: "Order", when: "Monday" },
          { label: "Move files", when: "Wednesday", text: "From the backup" },
          { label: "Sign in to services", when: "Thursday" },
        ],
      }),
    ),
  );
  await expect(second.getByText("Pros").first()).toBeVisible({ timeout: 30_000 });
  await expect(second.getByText("Cons").first()).toBeVisible();
  await expect(second.locator('.answer-block[data-block="steps"] li')).toHaveCount(3);
  await capture(page, `${SHOTS}/38-pros-cons-and-steps.png`, second);
});

test("RT-QUI-39 — the new chart kinds draw, and the toolbar switches, copies and downloads", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(420_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  const answer = await ask(
    page,
    verbatim(
      fence("chart", {
        kind: "hbar",
        caption: "Battery life",
        y_label: "Hours",
        labels: ["MacBook Air 13", "Dell XPS 13", "ThinkPad X1 Carbon"],
        series: [{ name: "Battery", values: [18, 13, 15] }],
      }),
      fence("chart", {
        kind: "stacked",
        caption: "Where the week went",
        labels: ["This week", "Last week"],
        series: [
          { name: "Chat", values: [6, 4] },
          { name: "Build", values: [3, 5] },
          { name: "Design", values: [1, 1] },
        ],
      }),
      fence("chart", {
        kind: "scatter",
        caption: "Price against battery",
        labels: ["MacBook Air 13", "Dell XPS 13", "ThinkPad X1 Carbon"],
        series: [
          { name: "Price (£)", values: [999, 1099, 1399] },
          { name: "Battery (h)", values: [18, 13, 15] },
        ],
      }),
    ),
  );
  const charts = answer.locator('.answer-block[data-block="chart"]');
  await expect(charts).toHaveCount(3, { timeout: 30_000 });
  await expect(answer.locator('figure.data-chart[data-kind="hbar"] svg')).toBeVisible();
  await expect(answer.locator('figure.data-chart[data-kind="stacked"] svg')).toBeVisible();
  await expect(answer.locator('figure.data-chart[data-kind="scatter"] svg')).toBeVisible();
  await capture(page, `${SHOTS}/39-new-chart-kinds.png`, answer);

  // Table one click away, and back.
  const stacked = charts.nth(1);
  await stacked.getByRole("button", { name: "Table" }).click();
  await expect(stacked.getByRole("table")).toBeVisible();
  await expect(stacked.getByRole("table")).toContainText("60%");
  await capture(page, `${SHOTS}/39-stacked-as-table.png`, stacked);
  await stacked.getByRole("button", { name: "Chart" }).click();
  await expect(stacked.locator("figure.data-chart svg")).toBeVisible();

  // CSV and PNG are real files.
  const hbar = charts.first();
  const [csv] = await Promise.all([page.waitForEvent("download"), hbar.getByRole("button", { name: "CSV" }).click()]);
  expect(csv.suggestedFilename()).toBe("battery-life.csv");
  expect(readFileSync(await csv.path(), "utf8")).toContain("ThinkPad X1 Carbon,15");
  const [png] = await Promise.all([page.waitForEvent("download"), hbar.getByRole("button", { name: "PNG" }).click()]);
  expect(png.suggestedFilename()).toBe("battery-life.png");
  expect(readFileSync(await png.path()).subarray(1, 4).toString()).toBe("PNG");

  // Show as text, and Copy.
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"], { origin: BASE });
  await hbar.getByRole("button", { name: "Show as text" }).click();
  await expect(hbar.getByText(/MacBook Air 13 · 18/)).toBeVisible();
  await hbar.getByRole("button", { name: "Copy" }).click();
  await expect(hbar.locator(".toolbar .notice")).toHaveText("Copied");
  expect(await page.evaluate(() => navigator.clipboard.readText())).toContain("Dell XPS 13\t13");
  await capture(page, `${SHOTS}/39-show-as-text.png`, hbar);
});

test("RT-QUI-40 — numbers with no source are shown as text, and a malformed block is refused visibly", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(420_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  const answer = await ask(
    page,
    verbatim(
      "Before the blocks.",
      fence("figures", { items: [{ label: "Longest battery", value: 18, unit: "h", of: "MacBook Air 13" }] }),
      fence("figures", { items: [{ label: "Battery", value: 18 }], source: "Spec pages" }),
      "After the blocks.",
    ),
  );
  await expect(answer.getByText("Longest battery: 18 h (MacBook Air 13)")).toBeVisible({ timeout: 30_000 });
  await expect(answer.getByText(/No source was given for these numbers/)).toBeVisible();
  await expect(answer.locator('.answer-block[data-block="figures"]')).toHaveCount(0);
  const refused = answer.getByRole("note").filter({ hasText: "Not rendered" });
  await expect(refused).toContainText("A figure had no unit");
  await expect(refused).toContainText("figures_unit_missing");
  await expect(answer.getByText("Before the blocks.")).toBeVisible();
  await expect(answer.getByText("After the blocks.")).toBeVisible();
  await capture(page, `${SHOTS}/40-unsourced-and-refused.png`, answer);
});

test("RT-QUI-41 — an answer of more than three blocks offers Create document, which fills the composer", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(420_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  const answer = await ask(
    page,
    verbatim(
      fence("compare", LAPTOPS),
      fence("callout", { tone: "verdict", text: "The MacBook Air 13 is the best all-rounder here." }),
      fence("callout", { tone: "action", text: "Check the port layout before ordering." }),
      fence("steps", { steps: [{ label: "Order" }, { label: "Set up" }] }),
    ),
  );
  await expect(answer.locator(".answer-block")).toHaveCount(4, { timeout: 30_000 });
  await expect(answer.getByText(/This answer has 4 blocks/)).toBeVisible();
  await capture(page, `${SHOTS}/41-report-offer.png`, answer.locator(".report-offer"));
  await answer.getByRole("button", { name: "Create document" }).click();
  await expect(page.getByLabel("Prompt", { exact: true })).toHaveValue(/into a document I can keep/);
});

test("RT-QUI-42 — a conversation export keeps a comparison as a table with Best", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(420_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await ask(page, verbatim(fence("compare", LAPTOPS)));
  await page.getByRole("button", { name: /Conversation actions|More conversation actions/ }).first().click();
  await page.getByRole("menuitem", { name: /Export/ }).click();
  const dialog = page.getByRole("dialog", { name: /Export/ });
  await dialog.getByRole("radio", { name: /Markdown/ }).check();
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    dialog.getByRole("button", { name: /Download|Export/ }).last().click(),
  ]);
  const text = readFileSync(await download.path(), "utf8");
  expect(text).toContain("| Battery (h) | 18 — Best | 13 | 15 |");
  // The prompt quotes the fence; Raiker's own section must not.
  expect(text.split("### Raiker")[1] ?? "").not.toContain("raiker:compare");
});

test("RT-QUI-43 — Mostly text: the same kind of question is answered in prose", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(420_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await setAnswerStyle(page, "Mostly text");
  const answer = await ask(
    page,
    "Using only these figures, which is lighter and by how much: MacBook Air 13 at 1.24 kg, " +
      "Dell XPS 13 at 1.19 kg, ThinkPad X1 Carbon at 1.09 kg? Do not search the web.",
  );
  await expect(answer).toContainText(/X1 Carbon/);
  await expect(answer.locator(".answer-block")).toHaveCount(0);
  await capture(page, `${SHOTS}/43-mostly-text.png`, answer);
  await setAnswerStyle(page, "Auto");
});
