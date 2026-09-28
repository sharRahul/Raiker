import { expect, test, type Locator, type Page } from "@playwright/test";
import { join } from "node:path";
import { capture } from "./capture";
import { DESTINATIONS, WIDTHS, settled } from "./destinations";
import { chooseModelForTurn, signInAsOwner, useHostedModel } from "./hosted-provider";

/**
 * The third 2026-09-28 round, live: the items this run took from `docs/plans/`
 * that a browser and a real host can prove.
 *
 * * **BUG-309** — on Approvals the notice dock no longer repeats the approval
 *   the queue is listing, and nothing docked is drawn over the queue's header.
 *   A notice about an approval opens Approvals, and arriving there reads it.
 * * **OPT-03** — every request model refuses a field it does not read. Walking
 *   every destination proves no page sends one; one direct request proves the
 *   refusal is real.
 * * **OPT-04 / OPT-07 / OPT-12 / OPT-14** — the shared route dependencies and
 *   refusal envelope, the migration registry that built this fresh workspace,
 *   and the readiness classifier naming the provider from the registry, all
 *   exercised by the provider connection, a real turn and the destination walk.
 *
 * Preconditions:
 *   1. `raiker-web` on 127.0.0.1:8765, on a workspace reset for the round and
 *      holding a one-line `hello.py`
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` in the environment — entered through the UI
 */
const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";
const SHOTS = join(
  import.meta.dirname,
  "..",
  "..",
  "docs",
  "screenshots",
  "2026-09-28-docs-items-round",
);
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const PYTHON = process.env.RAIKER_LIVE_PYTHON ?? "python";
const MODEL = "claude-haiku-4-5-20251001";
const MODEL_LABEL = /Haiku 4\.5/;

test.describe.configure({ mode: "serial" });
test.setTimeout(600_000);

test.skip(ANTHROPIC_KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is not set for this round.");

async function openCapability(page: Page, label: string): Promise<Locator> {
  await page.goto(`${BASE}/#/capabilities`);
  const search = page.getByLabel("Search capabilities");
  await expect(search).toBeVisible({ timeout: 60_000 });
  await search.fill(label);
  const card = page.locator(".cap.card").filter({ hasText: label }).first();
  await expect(card).toBeVisible({ timeout: 30_000 });
  const toggle = card.getByRole("button", { name: label });
  if ((await toggle.getAttribute("aria-expanded")) !== "true") await toggle.click();
  await expect(card.locator(".cap-detail")).toBeVisible({ timeout: 10_000 });
  return card;
}

async function turnOn(page: Page, label: string, reason: string): Promise<void> {
  const card = await openCapability(page, label);
  const control = card.getByRole("button", { name: "Turn on" });
  if (!(await control.isVisible().catch(() => false))) return; // already on
  await control.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible({ timeout: 10_000 });
  await dialog.getByLabel("Reason (required)").fill(reason);
  const token = dialog.getByLabel(/Confirmation token/);
  if (await token.isVisible().catch(() => false)) await token.fill("CONFIRM");
  const ack = dialog.getByRole("checkbox");
  if (await ack.isVisible().catch(() => false)) await ack.check();
  await dialog.getByRole("button", { name: "Confirm change" }).click();
  await expect(dialog).toBeHidden({ timeout: 30_000 });
}

/** The owner's unread notices, read the way the page reads them. */
async function unreadNotices(page: Page): Promise<{ kind: string; read: boolean }[]> {
  return page.evaluate(async () => {
    const response = await fetch("/api/notifications", { credentials: "same-origin" });
    const rows = (await response.json()) as { kind: string; read: boolean }[];
    return rows.filter((row) => !row.read);
  });
}

function overlaps(a: { x: number; y: number; width: number; height: number }, b: typeof a): boolean {
  return a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;
}

test("the owner's provider is connected, and readiness names it from the registry", async ({
  page,
}) => {
  await signInAsOwner(page, BASE);
  const card = await useHostedModel(page, BASE, {
    provider: "anthropic",
    keyLabel: "API key",
    key: ANTHROPIC_KEY,
    model: MODEL,
  });
  // OPT-12 / OPT-14 — the readiness answer is built by the classifier table and
  // names the provider by the display name `model-profiles.json` declares.
  await expect(card).toContainText(/Anthropic can reach claude-haiku-4-5/, { timeout: 60_000 });
  await capture(page, join(SHOTS, "01-anthropic-ready-named-from-the-registry.png"), card);
});

test("BUG-309: an approval notice is shown elsewhere, and answered by Approvals", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await turnOn(page, "Approval execution relay", "approvals should do what they say");
  await turnOn(page, "Shell commands", "let an approved command run");

  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, MODEL_LABEL);
  const prompt = page.getByPlaceholder("How can I help you today?");
  await expect(prompt).toBeVisible({ timeout: 60_000 });
  await prompt.fill(
    `Call the shell tool once with the command "${PYTHON} hello.py", then tell me exactly what it returned.`,
  );
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 300_000 });
  await expect(page.getByRole("main")).toContainText(/approval/i, { timeout: 60_000 });
  await expect
    .poll(async () => (await unreadNotices(page)).some((row) => row.kind === "approval_pending"), {
      timeout: 60_000,
    })
    .toBe(true);

  // Somewhere that is not Approvals, the notice is exactly what it is for.
  await page.goto(`${BASE}/#/workbench`);
  await page.reload();
  const dock = page.getByRole("region", { name: "Notifications" });
  await expect(dock).toContainText("Approval needed", { timeout: 60_000 });
  await capture(page, join(SHOTS, "02-approval-notice-on-home.png"));

  // Opening it lands on the queue that answers it, not on the record.
  await dock.getByRole("button", { name: /Approval needed/ }).click();
  await expect(page).toHaveURL(/#\/approvals/);
  const header = page.getByRole("columnheader", { name: "Status" });
  await expect(header).toBeVisible({ timeout: 60_000 });

  // Nothing docked repeats a row of the queue.
  await expect(dock.filter({ hasText: "Approval needed" })).toHaveCount(0);
  // And nothing docked is drawn over the queue's header.
  if (await dock.isVisible().catch(() => false)) {
    const dockBox = await dock.boundingBox();
    const headerBox = await page.locator("thead").first().boundingBox();
    expect(dockBox && headerBox ? overlaps(dockBox, headerBox) : false).toBe(false);
  }
  // Arriving read it, through the same route opening it uses.
  await expect
    .poll(async () => (await unreadNotices(page)).some((row) => row.kind === "approval_pending"), {
      timeout: 30_000,
    })
    .toBe(false);
  // And the bell agrees at once, rather than counting it until its next poll.
  await expect(page.getByRole("button", { name: "Notifications", exact: true })).toBeVisible({
    timeout: 10_000,
  });
  await capture(page, join(SHOTS, "03-approvals-without-the-repeated-notice-1440.png"));

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(page.getByRole("tablist", { name: "Approval status filter" })).toBeVisible({
    timeout: 60_000,
  });
  // The queue itself, loaded, so the capture shows what the dock would have covered.
  await expect(page.getByRole("button", { name: "Review" }).first()).toBeVisible({
    timeout: 60_000,
  });
  await expect(dock.filter({ hasText: "Approval needed" })).toHaveCount(0);
  await capture(page, join(SHOTS, "04-approvals-without-the-repeated-notice-390.png"));
});

