/**
 * B12/C7 and B17/C13 against a running `raiker-web` — the evidence behind those
 * four entries.
 *
 * Not a mocked shell: the runtime holds a real Anthropic credential entered
 * through the product's own Models page, the turns below reach the provider, the
 * page the agent reads is fetched from the real internet, and every screenshot
 * is the shipped product running its own endpoints.
 *
 *   B12/C7 — the agent can read a page. The `web_fetch` capability is off, so
 *            the first attempt is *withheld with the reason and the control that
 *            changes it*; once the owner enables the gate and raises the decision
 *            mode, the same request fetches a real page and quotes it back. A
 *            host outside the owner's egress allowlist is still refused.
 *   B17/C13 — the owner can stop and steer a turn that is already running. The
 *            composer grows a Stop and a steer field while a turn streams; a
 *            steer reaches the model as the owner's own words at the next safe
 *            boundary, and a stop ends the turn as **stopped**, keeping what it
 *            had already produced.
 *
 * Prerequisites:
 *   1. `python apps/api/main.py --workspace <ws> --port 8765 --no-browser` with
 *      `RAIKER_MODEL_EGRESS_ALLOWLIST=api.anthropic.com` and
 *      `RAIKER_WEB_EGRESS_ALLOWLIST=pypi.org`
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` in the environment (added through the UI below)
 */
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { capture } from "./capture";
import { join } from "node:path";

import {
  dismissFirstRunModelSetup,
  refreshHostedReadiness,
  useHostedModel,
} from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
const PASSWORD = "Web-access-turn-control-1!";
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const MODEL = "claude-haiku-4-5-20251001";
// A page on the owner egress allowlist the host was started with, whose content
// is stable enough to quote back. Any allowlisted https host works — this run
// used pypi.org because it is what the machine the run happened on could reach.
const ALLOWED_PAGE = "https://pypi.org/project/httpx/";
// Deliberately *not* on that allowlist: the refusal below is Raiker's, decided
// before any packet leaves the machine.
const DENIED_PAGE = "https://example.com/";

test.describe.configure({ mode: "serial" });

let context: BrowserContext;
let page: Page;

async function signIn(target: Page) {
  await target.goto(`${BASE}/#/workbench`);
  await expect(target.getByText("Verifying runtime…")).toBeHidden({ timeout: 30_000 });
  const confirm = target.getByLabel("Confirm password");
  await target.getByLabel("Username").fill("owner");
  await target.getByLabel("Password", { exact: true }).fill(PASSWORD);
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill(PASSWORD);
    await target.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await target.getByRole("button", { name: /unlock|sign in/i }).click();
  }
  // A brand-new instance opens the first-run model sheet over the workbench.
  await dismissFirstRunModelSetup(target);
  await expect(target.getByRole("heading", { name: /Welcome/ })).toBeVisible({ timeout: 30_000 });
}

/** Open one capability's card on the Permissions page. */
async function openCapability(label: string) {
  await page.goto(`${BASE}/#/capabilities`);
  const search = page.getByPlaceholder("Search capabilities…");
  await expect(search).toBeVisible({ timeout: 30_000 });
  await search.fill(label);
  const card = page.locator(".cap.card").filter({ hasText: label }).first();
  await expect(card).toBeVisible({ timeout: 30_000 });
  if ((await card.getByRole("button", { name: label }).getAttribute("aria-expanded")) !== "true") {
    await card.getByRole("button", { name: label }).click();
  }
  await expect(card.locator(".cap-detail")).toBeVisible({ timeout: 10_000 });
  return card;
}

/** Turn one capability on at runtime level, exactly as a person would. */
async function enableCapability(label: string, reason: string) {
  const card = await openCapability(label);
  const turnOn = card.getByRole("button", { name: "Turn on" });
  await expect(turnOn).toBeVisible({ timeout: 10_000 });
  await turnOn.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible({ timeout: 10_000 });
  await dialog.getByLabel("Reason (required)").fill(reason);
  const token = dialog.getByLabel(/Confirmation token/);
  if (await token.isVisible().catch(() => false)) await token.fill("CONFIRM");
  const ack = dialog.getByRole("checkbox");
  if (await ack.isVisible().catch(() => false)) await ack.check();
  await dialog.getByRole("button", { name: "Confirm change" }).click();
  await expect(dialog).toBeHidden({ timeout: 30_000 });
  // Asserted rather than assumed: a helper that silently skips its own work
  // would leave the next test proving the wrong thing.
  await expect(page.getByText(`Enabled ${label}.`)).toBeVisible({ timeout: 30_000 });
}

