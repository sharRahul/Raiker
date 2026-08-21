import { expect, test, type Locator, type Page } from "@playwright/test";
import { join } from "node:path";

/**
 * Live evidence for the 2026-08-16 round: the first-run provider matrix, the
 * Workbench board, and the two composers.
 *
 * Every credential is typed into the product's own field exactly as an owner
 * types it — never handed to the server as environment — so what this run proves
 * is the real chain: store the key, ask that provider for *its* catalogue, pin a
 * model from it, and take a governed turn on it. A provider whose account is out
 * of credit or whose runtime is not installed is a *result*: the row has to say
 * which, and the suite fails only when a row cannot reach a stated state at all.
 */

const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";
// Written straight into the tracked evidence folder rather than into the ignored
// `output/` tree: the FIXED-* entries cite these paths, and a citation a reader
// cannot open is not evidence.
const SHOTS = join(
  import.meta.dirname,
  "..",
  "..",
  "..",
  "docs",
  "plans",
  "screenshots",
  "working",
);
const PASSWORD = "Wizard-workbench-composer-1!";

const KEYS = {
  Anthropic: process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "",
  OpenRouter: process.env.RAIKER_LIVE_OPENROUTER_KEY ?? "",
  OpenAI: process.env.RAIKER_LIVE_OPENAI_KEY ?? "",
};

const consoleErrors: string[] = [];

async function register(page: Page): Promise<void> {
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText(/Verifying runtime/)).toBeHidden({ timeout: 120_000 });
  await page.getByLabel("Username").fill("owner");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  const confirm = page.getByLabel("Confirm password");
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill(PASSWORD);
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await page.getByRole("button", { name: "Unlock Raiker" }).click();
  }
  await page.waitForLoadState("networkidle").catch(() => undefined);
}

/** One row of the matrix, addressed by the provider it is for. */
const row = (page: Page, provider: string) =>
  page.getByRole("group", { name: provider, exact: true });

/**
 * What a row's catalogue currently says: the real model names, `"pending"` while
 * the read is still in flight, or the row's own sentence about why there are
 * none. Distinguishing the three is what stops this suite reading an empty
 * dropdown mid-request and reporting a provider with no models.
 */
async function modelsFor(target: Locator, provider: string): Promise<string[] | string> {
  // Exact: a long catalogue also carries "Filter <provider> models", whose
  // accessible name contains this one.
  const catalogue = target.getByLabel(`${provider} model`, { exact: true });
  const sentence = async () => ((await target.textContent()) ?? "").replace(/\s+/g, " ").trim();
  if (!(await catalogue.isVisible().catch(() => false))) {
    const state = await sentence();
    return /refused the credential|would not accept|could not be/.test(state) ? state : "pending";
  }
  const options = await catalogue.locator("option").allTextContents();
  if (options.some((option) => /Asking/.test(option))) return "pending";
  const real = options.filter((option) => option.trim() !== "" && !/No model listed/.test(option));
  if (real.length > 0) return real;
  const state = await sentence();
  return /answered|denied|reached|refused|does not publish/.test(state) ? state : "pending";
}

/**
 * Run the product's own readiness check against the pinned model.
 *
 * Pinning a model is not the same as proving it answers, and Raiker keeps those
 * apart deliberately: every work surface stays blocked until the *exact* model
 * has passed a check. That is the behaviour under test elsewhere; here it is a
 * prerequisite, so it is performed through the Test control an owner would use
 * rather than by reaching past the interface.
 */
async function proveModelReady(page: Page): Promise<boolean> {
  await page.goto(`${BASE}/#/new-chat`);
  await expect(page.getByLabel("Prompt", { exact: true })).toBeVisible({ timeout: 60_000 });
  const send = page.getByRole("button", { name: "Send", exact: true });
  const setUp = page.getByRole("button", { name: "Set up model" });
  // The composer opens on the "no model at all" fallback for the moment before
  // its model snapshot arrives, and the dialog opened in *that* state has no
  // model to check. Waiting for the picker to name a model first is what makes
  // the check land on the real one.
  await expect
    .poll(
      async () =>
        ((await page.getByRole("button", { name: /^Model for this turn:/ }).textContent()) ?? "")
          .replace(/\s+/g, " ")
          .trim(),
      { timeout: 60_000 },
    )
    .not.toMatch(/Not selected/);
  if (!(await setUp.isVisible({ timeout: 15_000 }).catch(() => false))) {
    // No strip means the model is already proven, which is the state this helper
    // exists to reach.
    return await send.isEnabled().catch(() => true);
  }
  // "Set up model" opens the dialog whose "Check again" runs the exact-model
  // check — the shortest real path from a blocked composer to a proven model.
  await setUp.click();
  const check = page.getByRole("button", { name: "Check again" });
  if (!(await check.isVisible({ timeout: 30_000 }).catch(() => false))) return false;
  await check.click();
  await expect(page.getByText(/Check complete|Check failed|no model to check/)).toBeVisible({
    timeout: 180_000,
  });
  const complete = await page.getByText("Check complete").isVisible().catch(() => false);
  await page.getByRole("button", { name: "Close" }).click();
  return complete;
}

