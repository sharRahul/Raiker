/**
 * The 2026-10-05 (third) round, Build half: BUG-317 on a real turn.
 *
 * A Build turn on Anthropic proposes a shell command; Build lists it under
 * **Waiting on you** with Accept beside it, and the shell's floating approval
 * card — which used to appear over the end of that card offering the same
 * decision — must not. Runs on the same host and workspace as
 * `round-2026-10-05-quiet-hours-live.spec.ts`, after it.
 */
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { settled } from "./destinations";
import { chooseModelForTurn, signInAsOwner } from "./hosted-provider";
import { LIVE_BASE, useAnthropic } from "./live";

const BASE = LIVE_BASE;
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-10-05-quiet-hours-round");
const PROJECT_NAME = "Quiet round build";

async function api<T>(page: Page, method: string, path: string, body?: unknown): Promise<T> {
  return page.evaluate(
    async ({ method, path, body }) => {
      const csrf = document.cookie.match(/(?:^|; )raiker_csrf=([^;]+)/)?.[1];
      const response = await fetch(path, {
        method,
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          ...(csrf ? { "X-Raiker-CSRF": decodeURIComponent(csrf) } : {}),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      return (await response.json()) as T;
    },
    { method, path, body },
  );
}

async function setCapability(page: Page, label: string, reason: string) {
  await page.goto(`${BASE}/#/capabilities`);
  const search = page.getByLabel("Search capabilities", { exact: true });
  await expect(search).toBeVisible({ timeout: 30_000 });
  await search.fill(label);
  const card = page.locator(".cap.card").filter({ hasText: label }).first();
  await expect(card).toBeVisible();
  const toggle = card.getByRole("button", { name: label });
  if ((await toggle.getAttribute("aria-expanded")) !== "true") await toggle.click();
  const turnOn = card.getByRole("button", { name: "Turn on" });
  if (!(await turnOn.isVisible().catch(() => false))) return;
  await turnOn.click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Reason (required)").fill(reason);
  const token = dialog.getByLabel(/Confirmation token/);
  if (await token.isVisible().catch(() => false)) await token.fill("CONFIRM");
  const acknowledgement = dialog.getByRole("checkbox");
  if (await acknowledgement.isVisible().catch(() => false)) await acknowledgement.check();
  await dialog.getByRole("button", { name: "Confirm change" }).click();
  await expect(dialog).toBeHidden({ timeout: 30_000 });
}

test("BUG-317: Build's own decision is not repeated by a card over it", async ({ page }) => {
  test.setTimeout(600_000);
  await signInAsOwner(page, BASE);
  await useAnthropic(page);
  await setCapability(page, "Shell commands", "BUG-317 live acceptance");
  await page.goto(`${BASE}/#/projects`);
  await settled(page);
  // Re-runnable: a decision an earlier attempt left pending is a *different*
  // decision, and floating it is right; deny it so only this turn's is pending.
  const leftover = await api<{ approval_id: string }[]>(page, "GET", "/api/approvals");
  for (const item of leftover) {
    await api(page, "POST", `/api/approvals/${item.approval_id}/resolve`, { approve: false, reason: "earlier attempt" });
  }
  const listed = await api<{ projects?: { name: string }[] }>(page, "GET", "/api/projects");
  if (!(listed.projects ?? []).some((project) => project.name === PROJECT_NAME)) {
    await api(page, "POST", "/api/projects", { name: PROJECT_NAME });
  }
  await page.goto(`${BASE}/#/build`);
  await page.reload();
  await settled(page);
  await page.getByRole("button", { name: "Add to this turn" }).first().click();
  await page.getByRole("menuitem", { name: "Work in a project" }).click();
  const picker = page.getByLabel("Project for this build");
  await expect(picker).toBeVisible({ timeout: 30_000 });
  await picker.selectOption({ label: PROJECT_NAME });
  await chooseModelForTurn(page, /Haiku 4\.5/, "Build composer");
  await page
    .getByLabel("Describe the change")
    .fill("Run the shell command `echo quiet-round` with the shell tool and tell me what it printed. Do nothing else.");
  const run = page.getByRole("button", { name: /^(Run|Plan|Propose)$/ }).first();
  await expect(run).toBeEnabled({ timeout: 60_000 });
  await run.click();

  const decisions = page.locator("section.decisions");
  await expect(decisions).toBeVisible({ timeout: 240_000 });
  await expect(decisions.getByRole("button", { name: "Accept", exact: true }).first()).toBeVisible();
  // The floating card polls every five seconds; give it two chances to appear.
  await page.waitForTimeout(11_000);
  await expect(page.getByRole("region", { name: "Approval needed" })).toBeHidden();
  await capture(page, join(SHOTS, "17-build-decision-not-repeated.png"));

  // On another page the same pending decision does float — it is only the
  // page already showing it that is spared the duplicate.
  await page.goto(`${BASE}/#/home`);
  await settled(page);
  await expect(page.getByRole("region", { name: "Approval needed" })).toBeVisible({ timeout: 30_000 });
  await capture(page, join(SHOTS, "18-same-decision-floats-elsewhere.png"));
  await page.goBack();
  await settled(page);
  await decisions.getByRole("button", { name: "Accept", exact: true }).first().click();
  await expect(page.getByText(/quiet-round/).first()).toBeVisible({ timeout: 240_000 });
});