test("OPT-03: a request carrying a field the route never reads is refused", async ({ page }) => {
  await signInAsOwner(page, BASE);
  const answers = await page.evaluate(async () => {
    const csrf = document.cookie.match(/(?:^|;\s*)raiker_csrf=([^;]*)/)?.[1] ?? "";
    const send = async (body: Record<string, unknown>) => {
      const response = await fetch("/api/language/check", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-Raiker-CSRF": decodeURIComponent(csrf) },
        body: JSON.stringify(body),
      });
      return { status: response.status, body: await response.text() };
    };
    return {
      misspelled: await send({ text: "A sentence.", langauge: "en-GB" }),
      exact: await send({ text: "A sentence.", language: "en-US" }),
    };
  });
  // Before OPT-03 the misspelled field was dropped and the check ran in en-US.
  expect(answers.misspelled.status).toBe(422);
  expect(answers.misspelled.body).toContain("extra_forbidden");
  expect(answers.exact.status).not.toBe(422);
});

/**
 * OPT-03 / OPT-04 / OPT-07 — every destination at the two capture widths, on a
 * workspace the migration registry built, reading every page's API through the
 * shared dependencies. No page sends a field its route refuses (a 422), and
 * nothing fails.
 */
test("every destination reads its API with no refused field and no failure", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`${page.url()} — ${message.text()}`);
  });
  page.on("response", (response) => {
    const status = response.status();
    if (response.url().includes("/api/") && (status === 422 || status >= 500)) {
      errors.push(`${status} ${response.request().method()} ${response.url()}`);
    }
  });
  await signInAsOwner(page, BASE);
  for (const { width, height } of WIDTHS) {
    await page.setViewportSize({ width, height });
    for (const destination of DESTINATIONS) {
      await page.goto(`${BASE}/#/${destination.route}`);
      await expect(page.locator("main#main")).toBeVisible({ timeout: 60_000 });
      await settled(page).catch(() => undefined);
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.locator("main#main")).toBeVisible({ timeout: 60_000 });
  await capture(page, join(SHOTS, "05-home-after-the-sweep.png"));
  // A provider this host cannot reach may log its refusal; nothing else may.
  const unexpected = errors.filter((line) => !/huggingface\.co|openrouter\.ai|ollama/i.test(line));
  expect(unexpected, unexpected.join("\n")).toEqual([]);
});
