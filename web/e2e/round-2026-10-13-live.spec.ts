/**
 * The 2026-10-13 round: fourteen open defects closed from the ledger, proved
 * against a running host with a real Anthropic key and its workspace ID.
 *
 * - BUG-332 / BUG-331 — first-run setup draws its step at once, does not call
 *   an identity-linked key "connected" while it lists nothing, and asks for the
 *   workspace ID with the field focused; the workspace makes the models list.
 * - BUG-313 — "Answer in one sentence." no longer stops recall finding the
 *   memory the question is about.
 * - BUG-316 — Build says where the work is filed and where it runs.
 * - BUG-315 — the owner's own Telegram message is answered back over Telegram
 *   through the governed sender; a reply carrying sensitive information is
 *   held on Deliveries to review with Send to chat and Discard.
 *
 * Runs against a workspace reset with `scripts/reset_live_workspace.py`, served
 * with `RAIKER_CHANNEL_INBOUND_SECRET=round-inbound-secret-1013`,
 * `RAIKER_TELEGRAM_BOT_TOKEN` set to a token Telegram does not know and
 * `RAIKER_CHANNEL_EGRESS_ALLOWLIST=api.telegram.org`, and `RAIKER_LIVE_WORKSPACE`
 * pointing at it. The Anthropic key and workspace ID come from
 * `RAIKER_LIVE_ANTHROPIC_KEY` and `RAIKER_LIVE_ANTHROPIC_WORKSPACE` and are typed
 * into setup the way an owner does; neither is written anywhere. Telegram's
 * side is this spec posting updates the way Telegram's servers would — there
 * is no Telegram account on this host — so the outbound send is proved to
 * leave through the governed path and to be refused by Telegram, not to arrive.
 */
import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { settled } from "./destinations";
import { chooseModelForTurn, signInAsOwner } from "./hosted-provider";
import { ANTHROPIC_KEY, LIVE_BASE, sendTurn } from "./live";

const BASE = LIVE_BASE;
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-10-13-ledger-round");
const REPO = join(import.meta.dirname, "..", "..");
const PYTHON = process.env.RAIKER_LIVE_PYTHON ?? "python";
const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? "";
const ANTHROPIC_WORKSPACE = process.env.RAIKER_LIVE_ANTHROPIC_WORKSPACE ?? "";
const INBOUND_SECRET = "round-inbound-secret-1013";
const OWNER = { user: "owner", password: "round-pass-1013" };
const TEA = "My favourite tea is Assam with a splash of oat milk.";
const HAIKU = /Haiku 5\.5/i;

test.describe.configure({ mode: "serial" });
test.use({ timezoneId: "UTC" });

function watchFailures(page: Page): { failures: string[] } {
  const failures: string[] = [];
  page.on("response", (response) => {
    if (response.url().includes("/api/") && response.status() >= 500) {
      failures.push(`${response.status()} ${response.request().method()} ${response.url()}`);
    }
  });
  return { failures };
}

