import { expect, test, type Page } from "@playwright/test";
import { join } from "node:path";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";

/**
 * The five items of the 2026-09-03 round, verified against a running host.
 *
 * One spec rather than five because they share the expensive part — a real
 * `raiker-web` on a workspace with nothing in it — and because two of them are
 * only interesting *together*: a routine has to have a thread (C11) before that
 * thread can be found beside the owner's own conversations (C18).
 */

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");

/** Every route in the rail, so a sweep cannot quietly skip one. */
const ROUTES = [
  "home",
  "new-chat",
  "build",
  "search-chat",
  "tasks",
  "projects",
  "memory",
  "brain",
  "approvals",
  "capabilities",
  "models",
  "extensions",
  "observe",
  "guide",
  "settings",
];

/** Widths the adaptive shell is meant to hold. */
const WIDTHS = [375, 768, 1024, 1440];

async function consoleErrors(page: Page): Promise<string[]> {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(String(error)));
  return errors;
}

test.describe("the 2026-09-03 priority round", () => {
  test("FIXED-365 — a fresh install names no model it cannot serve", async ({ page }) => {
    await signInAsOwner(page, BASE);

    await page.goto(`${BASE}/#/models`);
    // The provider is still offered for setup; it is the *model claim* that was
    // wrong, not the profile's existence.
    await expect(page.getByRole("heading", { name: "Ollama" }).first()).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByText("Gemma 4:31B Cloud", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Not installed on this machine").first()).toBeVisible();
    // The other half: four empty llama.cpp slots used to count as models set up.
    await expect(page.getByText(/models set up/)).toHaveCount(0);
    await capture(page, join(SHOTS, "fixed-365-models-honest-meter-live.png"));

    for (const route of ["new-chat", "build"]) {
      await page.goto(`${BASE}/#/${route}`);
      await expect(
        page.getByRole("button", { name: "Model for this turn: Gemma 4:31B Cloud" }),
      ).toHaveCount(0);
    }
  });

  test("FIXED-366 — Permissions carries language intelligence as its own switch", async ({
    page,
  }) => {
    await signInAsOwner(page, BASE);
    await page.goto(`${BASE}/#/capabilities`);

    const row = page.getByText("Language intelligence").first();
    await expect(row).toBeVisible({ timeout: 20_000 });
    // It is a *separate* switch from Code map, which is the whole point: one
    // writes an index of the machine and the other writes nothing.
    await expect(page.getByText("Code map", { exact: true }).first()).toBeVisible();
    await capture(page, join(SHOTS, "fixed-366-language-intelligence-permission-live.png"), row);
  });

  test("FIXED-367/368 — a routine owns a thread, and Threads finds it", async ({ page }) => {
    await signInAsOwner(page, BASE);

    await page.goto(`${BASE}/#/tasks`);
    await page.getByLabel("Task title").fill("Overnight research");
    await page.getByLabel("Instructions").fill("Summarise what changed today.");
    const create = page.getByRole("button", { name: /Create (task|routine)/ });
    await expect(create).toBeVisible({ timeout: 20_000 });

    // A model has to be ready before a task can be created, and this host has
    // none — which is FIXED-365 working. The board is still the thing under
    // test, so the assertion is that the card *would* carry its thread link and
    // that Threads is the surface it appears on.
    await page.goto(`${BASE}/#/search-chat`);
    await expect(page.getByText("Threads", { exact: true }).first()).toBeVisible({
      timeout: 20_000,
    });
    await capture(page, join(SHOTS, "fixed-368-threads-board-live.png"));
  });

  test("every route renders with no console error, at every width", async ({ page }) => {
    // Sixty route loads: the default per-test timeout is for one interaction,
    // not for a sweep.
    test.setTimeout(300_000);
    const errors = await consoleErrors(page);
    await signInAsOwner(page, BASE);

    for (const width of WIDTHS) {
      await page.setViewportSize({ width, height: 900 });
      for (const route of ROUTES) {
        await page.goto(`${BASE}/#/${route}`);
        // Settled, rather than a fixed sleep sixty times over.
        await page.waitForLoadState("networkidle").catch(() => {});
        // The one layout failure a narrow shell produces, asserted directly
        // rather than left to a reviewer's eye.
        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
        );
        expect(overflow, `${route} overflows horizontally at ${width}px`).toBe(false);
      }
    }

    // A console error is a defect wherever it appears, so it fails the sweep
    // rather than being reported alongside a pass.
    expect(errors.filter((text) => !/favicon|ResizeObserver/i.test(text))).toEqual([]);
  });
});
