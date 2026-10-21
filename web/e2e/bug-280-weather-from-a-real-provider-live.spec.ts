/**
 * BUG-280, the weather half: a real model asks a real Open-Meteo.
 *
 * The clock half closed as FIXED-539. The weather half stayed open for one
 * reason — every host the rounds ran on refused `api.open-meteo.com` at its
 * egress proxy — so the tool's `weather_provider_unavailable` was the correct
 * answer to an unreachable provider and no evidence that a reachable one is read
 * correctly. This round runs on a host that reaches Open-Meteo, with a
 * tool-using model served by the local Ollama (no API key), and checks the
 * interface outcome the entry names: the answer names the provider and how old
 * the reading is, and today's date is the runtime's.
 *
 * Prerequisites: run `bug-340-ollama-cloud-location-live.spec.ts` first on a
 * reset workspace — it creates the owner and selects the Ollama cloud model
 * (default `gpt-oss:20b-cloud`) this turn runs on — and outbound HTTPS to
 * open-meteo.com.
 */
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-10-17-bug-280-weather");
const MODEL_TURN = new RegExp(`Model for this turn: ${process.env.RAIKER_LIVE_OLLAMA_CLOUD_LABEL ?? "GPT oss:20B Cloud"}`, "i");

interface Bundle {
  local_date: string;
  day_of_week: string;
  location: string | null;
}

async function bundle(page: Page): Promise<Bundle> {
  return page.evaluate(async () => {
    const response = await fetch("/api/environment", { credentials: "same-origin" });
    if (!response.ok) throw new Error(`environment ${response.status}`);
    return (await response.json()) as Bundle;
  });
}

/** Save a settings tab when it has something to save; a re-run changes nothing. */
async function saveIfChanged(page: Page): Promise<void> {
  // The save bar exists only while something is unsaved; `isEnabled` on a
  // missing button would wait for it forever.
  await page.waitForTimeout(300);
  const save = page.getByRole("button", { name: /^Save/ });
  if ((await save.count()) > 0 && (await save.first().isEnabled())) {
    await save.first().click();
    await expect(page.getByText(/Saved/i).first()).toBeVisible({ timeout: 30_000 });
  }
}

test("a real turn reads today's weather from Open-Meteo and says how old it is", async ({ page }) => {
  test.setTimeout(420_000);
  await signInAsOwner(page, BASE);

  // The owner's zone and default place, the way an owner sets them.
  await page.goto(`${BASE}/#/settings?tab=general`);
  const zone = page.getByLabel("Time zone");
  await expect(zone).toBeVisible({ timeout: 30_000 });
  await zone.selectOption("Europe/London");
  await saveIfChanged(page);
  await page.getByRole("navigation", { name: "Settings sections" }).getByRole("button", { name: "Personalisation" }).click();
  const place = page.getByLabel("Default weather location");
  await expect(place).toBeVisible({ timeout: 30_000 });
  await place.fill("Edinburgh, United Kingdom");
  await place.press("Tab");
  await saveIfChanged(page);
  const clock = await bundle(page);
  expect(clock.location).toBe("Edinburgh, United Kingdom");

  // The cloud model the BUG-340 first-run round chose is the one that answers.
  await page.goto(`${BASE}/#/new-chat`);
  await expect(page.getByRole("button", { name: MODEL_TURN }).first()).toBeVisible({ timeout: 60_000 });
  const prompt = page.getByPlaceholder("What would you like Raiker to do?");
  await prompt.fill(
    "What is today's date (YYYY-MM-DD) and day, and what is the weather here right now? " +
      "Use the weather tool, and say which provider the reading came from and when it was observed.",
  );
  await page.getByRole("button", { name: "Send", exact: true }).click();

  // A governed read may ask first; the owner allows this one read.
  const allow = page.getByRole("button", { name: /^(Approve|Allow once|Allow)$/ }).first();
  const answer = page.locator(".message-bubble-raiker").last();
  await expect
    .poll(
      async () => {
        if (await allow.isVisible().catch(() => false)) await allow.click();
        return ((await answer.textContent().catch(() => "")) ?? "").trim().length;
      },
      { timeout: 300_000, intervals: [2_000] },
    )
    .toBeGreaterThan(20);
  let settled = "";
  await expect
    .poll(
      async () => {
        const now = ((await answer.textContent()) ?? "").trim();
        const same = now === settled;
        settled = now;
        return same;
      },
      { timeout: 120_000, intervals: [2_000] },
    )
    .toBe(true);
  await capture(page, join(SHOTS, "01-weather-answer.png"));

  // Models print dates and names with typographic hyphens (U+2010–2015).
  const plain = settled.replace(/[‐-―]/g, "-");
  expect(plain).toContain(clock.local_date);
  expect(plain).toMatch(/Open-?Meteo/i);
  expect(settled).toMatch(/°|degrees/i);
  // Not the typed refusal an unreachable provider produces.
  expect(settled).not.toMatch(/weather_provider_unavailable|could not finish/i);

  // The runtime recorded a real call to the weather capability.
  await page.locator("summary", { hasText: "Evidence" }).last().click();
  await capture(page, join(SHOTS, "02-turn-evidence.png"));
});
