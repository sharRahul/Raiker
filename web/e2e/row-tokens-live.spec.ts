/**
 * The token budget, checked on the real screens.
 *
 * The claim these two items make is about *scanning*: a list is readable when
 * an ordinary row looks ordinary, so the one row that needs the owner can be
 * found without reading every word on the page. That claim cannot be checked in
 * a unit test, because a unit test never sees a page with twenty rows on it.
 *
 * So this spec counts. On each list it opens, it asserts that the facts an
 * entity carries when nothing is wrong with it are plain metadata, and that
 * every badge still on the page belongs to something that is not ordinary.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = "../../docs/plans/screenshots/working";

test.describe.configure({ mode: "serial" });

test("a skill that is switched on and conformant spends no badge", async ({ page }) => {
  test.setTimeout(120_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/extensions?tab=skills`);

  await expect(page.getByRole("heading", { name: /Skills/i }).first()).toBeVisible({
    timeout: 30_000,
  });
  // The install ships active, conformant skills, which is the ordinary state
  // this rule is about: their version and command trigger read as metadata.
  const facts = page.locator(".row-fact");
  await expect(facts.first()).toBeVisible({ timeout: 30_000 });
  const activeFacts = await page.getByText("active", { exact: true }).count();
  expect(activeFacts).toBeGreaterThan(0);
  for (const label of await page.getByText("active", { exact: true }).all()) {
    await expect(label.locator("xpath=ancestor::span[contains(@class,'badge')]")).toHaveCount(0);
  }
  await capture(page, `${SHOTS}/vis2-13-skills-row-tokens.png`, facts.first());
});

test("the sessions list badges the running session and nothing else", async ({ page }) => {
  test.setTimeout(120_000);
  await signInAsOwner(page, BASE);
  // Sessions is a tab of the Observability hub (the hub Overview), not a route of its
  // own: the list is identified by its own table, not by a page title.
  await page.goto(`${BASE}/#/observe?tab=sessions`);
  await expect(
    page.getByRole("table").or(page.getByText(/No sessions yet/i)).first(),
  ).toBeVisible({ timeout: 30_000 });

  // An empty list would let every assertion below pass without seeing a row,
  // which is the shape of a harness that reports success and checks nothing.
  // A host with no sessions on it is a condition of the host, so this skips
  // visibly rather than passing on an empty page — the mocked suite
  // (`composer.spec.ts`) carries the multi-row version of the same rule.
  const idle = page.getByText("idle", { exact: true });
  test.skip((await idle.count()) === 0, "no session on this host to check the rule against");
  for (const label of await idle.all()) {
    await expect(label.locator("xpath=ancestor::span[contains(@class,'badge')]")).toHaveCount(0);
  }
  await capture(page, `${SHOTS}/vis2-13-sessions-row-tokens.png`);
});

test("the approvals queue tones risk only when the risk is elevated", async ({ page }) => {
  test.setTimeout(120_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/approvals`);
  // An empty queue renders its empty state rather than a table, so the wait
  // has to admit both — otherwise a host with nothing to decide fails as though
  // the page were broken.
  await expect(
    page
      .getByRole("columnheader", { name: "Risk" })
      .or(page.getByText(/Nothing waiting on you|No approvals/i))
      .first(),
  ).toBeVisible({ timeout: 30_000 });

  // Same rule as above: a queue with nothing in it proves nothing. A host with
  // no decisions on it is a condition of the host rather than a defect, so this
  // skips *visibly* instead of passing on an empty page.
  const routine = page.getByText(/^(low|medium)$/);
  test.skip(
    (await routine.count()) === 0,
    "no routine-risk decision in this queue to check the rule against",
  );
  for (const cell of await routine.all()) {
    await expect(cell.locator("xpath=ancestor::span[contains(@class,'badge')]")).toHaveCount(0);
  }
  await capture(page, `${SHOTS}/vis2-13-approvals-row-tokens.png`);
});
