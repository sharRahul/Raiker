import { expect, test } from "@playwright/test";
import { join } from "node:path";
import { signInAsOwner } from "./hosted-provider";
import { capture } from "./capture";

/**
 * BUG-301 — a reference from one guide chapter to another is a link that opens
 * that chapter in place.
 *
 * The defect was visible on the page and nowhere else: `working-in-build.md`
 * points at the *Connecting a model* chapter as an ordinary relative Markdown
 * link, and the renderer — correctly, because the same renderer draws
 * model-authored answers — downgraded it to plain text. Every chapter-to-chapter
 * reference read as broken punctuation.
 *
 * Live rather than mocked because what is being checked is that the resolved
 * address is one this app's router really serves: a unit test can assert the
 * href, and only a real navigation proves the chapter opens.
 */
const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-09-18-round");

test("a guide chapter's cross-reference opens the chapter it names", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/guide?section=working-in-build`);

  const article = page.getByRole("article").or(page.locator(".guide-page")).first();
  await expect(article.getByRole("heading", { name: /Working in Build/i })).toBeVisible({
    timeout: 30_000,
  });

  // The defect, stated as the thing that must not be on the page: the source
  // form of the reference.
  await expect(page.getByText("(connecting-a-model.md)")).toHaveCount(0);

  const reference = article
    .getByRole("link", { name: /Connecting a model/i })
    .first();
  await expect(reference).toBeVisible();
  await expect(reference).toHaveAttribute("href", "#/guide?section=connecting-a-model");
  // An in-app link must not open a second tab — the guide opening itself
  // alongside itself is a different defect.
  await expect(reference).not.toHaveAttribute("target", "_blank");

  await capture(page, join(SHOTS, "guide-cross-reference.png"));
  await reference.click();

  await expect(article.getByRole("heading", { name: /Connecting a model/i })).toBeVisible({
    timeout: 30_000,
  });
  expect(page.url()).toContain("section=connecting-a-model");
  await capture(page, join(SHOTS, "guide-chapter-opened.png"));

  expect(consoleErrors).toEqual([]);
});