async function allowCapability(label: string, reason: string) {
  const card = await openCapability(label);
  await card.getByRole("button", { name: "Allow", exact: true }).click();
  const dialog = page.getByRole("dialog");
  if (await dialog.isVisible().catch(() => false)) {
    await dialog.getByLabel("Reason (required)").fill(reason);
    await dialog.getByRole("button", { name: "Confirm change" }).click();
    await expect(dialog).toBeHidden({ timeout: 30_000 });
  }
  await expect(page.getByText(`${label} is now set to “Allow”.`)).toBeVisible({ timeout: 30_000 });
}

test.beforeAll(async ({ browser }: { browser: Browser }) => {
  context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    colorScheme: "light",
  });
  page = await context.newPage();
  await signIn(page);
});

test.afterAll(async () => await context?.close());

test("the provider key is added through the UI and a real turn answers", async () => {
  test.setTimeout(240_000);
  expect(ANTHROPIC_KEY, "set RAIKER_LIVE_ANTHROPIC_KEY").not.toBe("");

  const card = await useHostedModel(page, BASE, {
    provider: "Anthropic",
    keyLabel: "Anthropic API key",
    key: ANTHROPIC_KEY,
    model: MODEL,
  });
  await expect(card.locator("code").filter({ hasText: /Haiku 4\.5/i })).toBeVisible({
    timeout: 30_000,
  });

  await page.goto(`${BASE}/#/new-chat`);
  await page.getByPlaceholder("How can I help you today?").fill("Reply with exactly: WEB LIVE");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByRole("main").getByText("WEB LIVE", { exact: true })).toBeVisible({
    timeout: 180_000,
  });
});

test("B12/C7 — a web read is withheld with its reason before the owner enables it", async () => {
  test.setTimeout(300_000);
  await refreshHostedReadiness(page, BASE, "Anthropic");
  await page.goto(`${BASE}/#/new-chat`);
  const prompt = page.getByPlaceholder("How can I help you today?");
  await expect(prompt).toBeVisible({ timeout: 30_000 });
  await prompt.fill(
    `Call the web_fetch tool once with url ${ALLOWED_PAGE} and then tell me, in one ` +
      "sentence, exactly what the tool returned — including any refusal reason.",
  );
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByRole("button", { name: "Copy response" }).last()).toBeVisible({
    timeout: 240_000,
  });

  // The refusal names the gate and the control that changes it, rather than
  // failing silently or pretending the page was unreachable.
  const answer = page.locator(".message-bubble-raiker").last();
  await expect(answer).toContainText(/web_fetch/i);
  // Either governed refusal is correct and both name the owner's own control:
  // the gate is off on a fresh instance, and once it is on the decision mode
  // still withholds until the owner raises it.
  await expect(answer).toContainText(/gate|disabled|capabilit|withheld|decision mode/i);
  await capture(page, join(SHOTS, "b12-web-fetch-withheld.png"));
});

test("B12/C7 — once enabled and allowed, the agent reads a real page", async () => {
  test.setTimeout(300_000);
  await enableCapability("Web fetch", "B12/C7 live verification");
  await allowCapability("Web fetch", "B12/C7 live verification");
  await capture(page, join(SHOTS, "b12-web-fetch-capability.png"));

  await refreshHostedReadiness(page, BASE, "Anthropic");
  await page.goto(`${BASE}/#/new-chat`);
  const prompt = page.getByPlaceholder("How can I help you today?");
  await expect(prompt).toBeVisible({ timeout: 30_000 });
  await prompt.fill(
    `Call the web_fetch tool once with url ${ALLOWED_PAGE} and then quote back, ` +
      "word for word, the one-line summary that page gives for the httpx project.",
  );
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByRole("button", { name: "Copy response" }).last()).toBeVisible({
    timeout: 240_000,
  });
  await expect(page.locator(".message-bubble-raiker").last()).toContainText(
    /next generation HTTP client/i,
    { timeout: 30_000 },
  );
  await capture(page, join(SHOTS, "b12-web-fetch-live-page.png"));
});

