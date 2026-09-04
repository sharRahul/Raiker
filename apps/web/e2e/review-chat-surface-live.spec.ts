import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { join } from "node:path";
import { signInAsOwner } from "./hosted-provider";

/**
 * What one ordinary turn actually puts on screen.
 *
 * Evidence for the chat-surface review: the transcript is captured mid-stream
 * and again once the turn has settled, and every element the turn added is
 * listed rather than judged, so the write-up quotes the product instead of a
 * recollection of it.
 */

const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "output", "playwright");

test("a single turn's transcript, mid-stream and settled", async ({ page }) => {
  test.setTimeout(600_000);

  // BUG-248 — the shared sign-in. The copy this replaced clicked "Skip for now",
  // a control that no longer exists anywhere in the app, and then assumed the
  // wizard's remaining stages arrived in a fixed order.
  await signInAsOwner(page, BASE);

  await page.goto(`${BASE}/#/new-chat`);
  const composer = page.locator("textarea#prompt-input");
  await expect(composer).toBeVisible({ timeout: 60_000 });
  await composer.fill(
    "Thanks! In three short paragraphs, explain what a governed agent runtime is.",
  );

  // Readiness resolves after the composer mounts, so Send is briefly disabled on
  // a page that is perfectly ready. Wait for the gate rather than sampling it.
  const send = page.getByRole("button", { name: "Send", exact: true }).first();
  try {
    await expect(send).toBeEnabled({ timeout: 60_000 });
  } catch {
    console.log("SEND DISABLED — readiness expired; re-run the readiness probe first");
    return;
  }
  await send.click();

  // Mid-stream: whatever the turn shows while it is still answering.
  await page.waitForTimeout(1200);
  const streamingText = await page.locator(".message-group-raiker").last().innerText();
  console.log("MID-STREAM:\n" + streamingText.replace(/\n{2,}/g, "\n"));
  await capture(page, join(SHOTS, "review-chat-midstream.png"));

  const answer = page.locator(".message-bubble-raiker").last();
  await expect(answer).toBeVisible({ timeout: 300_000 });
  await page.waitForTimeout(4000);

  const settled = await page.locator(".turn").last().innerText();
  console.log("SETTLED TURN:\n" + settled.replace(/\n{2,}/g, "\n"));

  // Everything the turn put on screen, by class, so the review counts rather
  // than estimates.
  const parts = await page.locator(".turn").last().evaluate((node) => {
    const seen: string[] = [];
    node.querySelectorAll("*").forEach((el) => {
      const cls = (el.getAttribute("class") ?? "").trim();
      if (cls) seen.push(cls.split(/\s+/)[0]);
    });
    return [...new Set(seen)];
  });
  console.log("ELEMENT CLASSES IN ONE TURN: " + parts.join(", "));
  await capture(page, join(SHOTS, "review-chat-settled.png"));
});
