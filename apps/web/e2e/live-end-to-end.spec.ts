/**
 * End-to-end verification against a live model.
 *
 * This is not a mocked shell: the runtime holds a real provider credential, the
 * turn below reaches Anthropic, and every screenshot records the shipped product
 * answering its own endpoints with a real answer in it.
 *
 * Prerequisites (see docs/plans/TO_BE_FIXED.md for the run recorded from this):
 *   1. `python apps/api/main.py --workspace <ws> --port 8765 --no-browser`
 *      with RAIKER_MODEL_EGRESS_ALLOWLIST=api.anthropic.com
 *   2. the `hosted_model_runtime` capability enabled and a provider key stored
 *   3. a concrete model selected
 */
import { expect, test, type Browser, type Page } from "@playwright/test";
import { capture } from "./capture";
import { join } from "node:path";
import { signInAsOwner } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");

// A 1×1 PNG, built here rather than read from disk so the spec carries its own
// fixture and cannot fail on a missing file.
const PNG_BASE64 =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==";

/**
 * BUG-229 — sign in through the one shared helper.
 *
 * Every spec used to carry its own copy, and each copy encoded an assumption
 * about the *state* of the instance — usually the empty-workspace greeting —
 * that had nothing to do with what the spec asserts. A suite then passed on a
 * fresh instance and failed at its first step on a used one.
 */
async function signIn(page: Page) {
  await signInAsOwner(page, BASE);
}

test.describe.configure({ mode: "serial" });

let page: Page;

test.beforeAll(async ({ browser }: { browser: Browser }) => {
  page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, colorScheme: "light" });
  await signIn(page);
});

test.afterAll(async () => {
  await page?.close();
});

test("a real governed turn answers, and the copy action is a glyph", async () => {
  test.setTimeout(180_000);
  await page.goto(`${BASE}/#/new-chat`);
  const prompt = page.getByPlaceholder("How can I help you today?");
  await expect(prompt).toBeVisible({ timeout: 20_000 });

  await prompt.fill(
    "Reply with exactly one short sentence about governed agents, then a fenced " +
      "python code block containing: print('raiker')",
  );
  await page.getByRole("button", { name: "Send", exact: true }).click();

  // The model's own answer, not a fixture.
  await expect(page.getByRole("button", { name: "Copy response" })).toBeVisible({
    timeout: 120_000,
  });
  // BUG-23 / composer polish: both copy affordances are glyphs now.
  await expect(page.getByRole("button", { name: "Copy code" })).toBeVisible();
  await capture(page, join(SHOTS, "166-chat-live-turn.png"));
});

test("an attached image opens with working zoom, rotate and reset controls", async () => {
  test.setTimeout(180_000);

  // Attach through the shared control, exactly as a person would.
  await page.getByRole("button", { name: "Add attachment" }).click();
  await page.getByLabel("Upload image").setInputFiles({
    name: "pixel.png",
    mimeType: "image/png",
    buffer: Buffer.from(PNG_BASE64, "base64"),
  });
  await expect(page.getByTitle(/pixel\.png/)).toBeVisible({ timeout: 20_000 });

  await page.getByPlaceholder("How can I help you today?").fill("Describe this image in one line.");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByRole("button", { name: "Copy response" }).last()).toBeVisible({
    timeout: 120_000,
  });

  // The chip the turn carried opens the inspector.
  await page.getByRole("button", { name: /Open pixel\.png/i }).first().click();
  await expect(page.getByRole("complementary", { name: "File preview" })).toBeVisible({
    timeout: 20_000,
  });

  // BUG-26 — the controls exist, are labelled, and actually move the picture.
  await expect(page.getByText("100%")).toBeVisible();
  await page.getByRole("button", { name: /zoom in/i }).click();
  await expect(page.getByText("125%")).toBeVisible();
  await page.getByRole("button", { name: /rotate right/i }).click();
  const image = page.getByRole("img", { name: "pixel.png" });
  await expect(image).toHaveAttribute("style", /rotate\(90deg\)/);
  await capture(page, join(SHOTS, "167-image-inspection-live.png"));

  await page.getByRole("button", { name: /reset the view/i }).click();
  await expect(page.getByText("100%")).toBeVisible();
  await expect(image).toHaveAttribute("style", /scale\(1\) rotate\(0deg\)/);

  // BUG-28 — Download is offered on the pane, distinct from Preview.
  await expect(page.getByRole("button", { name: /Download pixel\.png/i })).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: /Download pixel\.png/i }).click();
  expect((await download).suggestedFilename()).toBe("pixel.png");
  await capture(page, join(SHOTS, "168-artifact-download-live.png"));
});
