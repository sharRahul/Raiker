/**
 * BUG-225 — the channel surface, against a real instance.
 *
 * The finding this closes is not "channels do not exist". The outbound
 * executor, the inbound receiver, the `external_channel_runtime` capability and
 * the channel egress boundary were all built and had **no owner surface**, so
 * `list_channel_pairings` stayed empty, both executors refused, and the tab
 * reported that channels did not exist. The transport was unreachable because
 * there was no way in.
 *
 * What has to be true on screen, and each is a test:
 *
 * 1. The tab states what a channel message **is** — untrusted content with a
 *    named sender who is not the owner.
 * 2. Linked, enabled and trusted read as three separate facts. Pairing must not
 *    look like switching on.
 * 3. The three things that gate delivery — the capability, the egress allowlist
 *    and the inbound secret — are reported separately, because each has a
 *    different remedy.
 * 4. Unpairing is what actually stops a channel, and the surface agrees.
 */
import { expect, test } from "@playwright/test";
import { dismissFirstRunModelSetup } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = "../../docs/plans/screenshots/working";

async function signIn(page: import("@playwright/test").Page) {
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 15_000 });
  await page.getByLabel("Username").fill("Rahul");
  await page.getByLabel("Password", { exact: true }).fill("Ithink@10");
  const confirm = page.getByLabel("Confirm password");
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill("Ithink@10");
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await page.getByRole("button", { name: "Unlock Raiker", exact: true }).click();
  }
  const workbench = page.getByRole("heading", { name: /Welcome (to your Work Dashboard|back)/ });
  await expect(
    page.getByRole("button", { name: "Decide later" }).or(workbench).first(),
  ).toBeVisible({ timeout: 60_000 });
  await dismissFirstRunModelSetup(page);
  await expect(workbench.first()).toBeVisible({ timeout: 30_000 });
}

const channels = (page: import("@playwright/test").Page) =>
  page.goto(`${BASE}/#/extensions?tab=channels`);

const webhookRow = (page: import("@playwright/test").Page) =>
  page
    .getByTestId("channel-profiles")
    .getByText("Webhooks", { exact: true })
    .locator("xpath=ancestor::li[1]");

test.describe.configure({ mode: "serial" });

test("the tab states what a channel message is (BUG-225)", async ({ page }) => {
  test.setTimeout(180_000);
  await signIn(page);
  await channels(page);

  await expect(page.getByRole("heading", { name: "What a channel message is" })).toBeVisible({
    timeout: 30_000,
  });
  await expect(
    page.getByText(/untrusted content with a named sender who is not you/i),
  ).toBeVisible();

  // The three gates, each its own row: one is a capability the owner sets, one
  // is an environment allowlist, one is an inbound secret. Different remedies.
  const posture = page.getByTestId("channel-posture");
  for (const fact of ["Outbound", "Egress", "Signing", "Inbound", "Rate limit"]) {
    await expect(posture.getByText(fact, { exact: true })).toBeVisible();
  }

  // Each row's chip has to agree with what the server actually said. The first
  // version of this page reported "Secret set" while the receiver was refusing
  // every message, because the API's redaction filter replaced the boolean
  // `secret_configured` with a *non-empty string* and the template read it as
  // truthy. A test that only checked the rows existed would have passed.
  const served = await page.evaluate(async () => {
    const response = await fetch("/api/channels", {
      headers: { Authorization: `Bearer ${(window as never as { __raikerToken?: string }).__raikerToken ?? ""}` },
    });
    return response.ok ? await response.json() : null;
  });
  const inboundRow = posture.getByText("Inbound", { exact: true }).locator("xpath=ancestor::li[1]");
  if (served !== null) {
    await expect(inboundRow).toContainText(
      served.inbound.secret_configured ? "Secret set" : "Refusing everything",
    );
  } else {
    // No token in page scope: assert the invariant that caught the bug — the
    // chip can never be the redaction marker, whatever the underlying state.
    await expect(inboundRow).not.toContainText("REDACTED");
    await expect(inboundRow).toContainText(/Secret set|Refusing everything/);
  }

  // Allowlisting says *who* may speak; the budget says how often. An allowlisted
  // sender was unbounded until this row existed.
  await expect(
    posture.getByText("Rate limit", { exact: true }).locator("xpath=ancestor::li[1]"),
  ).toContainText(/\d+\/min/);

  await page.screenshot({ path: `${SHOTS}/bug-225-channel-surface.png`, fullPage: true });
});