test("B12/C7 — a host outside the owner's allowlist is still refused", async () => {
  test.setTimeout(300_000);
  await refreshHostedReadiness(page, BASE, "Anthropic");
  await page.goto(`${BASE}/#/new-chat`);
  const prompt = page.getByPlaceholder("How can I help you today?");
  await expect(prompt).toBeVisible({ timeout: 30_000 });
  await prompt.fill(
    `Call the web_fetch tool once with url ${DENIED_PAGE} and then tell me in one ` +
      "sentence exactly what the tool returned, including any refusal reason.",
  );
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByRole("button", { name: "Copy response" }).last()).toBeVisible({
    timeout: 240_000,
  });
  await expect(page.locator(".message-bubble-raiker").last()).toContainText(
    /allowlist|not on the owner|egress/i,
  );
  await capture(page, join(SHOTS, "b12-web-fetch-egress-denied.png"));
});

test("B17/C13 — the owner steers a running turn, and its words reach the model", async () => {
  test.setTimeout(300_000);
  await refreshHostedReadiness(page, BASE, "Anthropic");
  await page.goto(`${BASE}/#/new-chat`);
  const prompt = page.getByPlaceholder("How can I help you today?");
  await expect(prompt).toBeVisible({ timeout: 30_000 });
  await prompt.fill(
    "First call the list_directory tool with arguments {}. Then, before you answer, " +
      "read the most recent user message in this conversation and follow it exactly.",
  );
  await page.getByRole("button", { name: "Send", exact: true }).click();

  // The composer becomes the turn's control surface while it streams.
  const control = page.getByTestId("turn-control");
  await expect(control).toBeVisible({ timeout: 60_000 });
  await capture(page, join(SHOTS, "b17-turn-control-visible.png"));

  await control.getByLabel("Add to this turn").fill("Reply with exactly: STEERED MIDTURN");
  await control.getByRole("button", { name: /Steer/ }).click();
  await expect(page.getByText(/1 instruction queued for this turn/)).toBeVisible({
    timeout: 30_000,
  });
  await capture(page, join(SHOTS, "b17-steer-queued.png"));

  await expect(page.getByRole("button", { name: "Copy response" }).last()).toBeVisible({
    timeout: 240_000,
  });
  await expect(page.locator(".message-bubble-raiker").last()).toContainText("STEERED MIDTURN");
  await capture(page, join(SHOTS, "b17-steered-answer.png"));
});

test("B17/C13 — the owner stops a running turn, and it ends as stopped", async () => {
  test.setTimeout(300_000);
  await refreshHostedReadiness(page, BASE, "Anthropic");
  await page.goto(`${BASE}/#/new-chat`);
  const prompt = page.getByPlaceholder("How can I help you today?");
  await expect(prompt).toBeVisible({ timeout: 30_000 });
  await prompt.fill(
    "Call list_directory with arguments {}, then call glob with arguments " +
      '{"pattern": "*"}, then write a very long essay about the workspace.',
  );
  await page.getByRole("button", { name: "Send", exact: true }).click();

  const control = page.getByTestId("turn-control");
  await expect(control).toBeVisible({ timeout: 60_000 });
  await control.getByRole("button", { name: "Stop this turn" }).click();
  await expect(page.getByText(/Stop requested/)).toBeVisible({ timeout: 30_000 });
  await capture(page, join(SHOTS, "b17-stop-requested.png"));

  // The turn really ends, and it ends as a decision rather than a failure.
  await expect(control).toBeHidden({ timeout: 240_000 });
  await expect(page.getByText(/Stopped at your request/).last()).toBeVisible({ timeout: 30_000 });
  await capture(page, join(SHOTS, "b17-turn-stopped.png"));
});
