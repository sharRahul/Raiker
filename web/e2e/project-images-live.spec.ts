/*
 * BUG-282 — a picture generated in a project belongs to that project.
 *
 * Two halves, and this asserts both against a running server. The first is the
 * request: Design's composer has to *carry* the project it names, or nothing
 * downstream can file anything. The second is the material: the project's own
 * page has to show the pictures made in it, which is the interface outcome the
 * entry set before it could close.
 *
 * The pictures for the second half are written into the workspace's own store
 * out of band, because this host's egress policy blocks the image providers and
 * a picture cannot be generated here. Everything the page reads is nonetheless
 * real — a project created through the product's own control, real attachments,
 * real rows, read back through `GET /api/images`.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";

const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8768";
const SHOTS = "../../docs/screenshots/2026-09-13-project-images";
const PROJECT = "Leaf studio";

test.describe.configure({ mode: "serial" });

/** The project this round works in, created once through the Projects page. */
let projectId = "";

test.beforeEach(async ({ page }) => {
  await signInAsOwner(page, BASE);
});

test("a project is created through the product's own control", async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto(`${BASE}/#/projects`);

  const existing = page.getByRole("button", { name: `Open project ${PROJECT}` });
  if ((await existing.count()) === 0) {
    await page.getByLabel(/project name/i).fill(PROJECT);
    await page.getByRole("button", { name: /^create( project)?$/i }).click();
  }
  await expect(existing.first()).toBeVisible({ timeout: 30_000 });

  projectId = await page.evaluate(async (name) => {
    const response = await fetch("/api/projects", { credentials: "same-origin" });
    const body = (await response.json()) as { projects?: { project_id: string; name: string }[] };
    return (body.projects ?? []).find((entry) => entry.name === name)?.project_id ?? "";
  }, PROJECT);
  expect(projectId).not.toBe("");
});

test("Design's request carries the project the composer names", async ({ page }) => {
  test.setTimeout(180_000);
  // The live half. Whether the provider answers is a separate question — and on
  // this host it cannot — but what leaves the browser is the thing being
  // asserted, because a request that does not name the project can file nothing
  // however well the store handles it.
  await page.goto(`${BASE}/#/design`);

  await page.getByRole("button", { name: "Add to this turn" }).first().click();
  await page.getByRole("menuitem", { name: "Work in a project" }).click();
  await page.getByLabel("Project for this work").selectOption(projectId);

  const composer = page.getByRole("textbox").first();
  await composer.fill("a single maple leaf, flat vector style");

  const request = page.waitForRequest(
    (candidate) => candidate.url().endsWith("/api/images") && candidate.method() === "POST",
  );
  await page.getByRole("button", { name: "Generate", exact: true }).click();
  const body = JSON.parse((await request).postData() ?? "{}") as { project_id?: string };

  expect(body.project_id).toBe(projectId);
});

test("the project's page shows the pictures made in it", async ({ page }) => {
  test.setTimeout(180_000);
  // Skipped rather than failed on a workspace whose provider is reachable and
  // whose project is therefore empty until somebody generates in it: this
  // asserts how a filed picture is shown, not that one exists.
  const filed = await page.evaluate(async (id) => {
    const response = await fetch("/api/images", { credentials: "same-origin" });
    const body = (await response.json()) as {
      generations?: { project_id?: string | null; status: string; has_image: boolean }[];
    };
    // Pictures, not rows. The turn above filed a refusal against this project —
    // correctly, since a refused request is still something the owner asked of
    // it — and a refusal is not something this section draws.
    return (body.generations ?? []).filter(
      (entry) => entry.project_id === id && entry.status === "ok" && entry.has_image,
    ).length;
  }, projectId);
  test.skip(filed === 0, "No picture is filed against this project to show.");

  await page.goto(`${BASE}/#/projects`);
  await page.getByRole("button", { name: `Open project ${PROJECT}` }).first().click();

  await expect(page.getByRole("heading", { name: "Images" })).toBeVisible({ timeout: 30_000 });
  // Both of the project's pictures, the original and the edit made from it.
  await expect(page.getByRole("img", { name: /maple leaf/i })).toHaveCount(2);
  // Filed somewhere means filed *here*: the unfiled pictures this workspace is
  // full of are the control, and none of them belongs to this project.
  await expect(page.getByRole("img", { name: /the same leaf, four ways/i })).toHaveCount(0);

  await capture(page, `${SHOTS}/project-01-images.png`);
});
