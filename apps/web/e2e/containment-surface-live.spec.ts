import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { join } from "node:path";
import { OWNER_CREDENTIALS } from "./hosted-provider";

/**
 * The containment surface, against a workspace that really has a contained
 * subject (FIXED-163, FIXED-164).
 *
 * A live browser cannot make a healthy provider fail three times on demand, so
 * the failures are recorded first through the same `CapabilityBreaker` the
 * runtime uses, against the same workspace the server is serving:
 *
 * ```
 * python - <<'PY'
 * from raiker.security.containment import CAPABILITY_CONNECTOR, CapabilityBreaker
 * from raiker.storage.sqlite import SQLiteStore
 * store = SQLiteStore("<workspace>")
 * breaker = CapabilityBreaker(store)
 * for _ in range(3):
 *     breaker.record("<owner>", CAPABILITY_CONNECTOR, "github",
 *                    ok=False, label="GitHub", reason_code="http_500")
 * PY
 * ```
 *
 * What this spec proves is the half a unit test cannot: that the state reaches
 * the owner, names its reason and its failure count, and clears in one press.
 */

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "output", "playwright");
const PASSWORD = OWNER_CREDENTIALS.password;

test("a contained subject is visible, explained, and revocable", async ({ page }) => {
  test.setTimeout(180_000);

  await page.goto(`${BASE}/#/home`);
  await expect(page.getByText(/Verifying runtime/)).toBeHidden({ timeout: 30_000 });
  await page.getByLabel("Username").fill(OWNER_CREDENTIALS.user);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Unlock Raiker" }).click();
  await expect(page.getByRole("navigation", { name: /navigation/i })).toBeVisible({
    timeout: 30_000,
  });

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
