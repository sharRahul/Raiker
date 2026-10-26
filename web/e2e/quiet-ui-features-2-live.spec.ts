/**
 * Quiet UI 06, second features round, against a running host and a real model.
 *
 * Prerequisites:
 *   1. A fresh workspace served by
 *      `raiker-web --workspace <ws> --port 8765 --no-browser`.
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` (and, for an identity-linked key,
 *      `RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID`) in this run's environment only.
 *      The key is typed into the product's own dialog; none is written here.
 *
 * The connector and channel set-up steps that have no screen of their own (a
 * manifest, a webhook pairing) go through the same API the page uses, with the
 * signed-in owner's session; everything the owner does is done on the page.
 *
 * Live cases (docs/architecture/WEB_APP_LIVE_TEST.md, "Quiet UI features,
 * second round"): RT-QUI-71 … RT-QUI-80.
 */
import { expect, test, type Locator, type Page } from "@playwright/test";

import { capture } from "./capture";
import { settled } from "./destinations";
import { chooseModelForTurn, keepModelAvailable, signInAsOwner } from "./hosted-provider";
import { ANTHROPIC_KEY as KEY, ANTHROPIC_MODEL as MODEL, LIVE_BASE as BASE } from "./live";

test.describe.configure({ mode: "serial" });

const WORKSPACE_ID = process.env.RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID ?? "";
const SHOTS = process.env.RAIKER_LIVE_SHOTS ?? "../../docs/screenshots/2026-10-26-quiet-ui-features-2";

const MANIFEST = {
  openapi: "3.0.0",
  servers: [{ url: "https://api.github.com" }],
  paths: { "/repos/{owner}/{repo}/issues": { post: { operationId: "createIssue", summary: "Open an issue" } } },
};

async function open(page: Page, hash: string): Promise<void> {
  await page.goto(`${BASE}/${hash}`);
  await settled(page);
}

async function start(page: Page): Promise<void> {
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
}

/** One API call with the signed-in owner's session, as the page makes it. */
async function call(page: Page, method: string, path: string, body?: unknown): Promise<{ status: number; json: unknown }> {
  return page.evaluate(
    async ({ method, path, body }) => {
      const csrf = document.cookie.match(/(?:^|;\s*)raiker_csrf=([^;]*)/);
      const token = sessionStorage.getItem("raiker_token") ?? localStorage.getItem("raiker_token");
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (csrf) headers["X-Raiker-CSRF"] = decodeURIComponent(csrf[1]);
      if (token) headers.Authorization = `Bearer ${token}`;
      const response = await fetch(path, {
        method,
        headers,
        credentials: "same-origin",
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      let json: unknown;
      try {
        json = await response.json();
      } catch {
        json = null;
      }
      return { status: response.status, json };
    },
    { method, path, body },
  );
}

async function finished(page: Page): Promise<Locator> {
  const answer = page.locator(".message-group-raiker").last();
  await expect(answer).toBeVisible({ timeout: 180_000 });
  await expect(page.getByRole("button", { name: "Send", exact: true })).toBeVisible({ timeout: 240_000 });
  await expect(answer.locator(".response-actions")).toBeVisible({ timeout: 240_000 });
  return answer;
}

async function ask(page: Page, prompt: string, hash = "#/new-chat"): Promise<Locator> {
  await open(page, hash);
  // Chat reopens the last conversation; each request here is its own.
  const fresh = page.getByRole("button", { name: "New chat", exact: true });
  if (await fresh.isVisible().catch(() => false)) {
    await fresh.click();
    await expect(page.locator(".message-group-raiker")).toHaveCount(0, { timeout: 30_000 });
  }
  await chooseModelForTurn(page, /Haiku|claude/i);
  await page.getByLabel("Prompt", { exact: true }).fill(prompt);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  return finished(page);
}

test("RT-QUI-71 — Anthropic connects through Add model and becomes the default", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(360_000);
  await start(page);
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
  await review.getByRole("button", { name: "Done" }).click();
  await expect(dialog).toBeHidden();
});

test("RT-QUI-72 — a drawn block is pinned from its toolbar and is in the Library", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(420_000);
  await start(page);
  const answer = await ask(
    page,
    "From our Q3 report: revenue was $1,200, costs were $800 and profit was $400. " +
      "Show these three as key figures (a raiker:figures block with the source 'Q3 report'), then one sentence.",
  );
  const block = answer.locator("section.answer-block").first();
  await expect(block).toBeVisible({ timeout: 30_000 });
  const pin = block.getByRole("button", { name: "Pin to the Library" });
  await expect(pin).toBeVisible();
  await pin.click();
  await expect(block.getByRole("status")).toHaveText("Pinned to the Library", { timeout: 30_000 });
  await expect(block.getByRole("button", { name: "Unpin" })).toHaveAttribute("aria-pressed", "true");
  await capture(page, `${SHOTS}/72-pinned-in-chat.png`, block);

  await open(page, "#/work?tab=library");
  const row = page.locator("li.row[data-kind='block']").first();
  await expect(row).toBeVisible({ timeout: 30_000 });
  await expect(row).toContainText("Key figures");
  await row.locator("button.title").click();
  await expect(row.locator("section.answer-block")).toBeVisible();
  await capture(page, `${SHOTS}/72-library.png`);
});

