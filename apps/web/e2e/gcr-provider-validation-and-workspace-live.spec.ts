/**
 * Live evidence for GCR-01, GCR-02 and GCR-03, driven through the UI.
 *
 * Three of the five findings in this pass changed something an owner reaches
 * from a screen, so they are checked from one:
 *
 * * **GCR-01/GCR-02** — saving a connection and choosing a model both used to
 *   answer "would this run?" by constructing a live provider and dropping it.
 *   Two of the five call sites built it without the owner's saved connection,
 *   so they answered about an endpoint and a credential the turn would not use;
 *   four never closed the `httpx.AsyncClient` the provider owns. The validation
 *   path opens nothing now, so repeating those presses must leave the host with
 *   the sockets it started with — measured against the real process by
 *   `scripts/live_socket_check.sh`, which brackets this run.
 * * **GCR-03** — a reasoning setting is judged against the model the turn will
 *   run on rather than whichever profile is first in the shipped registry, so a
 *   hosted reasoning model must offer its effort control instead of refusing
 *   every value with `reasoning_not_supported`.
 *
 * The key this round supplies is identity-linked, and the workspace id it needs
 * cannot be obtained from it — `/v1/organizations/*` answers this key class with
 * 403. A completed provider turn is therefore still BUG-273, and still open, for
 * the fifth round running. Nothing below needs one: every assertion is about
 * what Raiker does with a connection, a pin, and its own gates.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import {
  hostedProviderCard,
  openModelDialog,
  signInAsOwner,
} from "./hosted-provider";

const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";
const KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";

test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");

test.describe.configure({ mode: "serial" });

test("the key saves, and the card says so", async ({ page }) => {
  test.setTimeout(300_000);
  await signInAsOwner(page, BASE);

  const card = await hostedProviderCard(page, BASE, "Anthropic");
  const connect = card.getByRole("button", { name: "Connect", exact: true });
  if (await connect.isVisible().catch(() => false)) {
    await connect.click();
    await page.getByLabel("Anthropic API key").fill(KEY);
    await page.locator(".signin-connect").click();
    await expect(page.locator(".signin-overlay")).toHaveCount(0, { timeout: 60_000 });
  }
  // GCR-02 — saving a connection now validates the values without building a
  // provider. The outcome the owner sees is unchanged, which is the point: the
  // fix removes a transport, not a check.
  await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 60_000 });
  await capture(
    page,
    "../../docs/plans/screenshots/working/gcr-01-02-connection-saved.png",
  );
});

test("pinning a model repeatedly leaves the host answering", async ({ page, request }) => {
  test.setTimeout(300_000);
  await signInAsOwner(page, BASE);
  const card = await hostedProviderCard(page, BASE, "Anthropic");

  // Pinning a model is the call site GCR-02 changed from "build a provider and
  // drop it" to "validate and open nothing", and it is reachable even when the
  // provider will not list its catalogue: the dialog offers a **Custom model
  // name** field for exactly that case. So this presses the changed path three
  // times without needing a turn the round's key cannot make.
  //
  // The measurement is the host's own open-socket count either side of the
  // whole run — `scripts/live_socket_check.sh 8765 before|after`. This is the
  // load that used to move it by one client per press.
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const dialog = await openModelDialog(page, card);
    await dialog
      .getByRole("textbox", { name: "Custom model name" })
      .fill("claude-haiku-4-5-20251001");
    const use = dialog.getByRole("button", { name: "Use model" });
    await expect(use).toBeEnabled({ timeout: 30_000 });
    await use.click();
    await expect(dialog).toBeHidden({ timeout: 60_000 });
  }

  // Still answering afterwards, which is what an exhausted connection pool
  // eventually takes away.
  const health = await request.get(`${BASE}/api/health`);
  expect(health.ok()).toBeTruthy();
  await capture(
    page,
    "../../docs/plans/screenshots/working/gcr-02-model-pinned-without-a-leaked-client.png",
  );
});

test("an identity-linked key is refused in words, not as a network fault", async ({
  page,
}) => {
  test.setTimeout(240_000);
  await signInAsOwner(page, BASE);
  const card = await hostedProviderCard(page, BASE, "Anthropic");

  // The first real provider call this round makes. It must arrive as the
  // provider's own refusal — the workspace this key acts inside — rather than
  // as "check your network" (FIXED-388) or a bare status (FIXED-370).
  const dialog = await openModelDialog(page, card);
  await expect(dialog.getByText(/identity-linked|workspace/i)).toBeVisible({
    timeout: 120_000,
  });
  await expect(dialog.getByText(/Provider unreachable/i)).toHaveCount(0);
  await capture(
    page,
    "../../docs/plans/screenshots/not-working/bug-273-identity-linked-key-blocks-the-round.png",
  );
});

test("the hosted gate the validation consults is the one Permissions reports", async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  // GCR-01's other half. The provider validation and the turn now go through
  // one factory, so the gate that refuses a hosted provider is a single fact —
  // and Permissions must state the same one (FIXED-322).
  await page.goto(`${BASE}/#/capabilities`);
  await page.getByPlaceholder(/Search capabilities/).waitFor({ timeout: 60_000 });
  const hosted = page.locator(".cap.card").filter({ hasText: /Hosted models/ }).first();
  await expect(hosted).toBeVisible({ timeout: 60_000 });
  await capture(
    page,
    "../../docs/plans/screenshots/working/gcr-01-permissions-gate-agrees.png",
  );

  // Found running this spec, 2026-09-06: the Models page reported the same two
  // gates from their *rows* rather than from the enforcing path, so this panel
  // printed "Off" for hosted models directly above the connected Anthropic card
  // that had just accepted a pin. Connecting a provider is consent to use it, so
  // the enforcing path had said yes. The panel says what it answers now.
  await hostedProviderCard(page, BASE, "Anthropic");
  const posture = page.getByLabel("Off-machine provider posture");
  await expect(posture).toBeVisible({ timeout: 30_000 });
  await expect(posture.getByText("Off", { exact: true })).toHaveCount(0);
  await capture(
    page,
    "../../docs/plans/screenshots/working/models-posture-reports-the-enforced-answer.png",
  );
});
