/*
 * VIS2-19 — Design as a canvas workspace, driven against a real runtime.
 *
 * The review's composition is Assets │ Canvas │ Inspector, with the canvas
 * dominating whenever an asset exists. Every part of that needs a relationship
 * between pictures, which BUG-277 built: a generation records what it was made
 * from and which of the three requests made it.
 *
 * What this asserts is that the page derives the composition from those fields
 * rather than from the order rows happen to arrive in — a list sorted by time
 * drawn as a history is the defect the whole feature exists to avoid.
 *
 * The assets it runs against are seeded into the workspace's own store, because
 * this host's egress policy blocks the image providers. Everything the page
 * reads is nonetheless real: real attachments, real rows, read back through
 * `GET /api/images`.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";

const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8768";
const SHOTS = "../../docs/screenshots/2026-09-12-design-canvas";

test.describe.configure({ mode: "serial" });

test.beforeEach(async ({ page }) => {
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/design`);
  const seeded = await page.evaluate(async () => {
    const response = await fetch("/api/images", { credentials: "same-origin" });
    const body = (await response.json()) as { generations?: { generation_id: string }[] };
    return (body.generations ?? []).length;
  });
  test.skip(seeded === 0, "This workspace holds no generations to compose a canvas from.");
});

test("with nothing selected, the history is the page", async ({ page }) => {
  test.setTimeout(180_000);
  // A canvas with no object on it is not a canvas, and an empty three-pane
  // frame would be chrome pretending to be a workspace.
  await expect(page.getByRole("region", { name: "Canvas" })).toHaveCount(0);
  await expect(page.getByRole("complementary", { name: "Assets" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Open .* on the canvas/ }).first()).toBeVisible({
    timeout: 60_000,
  });
  await capture(page, `${SHOTS}/design-01-history.png`);
});

test("selecting an asset composes the three regions around it", async ({ page }) => {
  test.setTimeout(180_000);
  await page.getByRole("button", { name: /Open .* on the canvas/ }).first().click();

  const canvas = page.getByRole("region", { name: "Canvas" });
  await expect(canvas).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("complementary", { name: "Assets" })).toBeVisible();
  await expect(page.getByRole("complementary", { name: "Inspector" })).toBeVisible();

  // VIS2-19's one stated composition rule: the canvas dominates.
  const canvasBox = await canvas.boundingBox();
  const railBox = await page.getByRole("complementary", { name: "Assets" }).boundingBox();
  const inspectorBox = await page.getByRole("complementary", { name: "Inspector" }).boundingBox();
  expect(canvasBox!.width).toBeGreaterThan(railBox!.width);
  expect(canvasBox!.width).toBeGreaterThan(inspectorBox!.width);

  await capture(page, `${SHOTS}/design-02-canvas.png`);
});

test("an edited asset shows the chain it came from, not everything before it", async ({
  page,
}) => {
  test.setTimeout(180_000);
  // The newest asset in the seeded workspace is the twice-edited leaf.
  await page.getByRole("button", { name: /add a thin gold outline/i }).first().click();

  const versions = page.getByRole("region", { name: "Versions" });
  await expect(versions).toBeVisible({ timeout: 30_000 });
  // Three versions: the origin, the recolour, the outline — in that order.
  await expect(versions.getByRole("button", { name: /^Version \d/ })).toHaveCount(3);

  const inspector = page.getByRole("complementary", { name: "Inspector" });
  await expect(inspector.getByText("Edited from")).toBeVisible();
  await capture(page, `${SHOTS}/design-03-versions.png`, inspector);
});

test("the primary action says Edit once there is something to edit", async ({ page }) => {
  test.setTimeout(180_000);
  // COMPOSER-15 — the word names the act the press performs, and it follows the
  // state rather than the other way round.
  await expect(page.getByRole("button", { name: "Generate", exact: true })).toBeVisible({
    timeout: 60_000,
  });
  await expect(page.getByText(/Enter generates/)).toBeVisible();

  await page.getByRole("button", { name: /Open .* on the canvas/ }).first().click();

  await expect(page.getByRole("button", { name: "Edit", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Generate", exact: true })).toHaveCount(0);
  // The hint one line below the button names the same act. "Enter generates"
  // beside a button reading Edit is the mismatch this item is about, moved.
  await expect(page.getByText(/Enter edits/)).toBeVisible();
  // An edit produces one new version of the selected image, so the count is not
  // a choice while one is selected.
  await expect(page.getByLabel("How many")).toBeDisabled();

  await capture(page, `${SHOTS}/design-04-edit-action.png`);
});

test("a refused edit is shown against the picture it was about", async ({ page }) => {
  test.setTimeout(180_000);
  // Why the executor records lineage on refusals as well as successes.
  await page.getByRole("button", { name: /a single maple leaf/i }).first().click();

  const refused = page.getByRole("region", { name: "Refused attempts" });
  await expect(refused).toBeVisible({ timeout: 30_000 });
  // Scoped to the list item: the panel's own heading also reads "Refused", and
  // matching both is matching the frame rather than the content.
  await expect(refused.getByRole("listitem").first()).toContainText(/refused/i);
});
