/** QUI-G06: Approvals, Library and Sessions recovery against a running host.
 *
 * The approval is real: a connected hosted model (connected beforehand through
 * Models, never seeded) proposes a file write, and the final decision is made
 * through the host. Failures are explicit HTTP 503 answers injected in the
 * browser, so a failed decision, unpin, move or delete never reaches the host.
 * Library pin rows are a declared fixture; the host has no pinned block yet.
 */
import { expect as baseExpect, test, type Page } from "@playwright/test";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE, sendTurn } from "./live";
import { capture } from "./capture";

const expect = baseExpect.configure({ timeout: 30_000 });
const failed = { status: 503, json: { detail: { reason_code: "injected_failure" } } };
const SHOTS = "../../output/playwright/2026-11-06-approvals-library-sessions-recovery";
const SESSIONS_LIST = /\/api\/sessions(\?.*)?$/;
const DETAIL = /\/api\/approvals\/(?!lapsed)[^/?]+$/;
test.describe.configure({ mode: "serial", timeout: 240_000 });

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await signInAsOwner(page, BASE);
});

async function openApprovals(page: Page) {
  await page.goto(`${BASE}/#/approvals`);
  await expect(page.getByRole("listbox").or(page.getByText("Nothing waiting on you", { exact: true }))).toBeVisible();
}

test("RT-APPROVAL-RECOVERY-01: a real model proposes a write that waits for a decision", async ({ page }) => {
  const pendingRead = (r: { url(): string; request(): { method(): string } }) =>
    r.url().includes("/api/approvals?status_filter=pending") && r.request().method() === "GET";
  const first = page.waitForResponse(pendingRead);
  await openApprovals(page);
  const before = new Set(((await (await first).json()) as { approval_id: string }[]).map((a) => a.approval_id));
  await page.goto(`${BASE}/#/new-chat`);
  await sendTurn(
    page,
    "Use the write_file tool now to create the file approval-recovery.md containing exactly the line: recovery check. Do not ask me anything first.",
  );
  // Opened while the turn is still working: the queue must pick the decision up
  // when the top bar's count changes, without a Refresh (found this round).
  await page.getByRole("link", { name: /^Approvals/ }).first().click();
  let raised: { approval_id: string }[] = [];
  await expect
    .poll(
      async () => {
        const response = await page.waitForResponse(pendingRead, { timeout: 30_000 }).catch(() => null);
        if (response) raised = (await response.json()) as { approval_id: string }[];
        return raised.some((a) => !before.has(a.approval_id));
      },
      { timeout: 180_000 },
    )
    .toBe(true);
  await expect(page.getByRole("listbox").getByRole("option")).toHaveCount(raised.length);
  await expect(page.getByRole("button", { name: "Refresh approvals", exact: true })).toBeVisible();
  await capture(page, `${SHOTS}/01-raised-while-open.png`);
});

test("RT-APPROVAL-RECOVERY-02: a failed refresh keeps the queue and Retry approvals recovers", async ({ page }) => {
  await openApprovals(page);
  await page.route("**/api/approvals?*", (route) => route.fulfill(failed));
  await page.getByRole("button", { name: "Refresh approvals", exact: true }).click();
  const alert = page.getByRole("alert").filter({ hasText: "Approvals could not be read" });
  await expect(alert).toContainText("HTTP 503");
  await expect(alert).toContainText("may be out of date");
  await expect(page.getByRole("listbox").getByRole("option").first()).toBeVisible();
  await capture(page, `${SHOTS}/02-queue-refresh.png`);
  await page.unroute("**/api/approvals?*");
  await page.getByRole("button", { name: "Retry approvals", exact: true }).click();
  await expect(alert).toHaveCount(0);
});

test("RT-APPROVAL-RECOVERY-03: an approval that cannot be opened offers Open it again", async ({ page }) => {
  await page.route(DETAIL, (route) => (route.request().method() === "GET" ? route.fulfill(failed) : route.continue()));
  await openApprovals(page);
  await page.getByRole("listbox").getByRole("option").first().click();
  await expect(page.getByRole("alert").filter({ hasText: "This approval could not be opened" })).toContainText("nothing was decided");
  await capture(page, `${SHOTS}/03-detail.png`);
  await page.unroute(DETAIL);
  await page.getByRole("button", { name: "Open it again", exact: true }).click();
  await expect(page.getByRole("button", { name: /^Allow once/ })).toBeVisible();
});

test("RT-APPROVAL-RECOVERY-04: a lost decision says check History; the real decision then executes", async ({ page }) => {
  await openApprovals(page);
  await page.getByRole("listbox").getByRole("option").first().click();
  await page.route("**/api/approvals/*/resolve", (route) => route.fulfill(failed));
  await page.getByRole("button", { name: /^Allow once/ }).click();
  const notice = page.locator(".notice-danger").filter({ hasText: "Allowing this was not confirmed" });
  await expect(notice).toContainText("check History for this approval before deciding again");
  await capture(page, `${SHOTS}/04-decision.png`);
  await page.unroute("**/api/approvals/*/resolve");
  // The injected failure never reached the host: the approval is still waiting.
  await page.getByRole("button", { name: "Refresh approvals", exact: true }).click();
  await page.getByRole("listbox").getByRole("option").first().click();
  await page.getByRole("button", { name: /^Allow once/ }).click();
  await expect(page.locator(".notice-ok").filter({ hasText: /Executed once|Recorded/ })).toBeVisible({ timeout: 60_000 });
});