test("every connector profile is offered, and none is linked to begin with", async ({ page }) => {
  test.setTimeout(180_000);
  await signIn(page);
  await channels(page);

  const profiles = page.getByTestId("channel-profiles");
  await expect(profiles).toBeVisible({ timeout: 30_000 });
  await expect(profiles.locator("li")).not.toHaveCount(0);
  await expect(webhookRow(page)).toContainText("Not linked");
  await expect(webhookRow(page).getByRole("button", { name: "Pair" })).toBeVisible();
});

test("pairing links a channel without switching it on", async ({ page }) => {
  test.setTimeout(180_000);
  await signIn(page);
  await channels(page);

  await webhookRow(page).getByRole("button", { name: "Pair" }).click();
  // This profile requires a sender allowlist, so pairing has to ask for one —
  // that is the profile's declaration becoming enforcement.
  const form = webhookRow(page).locator("form");
  await expect(form).toBeVisible();
  await form.getByLabel("Allowed senders").fill("ops, oncall");
  // Scoped to *this* row's form. Every unpaired row carries its own Pair button,
  // so a document-wide match submits whichever one happens to be last.
  await form.getByRole("button", { name: "Pair", exact: true }).click();

  await expect(page.getByText(/It is switched off until you turn it on/i)).toBeVisible({
    timeout: 30_000,
  });
  const row = webhookRow(page);
  await expect(row).toContainText("Linked, off");
  await expect(row).toContainText("2 senders");
  await expect(row.getByRole("button", { name: "Turn on" })).toBeVisible();

  await page.screenshot({ path: `${SHOTS}/bug-225-channel-paired.png`, fullPage: true });
});

test("turning it on is a second decision, and a test delivery runs the governed path", async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signIn(page);
  await channels(page);

  await webhookRow(page).getByRole("button", { name: "Turn on" }).click();
  await expect(webhookRow(page)).toContainText("On", { timeout: 30_000 });

  await webhookRow(page).getByRole("button", { name: "Send a test delivery" }).click();
  await page.getByLabel("Destination URL").fill("https://hooks.example.invalid/x");
  await page.getByRole("button", { name: "Send", exact: true }).click();

  // The egress allowlist is empty on this instance, so the refusal has to come
  // from the boundary and has to be readable — not a raw reason code.
  await expect(
    page.getByText(
      /not on the channel egress allowlist|could not be reached|capability is turned off/i,
    ),
  ).toBeVisible({ timeout: 60_000 });

  await page.screenshot({ path: `${SHOTS}/bug-225-channel-delivery-refused.png`, fullPage: true });
});

test("unpairing is what stops it, and the surface agrees", async ({ page }) => {
  test.setTimeout(180_000);
  await signIn(page);
  await channels(page);

  await webhookRow(page).getByRole("button", { name: "Unpair" }).click();
  await expect(page.getByText(/Nothing can reach it now/i)).toBeVisible({ timeout: 30_000 });
  await expect(webhookRow(page)).toContainText("Not linked");
  await expect(webhookRow(page).getByRole("button", { name: "Turn on" })).toHaveCount(0);
});

test("the channels tab fits and keeps its icons at every width", async ({ page }) => {
  test.setTimeout(240_000);
  await signIn(page);
  for (const [label, viewport] of [
    ["mobile", { width: 390, height: 844 }],
    ["tablet", { width: 834, height: 1112 }],
    ["desktop", { width: 1440, height: 1000 }],
  ] as const) {
    await page.setViewportSize(viewport);
    await channels(page);
    await expect(page.getByTestId("channel-profiles")).toBeVisible({ timeout: 30_000 });
    await page.mouse.move(2, 2);
    await page.waitForTimeout(400);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow, `channels overflows at ${label}`).toBeLessThanOrEqual(1);
    await page.screenshot({ path: `${SHOTS}/bug-225-channels-${label}.png`, fullPage: true });
  }
});
