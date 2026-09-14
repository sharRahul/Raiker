/**
 * The four findings of §18.5 of the 2026-09-13 removal and simplification
 * review, against a running host.
 *
 * All four are the same kind of defect wearing four costumes: a surface saying
 * something more confident than what it actually knows.
 *
 * * **NEW-HOME-01** — a diagnostics failure became zero runtime issues, and
 *   Home went on to say nothing needed the owner.
 * * **NEW-MAP-01** — a failed refresh left the graph on screen labelled
 *   "Live workspace graph"; worse, it replaced the map with an error page.
 * * **NEW-MAP-03** — the review's 5,000-entry cap counted only accepted files,
 *   so skipped and excluded entries were free and the walk was unbounded.
 * * **NEW-PROJ-02** — a project's image strip could not open the image in it.
 */
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";

const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";
const SHOTS = "../../docs/screenshots/2026-09-13-removal-review";

/** Read one governed endpoint as the signed-in owner. */
async function apiGet(page: Page, path: string): Promise<unknown> {
  return page.evaluate(async (target) => {
    const response = await fetch(target);
    return response.json();
  }, path);
}

test("Home does not call an unread readiness check an all-clear (NEW-HOME-01)", async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);

  // With the real endpoint answering, the rail reports readiness as a number:
  // either a count of issues, or the all-clear when there are none. Which of
  // the two depends on the workspace, and both are claims Raiker is entitled
  // to make because it read the answer.
  await page.goto(`${BASE}/#/home`);
  const rail = page.getByRole("complementary", { name: "Needs your attention" });
  await expect(rail).toBeVisible({ timeout: 30_000 });
  await expect(
    rail.getByText("Runtime issues").or(rail.getByText(/nothing needs you right now/i)).first(),
  ).toBeVisible({ timeout: 60_000 });
  await capture(page, `${SHOTS}/home-readiness-read.png`);

  // Now readiness stops answering, while the board stays open — which is the
  // shape the defect actually took, since Home re-reads every fifteen seconds.
  //
  // Deliberately not a reload: `/api/diagnostics` is also what the boot probe
  // calls to decide whether the runtime is reachable, so refusing it across a
  // reload locks the workspace and proves nothing about the rail. Found by
  // trying it.
  await page.route("**/api/diagnostics**", (route) =>
    route.fulfill({ status: 503, body: "{}" }),
  );

  // The next poll picks it up. What was read stays readable, and stops being
  // asserted: the tile carries when it was last true and that renewing it
  // failed, instead of a count nobody checked.
  await expect(rail.getByText("Runtime health", { exact: true })).toBeVisible({
    timeout: 90_000,
  });
  await expect(rail.getByText(/refresh failed \(HTTP 503\)/i)).toBeVisible();
  await expect(rail.getByText(/this is not an all-clear/i)).toBeVisible();
  await expect(rail.getByText(/nothing needs you right now/i)).toHaveCount(0);
  // Never a number, because there is no current number to give.
  await expect(rail.getByText("Runtime issues")).toHaveCount(0);
  await capture(page, `${SHOTS}/home-readiness-unavailable.png`);
});

test("a stale Knowledge Map stays on screen and stops calling itself live (NEW-MAP-01)", async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/brain`);

  await expect(page.getByText("Live workspace graph")).toBeVisible({ timeout: 60_000 });

  // Every later read fails. The graph already drawn is the only one anybody
  // has, so it stays — and says how old it is.
  await page.route("**/api/brain", (route) => route.fulfill({ status: 500, body: "{}" }));
  await page.getByRole("button", { name: "Refresh" }).click();

  await expect(page.getByText("Live workspace graph")).toHaveCount(0, { timeout: 60_000 });
  await expect(page.getByText(/last updated/i)).toContainText(/refresh failed/i);
  // The map is still there. Before, a failed refresh replaced the whole page
  // with "Couldn't load the knowledge graph" — about a graph that had loaded.
  await expect(page.getByRole("application", { name: /knowledge graph/i })).toBeVisible();
  await capture(page, `${SHOTS}/knowledge-map-stale.png`);
});

test("a source review bounds what it walks and says when it stopped (NEW-MAP-03)", async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/brain`);
  await expect(page.getByRole("button", { name: "Add workspace source" })).toBeVisible({
    timeout: 60_000,
  });

  // Raiker's own generated-files root is always present and always reviewable,
  // which makes it the one source this assertion can rely on existing.
  const review = (await page.evaluate(async () => {
    const csrf = document.cookie.match(/(?:^|;\s*)raiker_csrf=([^;]*)/)?.[1];
    const response = await fetch("/api/brain/sources/review", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(csrf ? { "X-Raiker-CSRF": decodeURIComponent(csrf) } : {}),
      },
      body: JSON.stringify({ path: "generated-files" }),
    });
    return response.json();
  })) as Record<string, unknown>;

  // The fields the finding is about: what the walk cost, and whether it was
  // complete. Neither existed — the old answer could not say either.
  expect(review).toHaveProperty("visited_entries");
  expect(review).toHaveProperty("truncated");
  expect(typeof review.visited_entries).toBe("number");
  expect(review.truncated).toBe(false);
  expect(review.review_cap).toBe(5000);
});

test("a project's image opens in Design, not the whole history (NEW-PROJ-02)", async ({
  page,
}) => {
  test.setTimeout(240_000);
  await signInAsOwner(page, BASE);

  const images = (await apiGet(page, "/api/images")) as {
    generations?: Array<{ generation_id: string; project_id?: string | null; status: string }>;
  };
  const filed = (images.generations ?? []).find(
    (generation) => generation.status === "ok" && generation.project_id,
  );
  test.skip(
    filed === undefined,
    "this workspace holds no image filed to a project; generating one needs an image provider",
  );

  await page.goto(
    `${BASE}/#/design?project=${encodeURIComponent(String(filed!.project_id))}&asset=${encodeURIComponent(filed!.generation_id)}`,
  );
  // The canvas says what it is scoped to, and offers the way out.
  await expect(page.getByText(/Showing images from/)).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole("link", { name: "Show all images" })).toBeVisible();
  // An asset is selected, so the composer edits rather than generates.
  await expect(page.getByText(/Enter edits/)).toBeVisible({ timeout: 30_000 });
  await capture(page, `${SHOTS}/design-opened-from-project.png`);
});