test("RT-QUI-73 — a pin moves to a project, and the project's limits are set on its page", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(240_000);
  await start(page);
  const existing = await call(page, "GET", "/api/projects");
  let projectId =
    (existing.json as { projects: { project_id: string; name: string }[] }).projects.find(
      (item) => item.name === "Quarterly review",
    )?.project_id ?? "";
  if (!projectId) {
    const created = await call(page, "POST", "/api/projects", { name: "Quarterly review" });
    expect([200, 201]).toContain(created.status);
    projectId = String((created.json as { project_id: string }).project_id);
  }

  await open(page, "#/work?tab=library");
  const row = page.locator("li.row[data-kind='block']").first();
  await row.getByRole("combobox", { name: /^Project for / }).selectOption({ label: "Quarterly review" });
  await expect(page.getByText("Moved to Quarterly review")).toBeVisible({ timeout: 30_000 });
  await expect(row).toContainText("Quarterly review");

  await open(page, `#/work?tab=projects&project=${projectId}`);
  await expect(page.getByRole("heading", { name: "Quarterly review" })).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Set limits" }).click();
  const dialog = page.getByRole("dialog", { name: "Project limits" });
  await dialog.getByLabel("Repositories it may push to").fill("acme/site");
  await dialog.getByLabel("Sites it may read").fill("docs.python.org");
  await dialog.getByRole("button", { name: "Save limits" }).click();
  await expect(page.getByText("Pushes only to acme/site")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Reads web pages only from docs.python.org")).toBeVisible();
  await capture(page, `${SHOTS}/73-project-limits.png`);

  await page.getByRole("tab", { name: "Project library" }).click();
  await expect(page.locator("li.row[data-kind='block']").first()).toBeVisible({ timeout: 30_000 });
  await capture(page, `${SHOTS}/73-project-library.png`);
});

test("RT-QUI-74 — Make this a goal opens the Goals form filled in from the request", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(300_000);
  await start(page);
  const answer = await ask(page, "Help me plan a small vegetable garden for next spring. Two short bullet points.");
  await answer.getByRole("button", { name: "Make this a goal" }).click();
  await expect(page.getByText(/Filled in from “.+”\. Add how you will know it is done/)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByLabel("Outcome")).toHaveValue(/Help me plan a small vegetable garden/);
  await expect(page.getByLabel("Criterion 1 text")).toHaveValue("");
  await capture(page, `${SHOTS}/74-goal-from-chat.png`);
});

test("RT-QUI-75 — the same aim in a second conversation is offered as a goal, once", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(480_000);
  await start(page);
  await ask(page, "Sketch a Berlin marathon training schedule for September in three bullet points.");
  await ask(page, "My Berlin marathon training schedule for September: are the long runs too short? One line.");
  const offer = page.getByRole("complementary", { name: "Suggested goal" });
  await expect(offer).toBeVisible({ timeout: 30_000 });
  await expect(offer).toContainText("This looks like an ongoing goal. Track it?");
  await capture(page, `${SHOTS}/75-goal-noticed.png`, offer);
  await offer.getByRole("button", { name: "Not now" }).click();
  await expect(offer).toBeHidden({ timeout: 30_000 });
  await page.reload();
  await settled(page);
  await expect(page.locator(".message-group-raiker").last()).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole("complementary", { name: "Suggested goal" })).toHaveCount(0);
});