/** A same-origin API call made the way the page makes one. */
async function api(page: Page, method: string, path: string, body?: unknown, headers: Record<string, string> = {}) {
  return page.evaluate(
    async ({ method, path, body, headers }) => {
      const csrf = document.cookie.match(/(?:^|;\s*)raiker_csrf=([^;]*)/)?.[1] ?? "";
      const response = await fetch(path, {
        method,
        credentials: "same-origin",
        headers: {
          ...(body === undefined ? {} : { "Content-Type": "application/json" }),
          ...(method === "GET" ? {} : { "X-Raiker-CSRF": decodeURIComponent(csrf) }),
          ...headers,
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      const json: unknown = await response.json().catch(() => null);
      return { status: response.status, json };
    },
    { method, path, body, headers },
  );
}

test("setup asks for the workspace ID, and the workspace makes the models list", async ({ page }) => {
  test.setTimeout(300_000);
  expect(ANTHROPIC_KEY, "set RAIKER_LIVE_ANTHROPIC_KEY").not.toBe("");
  expect(ANTHROPIC_WORKSPACE, "set RAIKER_LIVE_ANTHROPIC_WORKSPACE").not.toBe("");
  const seen = watchFailures(page);
  await page.goto(`${BASE}/#/workbench`);
  const username = page.getByLabel("Username");
  await expect(username).toBeEnabled({ timeout: 60_000 });
  await username.fill(OWNER.user);
  await page.getByLabel("Password", { exact: true }).fill(OWNER.password);
  await page.getByLabel("Confirm password").fill(OWNER.password);
  await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  await expect(page.locator("#setup-title")).toBeVisible({ timeout: 60_000 });
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("heading", { name: "Choose how Raiker should think" })).toBeVisible();

  // The key, typed where setup asks for it.
  await page.getByLabel("Anthropic API key").fill(ANTHROPIC_KEY);
  const anthropic = page
    .locator("article, li, section")
    .filter({ has: page.getByLabel("Anthropic API key") })
    .last();
  await anthropic.getByRole("button", { name: "Save and list models" }).click();

  // BUG-332 — not "connected": the provider said the key needs its workspace.
  await expect(page.getByText("Anthropic needs its workspace ID")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText(/Anthropic is connected/)).toHaveCount(0);
  await capture(page, join(SHOTS, "01-setup-asks-for-the-workspace.png"));

  await page.getByRole("button", { name: "Add the workspace ID" }).click();
  await expect
    .poll(() => page.evaluate(() => document.activeElement?.getAttribute("aria-label")), { timeout: 10_000 })
    .toBe("Anthropic workspace ID");
  await page.keyboard.type(ANTHROPIC_WORKSPACE);
  await page.getByRole("button", { name: "Add workspace" }).click();
  await expect(page.getByText(/\d+ models from Anthropic\./)).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("Anthropic is connected")).toBeVisible();
  await capture(page, join(SHOTS, "02-workspace-added-models-listed.png"));

  // Choose Haiku 5.5 as the default from the provider's own catalogue.
  await page.getByRole("button", { name: "Choose a model" }).last().click();
  await expect(page.getByRole("heading", { name: "Anthropic models" })).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Use Haiku 5.5" }).click();
  await expect(page.getByText(/Haiku 5\.5 is selected/)).toBeVisible({ timeout: 30_000 });
  expect(seen.failures).toEqual([]);
});

test("an instruction in the prompt no longer hides the memory it asks about", async ({ page }) => {
  test.setTimeout(300_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE, OWNER);
  await page.goto(`${BASE}/#/memory?tab=recall`);
  await settled(page);
  const advanced = page.locator("details.advanced");
  if (!(await advanced.evaluate((element) => (element as HTMLDetailsElement).open))) {
    await page.getByText("Advanced memory management").click();
  }
  const file = join(tmpdir(), "round-2026-10-13-tea.json");
  writeFileSync(file, JSON.stringify({ memories: [{ text: TEA, scope: "account" }] }));
  await page.locator('.file-button input[type="file"]').setInputFiles(file);
  await page.getByRole("button", { name: /^Import 1 record$/ }).click();
  await expect(page.getByText(/^Imported 1 record\./)).toBeVisible({ timeout: 30_000 });

  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, HAIKU);
  const answers = page.locator(".message-bubble-raiker");
  const before = await answers.count();
  // BUG-313 — the exact sentence the 2026-10-02 round found recalled nothing.
  await sendTurn(page, "What is my favourite tea? Answer in one sentence.");
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 240_000 });
  await expect.poll(async () => answers.count(), { timeout: 60_000 }).toBeGreaterThan(before);
  await expect(page.getByRole("button", { name: /Remembered \d+/ }).last()).toBeVisible({ timeout: 30_000 });
  await expect(answers.last()).toContainText(/Assam/i, { timeout: 30_000 });
  await capture(page, join(SHOTS, "03-recall-despite-the-instruction.png"));
  expect(seen.failures).toEqual([]);
});