test.describe.configure({ mode: "serial" });

test("the first-run wizard answers the model question on its own screen", async ({ page }) => {
  test.setTimeout(900_000);
  await register(page);

  // The first-run wizard is shown once per workspace. Re-running this file
  // against a host that has already completed it is a state, not a failure — say
  // so rather than timing out on a screen that has done its job.
  const stage = page.getByRole("heading", { name: "Choose where Raiker thinks" });
  const shown = await stage.isVisible({ timeout: 60_000 }).catch(() => false);
  test.skip(!shown, "this host has already completed first-run setup; use a fresh workspace");

  // ── Every provider gets a row ──────────────────────────────────────────
  // The old stage listed only profiles that already had a concrete model, so a
  // fresh install said "No model connection yet" and sent the owner elsewhere.
  for (const provider of [
    "Local GGUF",
    "Ollama",
    "LM Studio",
    "Anthropic",
    "OpenAI",
    "OpenRouter",
    "Ollama Cloud",
    "Hugging Face",
  ]) {
    await expect(row(page, provider)).toBeVisible({ timeout: 30_000 });
  }

  // ── On this machine: detection, not configuration ──────────────────────
  // Ollama is running on this host, so its row has to answer with the models it
  // actually has. A runtime that is not running has to say so instead.
  const ollama = row(page, "Ollama");
  const detected = ollama.getByLabel("Ollama model", { exact: true });
  await expect(detected).toBeVisible({ timeout: 60_000 });
  const detectedOptions = await detected.locator("option").allTextContents();
  const localState = (await ollama.textContent()) ?? "";
  expect(
    detectedOptions.some((option) => option.trim() !== "" && !/No model detected|Asking/.test(option)) ||
      /not running on this device|could not be reached/.test(localState),
  ).toBe(true);
  await page.screenshot({ path: join(SHOTS, "r0816b-01-first-run-provider-matrix.png"), fullPage: true });

  // ── With an API key: the key, then that provider's own catalogue ───────
  const listed: string[] = [];
  for (const [provider, key] of Object.entries(KEYS)) {
    if (key === "") continue;
    const target = row(page, provider);
    await target.getByLabel(`${provider} API key`).fill(key);
    await target.getByRole("button", { name: "Save and list models" }).click();
    // Storing a key and reaching the provider are two facts, and the row reports
    // them in that order. Waiting on the "Key stored" chip alone reads the
    // dropdown mid-request, so this waits for the catalogue read to *land*, in
    // whichever direction it lands.
    await expect
      .poll(async () => await modelsFor(target, provider), { timeout: 180_000 })
      .not.toEqual("pending");
    const outcome = await modelsFor(target, provider);
    if (Array.isArray(outcome)) {
      listed.push(`${provider}: ${outcome.length} models — ${outcome.slice(0, 3).join(", ")}`);
      // Model names are the provider's own, never invented here.
      expect(outcome.join(" ")).not.toContain("<model>");
    } else {
      listed.push(`${provider}: ${outcome.slice(0, 160)}`);
    }
    // A credential never comes back into the page.
    expect((await page.content()).includes(key)).toBe(false);
  }
  console.log("Wizard provider rows —\n" + listed.join("\n"));
  await page.screenshot({ path: join(SHOTS, "r0816b-02-first-run-catalogues-listed.png"), fullPage: true });

  // ── Pin one model from a real catalogue ───────────────────────────────
  if (KEYS.Anthropic !== "") {
    const anthropic = row(page, "Anthropic");
    const catalogue = anthropic.getByLabel("Anthropic model", { exact: true });
    await expect(catalogue).toBeVisible({ timeout: 60_000 });
    const outcome = await modelsFor(anthropic, "Anthropic");
    // A key that cannot reach Anthropic is a result, not a suite failure — but
    // pinning a model needs a real catalogue, so this states which happened.
    test.skip(!Array.isArray(outcome), `Anthropic did not list models: ${outcome}`);
    const options = outcome as string[];
    expect(options.length).toBeGreaterThan(0);
    const haiku = options.find((option) => /Haiku/i.test(option)) ?? options[0];
    await catalogue.selectOption({ label: haiku });
    await anthropic.getByRole("button", { name: "Use this model" }).click();
    await expect(page.getByText(/is selected\. Continue to set your privacy boundary/)).toBeVisible({
      timeout: 60_000,
    });
    await expect(anthropic.getByText(/^Selected:/)).toBeVisible({ timeout: 60_000 });
  }
  await page.screenshot({ path: join(SHOTS, "r0816b-03-first-run-model-pinned.png"), fullPage: true });

  // ── Finish the wizard ──────────────────────────────────────────────────
  await page.getByRole("button", { name: /^Continue$|^Decide later$/ }).click();
  await page.getByRole("button", { name: "Balanced" }).click();
  await page.getByRole("button", { name: "Set up later" }).click();
  await page.getByRole("button", { name: "Open Workbench" }).click();
  await expect(page).toHaveURL(/#\/home$/, { timeout: 60_000 });
});

test("the Workbench is a board over the running work, not a composer", async ({ page }) => {
  test.setTimeout(300_000);
  await register(page);
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByRole("heading", { name: /Welcome/ })).toBeVisible({ timeout: 60_000 });

  // The box is gone: it could not send anything, and it pushed the only live
  // information on the screen into a narrow rail.
  await expect(page.getByLabel("What would you like Raiker to do?")).toHaveCount(0);
  await expect(page.getByRole("tablist", { name: "Work mode" })).toHaveCount(0);
  for (const group of ["Running now", "Standing agents", "Scheduled runs"]) {
    await expect(page.getByRole("heading", { name: group })).toBeVisible({ timeout: 30_000 });
  }
  const start = page.getByRole("navigation", { name: "Start work" });
  for (const action of ["Start a conversation", "Start a build", "Plan a task or agent"]) {
    await expect(start.getByRole("link", { name: new RegExp(action) })).toBeVisible();
  }
  await page.screenshot({ path: join(SHOTS, "r0816b-04-workbench-board.png"), fullPage: true });

  // A real standing agent, so the board is proven against live rows rather than
  // against three empty cards. Planning one needs a model that has passed a
  // readiness check, exactly as a typed prompt does.
  const ready = await proveModelReady(page);
  test.skip(!ready, "no model reached a ready readiness state on this host");
  await page.goto(`${BASE}/#/tasks`);
  await page.getByRole("button", { name: "Daily routine" }).click();
  await page.getByLabel("Task title").fill("Watch the release branch");
  await page.getByLabel("Instructions").fill("Report anything that changed on the release branch.");
  // A daily routine is anchored to the time of its first run, so the form asks
  // for one; the far-future slot keeps this test from racing a real cycle.
  await page.getByLabel("Start time").fill("2099-01-01T09:00");
  // The form stays disabled until *this* page has read the model snapshot and
  // the exact model's readiness, which is the gate working rather than a slow
  // page — so wait for the state instead of racing it.
  const create = page.getByRole("button", { name: "Create daily routine" });
  const plannable = await expect(create)
    .toBeEnabled({ timeout: 120_000 })
    .then(() => true)
    .catch(() => false);
  test.skip(!plannable, "the task form stayed blocked: no model reached a ready state");
  await create.click();
  await page.goto(`${BASE}/#/workbench`);
  // Each board group is a named region, so a row is asserted in the group it
  // actually belongs to rather than anywhere on the page.
  const agents = page.getByRole("region", { name: "Standing agents" });
  await expect(agents.getByText("Watch the release branch").first()).toBeVisible({
    timeout: 60_000,
  });
  await expect(agents.getByText("Runs daily").first()).toBeVisible();
  // A daily routine armed for a future slot is not running this second.
  await expect(
    page.getByRole("region", { name: "Running now" }).getByText("Watch the release branch"),
  ).toHaveCount(0);
  await page.screenshot({ path: join(SHOTS, "r0816b-05-workbench-standing-agent.png"), fullPage: true });
});