test("RT-QUI-76 — a connection's accounts are named, and another is added with its own credential", async ({ page }) => {
  test.setTimeout(180_000);
  await start(page);
  expect((await call(page, "POST", "/api/connector-store/github/install")).status).toBe(200);
  expect(
    (await call(page, "PUT", "/api/connector-store/github/credentials", { values: { access_token: "live-placeholder-a" } })).status,
  ).toBe(200);
  expect((await call(page, "POST", "/api/connector-store/github/manifest", { manifest: MANIFEST })).status).toBe(200);
  expect((await call(page, "PUT", "/api/connector-store/github/enabled?enabled=true")).status).toBe(200);

  await open(page, "#/connections?tab=services");
  await page.getByRole("option", { name: /GitHub/ }).first().click();
  const accounts = page.locator("section.accounts");
  await expect(accounts).toBeVisible({ timeout: 30_000 });
  await accounts.getByRole("button", { name: /^Rename / }).first().click();
  await accounts.getByLabel("Name for this account").fill("Work GitHub");
  await accounts.getByRole("button", { name: "Save" }).click();
  await expect(accounts.getByText("Work GitHub")).toBeVisible({ timeout: 30_000 });
  await accounts.getByRole("button", { name: /Add another account/ }).click();
  await accounts.getByLabel("Name for the new account").fill("Personal GitHub");
  await accounts.getByRole("button", { name: "Add", exact: true }).click();
  await expect(accounts.getByText("Personal GitHub")).toBeVisible({ timeout: 30_000 });
  const personal = accounts.locator("li").filter({ hasText: "Personal GitHub" });
  await personal.getByRole("button", { name: "Connect" }).click();
  await personal.getByLabel(/OAuth access token for Personal GitHub/).fill("live-placeholder-b");
  await personal.getByRole("button", { name: "Connect" }).click();
  await expect(personal.getByText("Connected")).toBeVisible({ timeout: 30_000 });
  await capture(page, `${SHOTS}/76-named-accounts.png`, accounts);
});

test("RT-QUI-77 — an approved send is held, names its account, and Undo takes it back", async ({ page }) => {
  test.setTimeout(180_000);
  await start(page);
  const listed = await call(page, "GET", "/api/connector-store/github/accounts");
  const personal = (listed.json as { accounts: { account_id: string; label: string }[] }).accounts.find(
    (account) => account.label === "Personal GitHub",
  );
  expect(personal).toBeTruthy();
  const proposed = await call(page, "POST", "/api/connector-store/github/actions", {
    operation_id: "createIssue",
    arguments: { path: { owner: "acme", repo: "site" }, body: { title: "From the live round" } },
    account_id: personal?.account_id,
  });
  expect(proposed.status).toBe(200);
  const approvalId = String((proposed.json as { approval_id: string }).approval_id);

  await open(page, `#/approvals?item=${approvalId}`);
  await expect(page.getByText(/github \(Personal GitHub\) \/ createIssue/)).toBeVisible({ timeout: 30_000 });
  await capture(page, `${SHOTS}/77-account-on-approval.png`);
  await page.getByRole("button", { name: /^Allow once/ }).click();
  await expect(page.getByRole("status").filter({ hasText: /Sending in \d+ s/ })).toBeVisible({ timeout: 10_000 });
  await capture(page, `${SHOTS}/77-sending-undo.png`);
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(page.getByText(/Not sent: you took it back within its undo window/)).toBeVisible({ timeout: 30_000 });
  await capture(page, `${SHOTS}/77-not-sent.png`);
});