test("Build says where the work is filed and where it runs", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE, OWNER);
  const made = await api(page, "POST", "/api/projects", { name: "Garden planner" });
  // A re-run finds the project the first run made.
  expect([200, 409], JSON.stringify(made.json)).toContain(made.status);
  // The project list is read when the shell loads, so it is read again here.
  await page.goto(`${BASE}/#/build`);
  await page.reload();
  await settled(page);
  const pick = page.getByLabel("Project for this build");
  if (!(await pick.isVisible().catch(() => false))) {
    await page.getByRole("button", { name: /Choose one|project/i }).first().click();
  }
  await page.getByLabel("Project for this build").selectOption({ label: "Garden planner" });
  const line = page.locator(".project-boundary");
  await expect(line).toContainText("Filed in Garden planner", { timeout: 30_000 });
  await expect(line).toContainText("works in live-ws");
  await capture(page, join(SHOTS, "04-build-filed-in-and-works-in.png"));
});

test("the owner's Telegram message is answered over Telegram, and a sensitive reply waits", async ({ page }) => {
  test.setTimeout(420_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE, OWNER);
  execFileSync(PYTHON, [join(REPO, "scripts", "live_channel_reply_harness.py"), WORKSPACE, "telegram", "4242"], {
    encoding: "utf-8",
  });
  const telegram = async (updateId: number, text: string) =>
    api(
      page,
      "POST",
      "/api/channels/channel.telegram/telegram",
      { update_id: updateId, message: { from: { id: 4242 }, chat: { id: 4242, type: "private" }, text } },
      { "X-Telegram-Bot-Api-Secret-Token": INBOUND_SECRET },
    );

  // An ordinary answer is sent back without asking. Telegram does not know the
  // round's bot token, so its refusal is the evidence the send left through
  // the governed path; the receipt says so.
  const plain = await telegram(101, "Say hello in exactly five words.");
  expect(plain.status, JSON.stringify(plain.json)).toBe(200);
  const plainBody = plain.json as Record<string, unknown>;
  expect(plainBody.routed).toBe(true);
  expect(plainBody.status).toBe("completed");
  expect(plainBody.reply_delivery).toBe("failed");

  // An answer carrying an email address is held for the owner.
  const sensitive = await telegram(
    102,
    "Reply with exactly this text and nothing else: write to owner@example.com",
  );
  expect(sensitive.status).toBe(200);
  expect((sensitive.json as Record<string, unknown>).reply_delivery).toBe("held");

  await page.goto(`${BASE}/#/messaging`);
  await settled(page);
  const review = page.getByRole("region", { name: /Telegram deliveries to review/ });
  await expect(review).toBeVisible({ timeout: 30_000 });
  await expect(review.getByText(/Held — it carries sensitive information/)).toBeVisible();
  await expect(review.getByRole("button", { name: "Send to chat" })).toBeVisible();
  await expect(review.getByRole("button", { name: "Discard" })).toBeVisible();
  await expect(review.getByText(/Failed:/)).toBeVisible();
  await capture(page, join(SHOTS, "05-messaging-held-and-failed-replies.png"), review);

  // Replies, as the route now says.
  await page.getByText(/What this route does/).first().click();
  await expect(page.getByText(/Sent back to your chat when you message Raiker/)).toBeVisible();
  await capture(page, join(SHOTS, "06-route-says-replies-go-back.png"));

  // Discard sends nothing and takes it off the list.
  await review.getByRole("button", { name: "Discard" }).click();
  await expect(page.getByText(/Discarded\. Nothing was sent/)).toBeVisible({ timeout: 30_000 });
  await expect(review.getByText(/Held — it carries sensitive information/)).toHaveCount(0);

  // Phone width, dark.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ colorScheme: "dark" });
  await page.reload();
  await settled(page);
  await expect(page.getByRole("region", { name: /Telegram deliveries to review/ })).toBeVisible({ timeout: 30_000 });
  await capture(page, join(SHOTS, "07-messaging-review-390-dark.png"));
  expect(seen.failures).toEqual([]);
});