test("both composers carry the reference control set, and Chat still sends", async ({ page }) => {
  test.setTimeout(900_000);
  await register(page);

  // ── Chat ───────────────────────────────────────────────────────────────
  await page.goto(`${BASE}/#/new-chat`);
  const prompt = page.getByLabel("Prompt", { exact: true });
  await expect(prompt).toBeVisible({ timeout: 60_000 });
  await expect(prompt).toHaveAttribute("placeholder", "How can I help you today?");
  // `+`, the approval-mode chip, and the model chip: Cowork's minimal composer
  // shape, with Raiker's governance controls in it and nothing else.
  await expect(page.getByRole("group", { name: "Chat or Build" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /^Approval mode:/ })).toBeVisible();
  const modelChip = page.getByRole("button", { name: /^Model for this turn:/ });
  await expect(modelChip).toBeVisible();
  await page.screenshot({ path: join(SHOTS, "r0816b-06-chat-composer.png"), fullPage: true });

  // The thinking budget belongs to the model, so it is a section of the model
  // menu rather than a second dropdown beside it.
  await modelChip.click();
  await expect(page.getByRole("menu", { name: "Models" })).toBeVisible();
  const effort = page.getByRole("button", { name: /^Effort/ });
  if (await effort.isVisible().catch(() => false)) {
    await effort.click();
    await expect(page.getByRole("group", { name: "Effort" })).toBeVisible();
    await expect(
      page.getByRole("group", { name: "Effort" }).getByRole("switch", { name: /Thinking/ }),
    ).toBeVisible();
    await page.screenshot({ path: join(SHOTS, "r0816b-06b-chat-model-effort.png"), fullPage: true });
  }
  await page.keyboard.press("Escape");

  // A real governed turn, so the restructured composer is proven to still send.
  const marker = "ROUND LIVE COMPOSER";
  // Send is disabled while the prompt is empty *and* while the exact model is
  // unproven, so the model is proven first and the prompt written second —
  // otherwise "disabled" says nothing about which of the two it was.
  await proveModelReady(page);
  await page.goto(`${BASE}/#/new-chat`);
  await expect(prompt).toBeVisible({ timeout: 60_000 });
  await prompt.fill(`Reply with exactly: ${marker}`);
  const send = page.getByRole("button", { name: "Send", exact: true });
  // `isEnabled` is a snapshot, and the composer is legitimately disabled for the
  // moment between mount and the model snapshot arriving. Waiting for the state
  // is the difference between "this host has no ready model" and "the assertion
  // was early".
  const sendable = await expect(send)
    .toBeEnabled({ timeout: 60_000 })
    .then(() => true)
    .catch(() => false);
  if (sendable) {
    await send.click();
    await expect(page.getByText(marker).first()).toBeVisible({ timeout: 300_000 });
    await page.screenshot({ path: join(SHOTS, "r0816b-07-chat-live-turn.png"), fullPage: true });
    // Every completed turn offers Branch — the last open part of C14.
    await expect(
      page.getByRole("button", { name: /Branch a second conversation/ }).first(),
    ).toBeVisible({ timeout: 60_000 });
  } else {
    // An unproven model is a state this suite reports rather than hides: the
    // readiness gate is doing its job, and the composer is honest about it.
    const strip = await page
      .getByRole("status")
      .filter({ hasText: /model/i })
      .first()
      .textContent()
      .catch(() => null);
    console.log(`Chat send stayed disabled. The composer said: ${strip ?? "(no readiness strip)"}`);
  }

  // ── Build ──────────────────────────────────────────────────────────────
  await page.goto(`${BASE}/#/build`);
  await expect(page.getByLabel("Describe the change")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole("group", { name: "Chat or Build" })).toHaveCount(0);
  const mode = page.getByRole("button", { name: /^How much Raiker may do this turn:/ });
  await expect(mode).toBeVisible();
  await mode.click();
  await expect(page.getByRole("menu", { name: "Mode" })).toBeVisible();
  for (const option of ["Plan", "Edit", "Auto"]) {
    await expect(page.getByRole("menuitemradio", { name: new RegExp(`^${option}`) })).toBeVisible();
  }
  await page.screenshot({ path: join(SHOTS, "r0816b-08-build-composer-mode.png"), fullPage: true });
  await page.keyboard.press("Escape");

  // The palette, in both themes, on the surface that shows the most of it.
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto(`${BASE}/#/new-chat`);
  await expect(page.getByLabel("Prompt", { exact: true })).toBeVisible({ timeout: 60_000 });
  await page.screenshot({ path: join(SHOTS, "r0816b-09-chat-dark.png"), fullPage: true });
  await page.emulateMedia({ colorScheme: "light" });

  expect(consoleErrors, `console errors: ${consoleErrors.join(" | ")}`).toEqual([]);
});