test("RT-QUI-78 — a routine's results go to a paired channel only with consent, and its receipt adds up its run", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(420_000);
  await start(page);
  const paired = await call(page, "POST", "/api/channels/pairings", {
    connector_id: "channel.webhooks",
    display_name: "Ops room",
    senders: ["ops"],
  });
  if (paired.status !== 200) {
    // An earlier attempt of this round paired it already.
    const channels = await call(page, "GET", "/api/channels");
    const profile = (channels.json as { profiles: { connector_id: string; pairing_id: string | null }[] }).profiles.find(
      (item) => item.connector_id === "channel.webhooks",
    );
    expect(profile?.pairing_id).toBeTruthy();
  }

  await open(page, "#/work?tab=tasks");
  await chooseModelForTurn(page, /Haiku|claude/i, "Plan work");
  await page.getByLabel("What should Raiker do?").fill("Reply with one short sentence saying the daily check ran.");
  await page.getByRole("button", { expanded: false, name: /Runs|Once|Daily|Hourly|Weekly|Every/ }).first().click();
  const channel = page.getByRole("combobox", { name: "Channel for results" });
  await expect(channel).toBeDisabled();
  await page.getByRole("checkbox", { name: /Also send each result to/ }).check();
  await expect(page.getByText(/without asking again, while that channel is on/)).toBeVisible();
  await capture(page, `${SHOTS}/78-consent.png`);
  await page.getByRole("button", { name: /Create task/ }).click();

  const card = page.locator("article").filter({ hasText: "Reply with one short sentence" }).first();
  await expect(card.getByText(/Also to Ops room/)).toBeVisible({ timeout: 60_000 });
  // The run finishes on its own; its conversation then has a turn to add up.
  await expect
    .poll(
      async () => {
        await open(page, "#/work?tab=tasks");
        return page.getByTestId("task-receipt").count();
      },
      { timeout: 300_000, intervals: [5_000] },
    )
    .toBeGreaterThan(0);
  // Finished, it is under Finished work, with where its result also went.
  const finished = page.locator(".history-row").filter({ hasText: "Reply with one short sentence" }).first();
  await expect(finished).toContainText("Also sent to Ops room · the last one was not sent", { timeout: 30_000 });
  const receipt = finished.getByTestId("task-receipt");
  await receipt.locator("summary").click();
  await expect(receipt).toContainText(/Across 1 turn ·/, { timeout: 30_000 });
  await capture(page, `${SHOTS}/78-task-receipt.png`, finished);
  // The channel's own gate is off on a fresh workspace, so the send was refused
  // and the routine says so rather than looking delivered.
  const deliveries = await call(page, "GET", "/api/routine-deliveries");
  const row = (deliveries.json as { deliveries: { last_status: string | null }[] }).deliveries[0];
  expect(row.last_status).toBe("not_delivered");
});

test("RT-QUI-79 — choosing a project in the composer puts the chat under its limits", async ({ page }) => {
  test.setTimeout(120_000);
  await start(page);
  const projects = await call(page, "GET", "/api/projects");
  const project = (projects.json as { projects: { project_id: string; name: string }[] }).projects.find(
    (item) => item.name === "Quarterly review",
  );
  expect(project).toBeTruthy();
  await open(page, "#/new-chat");
  const composer = page.getByRole("group", { name: "Message composer" });
  for (const trigger of ["Add to this turn", "Tools"]) {
    await composer.getByRole("button", { name: trigger, exact: true }).click();
    const item = page.getByRole("menuitem", { name: "Work in a project" });
    if (await item.isVisible().catch(() => false)) {
      await item.click();
      break;
    }
    await page.keyboard.press("Escape");
  }
  await page.getByLabel("Project for this chat").selectOption({ label: "Quarterly review" });
  await expect(page.getByText("Project limits apply")).toBeVisible({ timeout: 30_000 });
  await capture(page, `${SHOTS}/79-composer-limits.png`);
});

test("RT-QUI-80 — rewriting Raiker's change offers to remember why, in the owner's words", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(420_000);
  await start(page);
  await open(page, "#/new-chat");
  await chooseModelForTurn(page, /Haiku|claude/i);
  await page
    .getByLabel("Prompt", { exact: true })
    .fill(
      "Use the apply_patch tool (not write_file) to create notes/todo.md containing the single line 'buy milk'. " +
        "Do not ask me anything first.",
    );
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.locator("[data-raiker-safety]").last()).toBeVisible({ timeout: 240_000 });
  await open(page, "#/approvals");
  await page.getByTestId("approval-row").first().click();
  const edit = page.getByRole("button", { name: "Edit…" });
  await expect(edit).toBeVisible({ timeout: 60_000 });
  await edit.click();
  const patch = page.getByLabel("Your version of this change");
  const text = await patch.inputValue();
  await patch.fill(text.replace("buy milk", "buy oat milk"));
  await page.getByRole("button", { name: "Propose as a new change" }).click();
  const offer = page.getByRole("form", { name: "Remember why you changed it" });
  await expect(offer).toBeVisible({ timeout: 30_000 });
  // The routine of RT-QUI-78 left notices docked over the right column; the
  // owner closes them as they would (recorded in TO_BE_FIXED).
  const notices = page.getByRole("region", { name: "Notifications" }).or(page.locator("section.notifications"));
  for (let round = 0; round < 5; round += 1) {
    const dismiss = notices.getByRole("button", { name: /^Dismiss: / }).first();
    if (!(await dismiss.isVisible().catch(() => false))) break;
    await dismiss.click();
  }
  await offer.getByLabel(/Anything to remember for next time/).fill("I drink oat milk, not cow's milk.");
  await offer.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText(/Remembered\./)).toBeVisible({ timeout: 30_000 });
  await capture(page, `${SHOTS}/80-edited-draft-memory.png`);
});
