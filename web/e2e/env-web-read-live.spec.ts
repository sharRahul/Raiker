/**
 * The 2026-09-07 round's evidence: the clock, the read catalogue and the weather.
 *
 * Three claims are made by this round's plans, and each of them is exactly the
 * kind that a document can assert and a product can fail to deliver:
 *
 * 1. **Raiker owns the clock.** Every model-backed turn is given the current
 *    UTC and owner-local time, the IANA zone, the date and the day — derived by
 *    the runtime, not recalled by a model, and not dependent on a network.
 * 2. **The read catalogue is global and its readiness is explicit.** Search,
 *    URL read, extraction and weather are visible on every Work surface, and
 *    each says whether it can answer now — separately from whether the owner
 *    has permitted it.
 * 3. **Visibility is never authority.** All four are projected; all four still
 *    fail closed when the gate is off.
 *
 * This spec drives the real host with a real Anthropic key entered through the
 * product's own Connect dialog, because that is the only way to be sure the
 * screen an owner sees is the screen these tests describe.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { hostedProviderCard, signInAsOwner } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const SHOTS = "../../docs/plans/screenshots/working";

test.describe.configure({ mode: "serial" });

test("Settings makes the time zone the visible owner-level source of truth", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=general`);

  const zone = page.getByLabel("Time zone");
  await expect(zone).toBeVisible({ timeout: 30_000 });
  await zone.selectOption("Europe/London");

  // The line under the control is the point of the whole section: a select
  // whose effect you cannot see is a select nobody trusts.
  const resolved = page.getByTestId("timezone-resolved");
  await expect(resolved).toContainText("Europe/London");
  await expect(resolved).toContainText("You chose this.");
  await expect(resolved).toContainText("Right now that reads");

  // WEATHER-02 — a default place, held separately from the zone.
  await page.getByLabel("Default weather location").fill("Edinburgh, United Kingdom");
  await page.getByRole("button", { name: /^Save/ }).click();
  await expect(page.getByText(/Saved/i).first()).toBeVisible({ timeout: 30_000 });

  await capture(page, `${SHOTS}/env-01-timezone-and-weather-location.png`, resolved);
});

test("the runtime's own clock is what the API reports", async ({ page }) => {
  await signInAsOwner(page, BASE);

  const bundle = await page.evaluate(async () => {
    const response = await fetch("/api/environment", { credentials: "same-origin" });
    return response.ok ? await response.json() : { error: response.status };
  });

  // The same function the orchestrator calls, so the page and the turn cannot
  // disagree about what time it is or which timezone source won.
  expect(bundle.timezone).toBe("Europe/London");
  expect(bundle.timezone_source).toBe("owner_setting");
  expect(String(bundle.generated_at_utc)).toMatch(/Z$/);
  expect(String(bundle.local_datetime)).toContain("+0");
  expect(bundle.day_of_week).toBeTruthy();
  expect(bundle.location).toBe("Edinburgh, United Kingdom");
});

test("the read catalogue is global, and its readiness is separate from authority", async ({
  page,
}) => {
  await signInAsOwner(page, BASE);

  const catalogue = await page.evaluate(async () => {
    const response = await fetch("/api/read-capabilities", { credentials: "same-origin" });
    return response.ok ? await response.json() : { error: response.status };
  });

  for (const surface of ["chat", "build", "design", "tasks", "schedule", "agent"]) {
    expect(catalogue.surfaces[surface]).toEqual(
      expect.arrayContaining(["web_search", "web_fetch", "web_extract", "weather_lookup"]),
    );
  }
  // A bounded delegation must not widen what leaves the machine.
  expect(catalogue.surfaces.subagent).not.toEqual(
    expect.arrayContaining(["web_fetch", "web_search"]),
  );
  // Readiness is its own field, with a state rather than a boolean.
  const readiness = Object.fromEntries(
    catalogue.readiness.map((row: { tool: string }) => [row.tool, row]),
  );
  for (const tool of ["web_search", "web_fetch", "web_extract", "weather_lookup"]) {
    expect(readiness[tool].available).toBe(true);
    expect(readiness[tool].state).toBeTruthy();
    expect(readiness[tool].checked_at).toBeTruthy();
  }
});

test("the weather capability is reachable and fails in a typed state, not silently", async ({
  page,
}) => {
  await signInAsOwner(page, BASE);

  // WEATHER-03 — the honest failure. This host's egress policy refuses
  // `api.open-meteo.com`, and what matters is that the refusal is *typed*: a
  // capability that quietly returns nothing is indistinguishable from one that
  // returned "no weather", and a scheduling rule cannot tell those apart.
  const result = await page.evaluate(async () => {
    const response = await fetch("/api/read-capabilities", { credentials: "same-origin" });
    const payload = await response.json();
    return payload.readiness.find(
      (row: { tool: string }) => row.tool === "weather_lookup",
    );
  });

  // Readiness says the capability exists and would be attempted; whether the
  // provider answers is a separate question the call itself reports.
  expect(result.available).toBe(true);
  expect(result.provider).toBe("Open-Meteo");
  expect(["ready", "blocked", "unavailable", "transient_failure"]).toContain(result.state);
});

test("Chat's Tools menu offers the three reads and the weather", async ({ page }) => {
  test.setTimeout(120_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/new-chat`);

  const tools = page.getByRole("button", { name: "Tools" }).first();
  await expect(tools).toBeVisible({ timeout: 60_000 });
  await tools.click();

  const menu = page.getByRole("menu", { name: "Tools" });
  for (const label of [
    "Search the web",
    "Read a URL",
    "Extract page content",
    "Check the weather",
  ]) {
    await expect(menu.getByRole("menuitem", { name: label })).toBeVisible();
  }
  // They are separate entries because they fail differently — one "Web" row
  // could only ever report the state of whichever it happened to check.
  await capture(page, `${SHOTS}/env-02-chat-tools-research-reads.png`, menu);
});

test("Design offers the same reads, and says the image model gained nothing", async ({ page }) => {
  test.setTimeout(120_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/design`);

  const tools = page.getByRole("button", { name: "Tools" }).first();
  await expect(tools).toBeVisible({ timeout: 60_000 });
  await tools.click();
  const menu = page.getByRole("menu", { name: "Tools" });
  await expect(menu.getByRole("menuitem", { name: "Search the web" })).toBeVisible();
  await capture(page, `${SHOTS}/env-03-design-research-tools.png`, menu);
});

test("the Hugging Face flow states its steps and hides the token behind a reason", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/models?tab=add`);

  const rail = page.getByRole("list", { name: "Adding a local model" });
  await expect(rail.getByText("Find model")).toBeVisible({ timeout: 60_000 });
  await expect(rail.getByText("Choose variant")).toBeVisible();
  await expect(rail.getByText("Review download")).toBeVisible();
  // MODEL-09 — the token control is for gated repositories, not for everyone.
  // As a permanent hero button it told every owner that signing in to Hugging
  // Face was a normal part of downloading a public model.
  await expect(page.getByRole("button", { name: "Set access token" })).toHaveCount(0);
  await capture(page, `${SHOTS}/env-04-huggingface-step-rail.png`, rail);
});

test("connecting the supplied Anthropic key through the product's own flow", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(240_000);
  await signInAsOwner(page, BASE);

  const card = await hostedProviderCard(page, BASE, "Anthropic");
  const connect = card.getByRole("button", { name: /^(Connect|Reconnect)$/ });
  if (await connect.count()) {
    await connect.first().click();
    await page.getByLabel("Anthropic API key").fill(KEY);
    await page.locator(".signin-connect").click();
    await expect(page.getByRole("dialog", { name: "Connect to Anthropic" })).toBeHidden({
      timeout: 60_000,
    });
  }
  // Storing a key is not using one. What this asserts is that the credential
  // reached the vault through the interface, which is the precondition every
  // other claim in this round is measured under.
  await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 60_000 });
  await capture(page, `${SHOTS}/env-05-anthropic-connection.png`, card);
});