test("RT-APPROVAL-RECOVERY-05: History read failure in dark theme recovers", async ({ page }) => {
  await openApprovals(page);
  await page.evaluate(() => { document.documentElement.dataset.theme = "dark"; });
  await page.route("**/api/approvals?*", (route) => route.fulfill(failed));
  await page.getByRole("tab", { name: /^History/ }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Approval history could not be read" })).toContainText("Retry approvals");
  await capture(page, `${SHOTS}/05-history-dark.png`);
  await page.unroute("**/api/approvals?*");
  await page.getByRole("button", { name: "Retry approvals", exact: true }).click();
  await expect(page.getByRole("listbox").getByRole("option").first()).toBeVisible();
});

const PIN = {
  item_id: "block:pin_fixture",
  kind: "block",
  title: "Recovery fixture figures",
  detail: "Key figures",
  project_id: null,
  project_name: null,
  session_id: null,
  session_title: null,
  turn_id: null,
  external: false,
  href: "#/new-chat",
  download_url: null,
  pin_id: "pin_fixture",
  block: { type: "callout", data: { tone: "verdict", text: "Declared fixture." } },
  created_at: "2026-11-06T09:00:00Z",
};

test("RT-LIBRARY-RECOVERY-01: Library read, unpin and move failures name a check-first step", async ({ page }) => {
  await page.route("**/api/library?*", (route) => route.fulfill(failed));
  await page.route("**/api/library", (route) => route.fulfill(failed));
  await page.goto(`${BASE}/#/work?tab=library`);
  await expect(page.getByRole("alert").filter({ hasText: "The Library could not be read" })).toContainText("nothing was removed");
  await capture(page, `${SHOTS}/06-library-read.png`);
  await page.unroute("**/api/library?*");
  await page.unroute("**/api/library");
  await page.getByRole("button", { name: "Retry Library", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "The Library could not be read" })).toHaveCount(0);

  await page.route(/\/api\/library(\?.*)?$/, (route) => route.fulfill({ json: { items: [PIN], kinds: [] } }));
  await page.route("**/api/library/pins/**", (route) => route.fulfill(failed));
  await page.reload();
  const title = page.getByRole("button", { name: PIN.title, exact: true });
  await expect(title).toBeVisible();
  await page.locator("li").filter({ has: title }).getByRole("button", { name: "Unpin", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Unpinning Recovery fixture figures was not confirmed" })).toContainText(
    "check whether it is still pinned",
  );
  await expect(title).toBeVisible();
  await capture(page, `${SHOTS}/07-library-unpin.png`);
});

test("RT-SESSIONS-RECOVERY-01: Sessions refresh, detail and delete failures keep what was read", async ({ page }) => {
  await page.goto(`${BASE}/#/observe?tab=sessions`);
  const firstRow = page.locator("table.table tbody tr").first();
  await expect(firstRow).toBeVisible();
  await page.route(SESSIONS_LIST, (route) => route.fulfill(failed));
  await page.getByRole("button", { name: "Refresh sessions", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Sessions could not be read" })).toContainText("may be out of date");
  await expect(firstRow).toBeVisible();
  await page.unroute(SESSIONS_LIST);
  await page.getByRole("button", { name: "Retry sessions", exact: true }).first().click();
  await expect(page.getByRole("alert").filter({ hasText: "Sessions could not be read" })).toHaveCount(0);

  await page.route(/\/api\/sessions\/sess_[^/?]+$/, (route) => (route.request().method() === "GET" ? route.fulfill(failed) : route.continue()));
  await firstRow.locator("td").nth(1).click();
  await expect(page.getByRole("alert").filter({ hasText: "This session could not be opened" })).toContainText("nothing was changed");
  await page.unroute(/\/api\/sessions\/sess_[^/?]+$/);
  await page.getByRole("button", { name: "Open it again", exact: true }).click();
  await expect(page.locator("#session-detail-h")).toBeVisible();

  await page.route("**/api/sessions/bulk", (route) => route.fulfill(failed));
  await firstRow.locator("td.check-col").click();
  await page.getByRole("button", { name: /Delete selected/ }).click();
  const confirm = page.getByRole("dialog");
  await confirm.getByRole("button", { name: "Delete", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Deleting the selected conversations was not confirmed" })).toContainText(
    "check which are still listed",
  );
  await expect(page.getByText("1 selected", { exact: true })).toBeVisible();
  await capture(page, `${SHOTS}/08-sessions-delete.png`);
});
