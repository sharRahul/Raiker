import { execFileSync } from "node:child_process";
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { join } from "node:path";
import { signInAsOwner } from "./hosted-provider";

/**
 * The containment surface, against a workspace that really has a contained
 * subject (FIXED-163, FIXED-164).
 *
 * A live browser cannot make a healthy provider fail three times on demand, so
 * the failures are recorded first through the same `CapabilityBreaker` the
 * runtime uses, against the same workspace the server is serving.
 *
 * **BUG-250 — that seeding used to be a comment.** The steps were written here
 * as a shell block for a person to run by hand, and a round that did not run
 * them met a red assertion about a list that was empty *because the product was
 * behaving correctly*. The spec now performs its own precondition when
 * `RAIKER_LIVE_WORKSPACE` names the workspace the host is serving, and skips
 * with the reason when it does not — the same rule the rest of the suite follows:
 * a spec states what it needs rather than discovering it by failing.
 *
 * What this spec proves is the half a unit test cannot: that the state reaches
 * the owner, names its reason and its failure count, and clears in one press.
 */

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "output", "playwright");
const REPO = join(import.meta.dirname, "..", "..", "..");
const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? "";

/**
 * Record three consecutive connector failures, through the runtime's own
 * breaker rather than through a hand-written row.
 *
 * Idempotent by construction: the breaker's own threshold is what contains the
 * subject, so running this against an already-contained workspace records three
 * more failures and leaves it contained, which is the same state.
 */
function seedContainedConnector(): void {
  execFileSync(
    "python",
    [
      "-c",
      [
        "import sys",
        "from raiker.security.containment import CAPABILITY_CONNECTOR, CapabilityBreaker",
        "from raiker.storage.sqlite import SQLiteStore",
        "store = SQLiteStore(sys.argv[1])",
        "owner = store.original_account_principal_id()",
        "breaker = CapabilityBreaker(store)",
        "[breaker.record(owner, CAPABILITY_CONNECTOR, 'github', ok=False,",
        "                label='GitHub', reason_code='http_500') for _ in range(3)]",
      ].join("\n"),
      WORKSPACE,
    ],
    { cwd: REPO, stdio: "pipe" },
  );
}

test("a contained subject is visible, explained, and revocable", async ({ page }) => {
  test.setTimeout(180_000);
  test.skip(
    WORKSPACE === "",
    "This spec needs a contained subject to look at. Set RAIKER_LIVE_WORKSPACE to the " +
      "workspace the host is serving so it can record the three failures itself.",
  );
  seedContainedConnector();

  // BUG-248 — the shared sign-in. This copy only ever unlocked, so it could not
  // run against a workspace that had no owner yet.
  await signInAsOwner(page, BASE);

  await page.goto(`${BASE}/#/settings?tab=security`);
  const containment = page.getByTestId("capability-containment");
  const subject = containment.locator("li").filter({ hasText: "GitHub" });
  await expect(subject).toBeVisible({ timeout: 30_000 });
  await expect(subject).toContainText("Connector · paused");
  await expect(subject).toContainText("Contained after 3 consecutive failures");
  await expect(subject).toContainText("3 consecutive failures (http_500)");
  await containment.scrollIntoViewIfNeeded();
  await capture(page, join(SHOTS, "round0810-10-contained-subject.png"));

  // One press, and it is the owner's again.
  await subject.getByRole("button", { name: "Resume" }).click();
  await expect(subject).toContainText("Connector · active", { timeout: 30_000 });
  await expect(subject.getByRole("button", { name: "Pause" })).toBeVisible();
  await containment.scrollIntoViewIfNeeded();
  await capture(page, join(SHOTS, "round0810-11-containment-resumed.png"));
});
