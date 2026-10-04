/**
 * The 2026-10-04 round: Ollama found running, chosen once and kept checked, and
 * the release-readiness review items this run closed.
 *
 * Runs against a workspace reset with `scripts/reset_live_workspace.py`. The
 * Ollama scenario needs a service on 127.0.0.1:11434. Hosts that cannot fetch
 * Ollama run `scripts/live_ollama_standin.py --pidfile <file>` and point
 * `RAIKER_LIVE_OLLAMA_PIDFILE` at that file, which is also what lets this spec
 * stop the service and start it again to prove Raiker follows it. With a real
 * Ollama and no pidfile, the stop-and-start half is skipped with the reason.
 */
import { execFileSync, spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { capture, captureElement } from "./capture";
import { horizontalBleed, settled } from "./destinations";
import { chooseModelForTurn, OWNER_CREDENTIALS, signInAsOwner } from "./hosted-provider";
import { LIVE_BASE, sendTurn, useAnthropic } from "./live";

const BASE = LIVE_BASE;
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-10-04-ollama-readiness-round");
const REPO = join(import.meta.dirname, "..", "..");
const PIDFILE = process.env.RAIKER_LIVE_OLLAMA_PIDFILE ?? "";
const PYTHON = process.env.RAIKER_LIVE_PYTHON ?? "python";
const MODEL = process.env.RAIKER_LIVE_OLLAMA_MODEL ?? "llama3.2:3b";
const MODEL_LABEL = process.env.RAIKER_LIVE_OLLAMA_MODEL_LABEL ?? "Llama 3.2:3B";
const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? "";
const PROJECT_NAME = "Readiness round";

test.describe.configure({ mode: "serial" });

function watchFailures(page: Page): { failures: string[]; consoleErrors: string[] } {
  const failures: string[] = [];
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("response", (response) => {
    if (response.url().includes("/api/") && response.status() >= 500) {
      failures.push(`${response.status()} ${response.request().method()} ${response.url()}`);
    }
  });
  return { failures, consoleErrors };
}

async function signIn(page: Page): Promise<"created" | "unlocked"> {
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 30_000 });
  const username = page.getByLabel("Username");
  await expect(username).toBeEnabled({ timeout: 60_000 });
  await username.fill(OWNER_CREDENTIALS.user);
  await page.getByLabel("Password", { exact: true }).fill(OWNER_CREDENTIALS.password);
  const confirm = page.getByLabel("Confirm password");
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill(OWNER_CREDENTIALS.password);
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
    return "created";
  }
  await page.getByRole("button", { name: /unlock|sign in/i }).click();
  return "unlocked";
}

/** Stop the stand-in the round started, and say so. */
function stopStandin(): void {
  const pid = Number(readFileSync(PIDFILE, "utf-8").trim());
  process.kill(pid);
}

/** Start the stand-in again on the same port, writing the same pidfile. */
function startStandin(): void {
  const child = spawn(
    PYTHON,
    [join(REPO, "scripts", "live_ollama_standin.py"), "--models", `${MODEL},qwen3:8b`, "--pidfile", PIDFILE],
    { detached: true, stdio: "ignore" },
  );
  child.unref();
}

/**
 * Open Models and wait — without reloading — until the Ollama row says `text`.
 *
 * Nothing here presses Check or reloads: the host re-checks the chosen model on
 * its own tick and the open page re-reads it, which is the behaviour proved.
 */
async function waitForOllamaRow(page: Page, text: string | RegExp, timeout = 90_000) {
  if (!page.url().includes("tab=add")) {
    await page.goto(`${BASE}/#/models?tab=add`);
    await settled(page);
  }
  const row = page.locator(".local-row", { has: page.getByRole("heading", { name: "Ollama", exact: true }) });
  await expect(row).toContainText(text, { timeout });
}

test("a running Ollama is offered on first run, its chosen model is Ready, remembered and answers", async ({ page }) => {
  test.setTimeout(300_000);
  const { failures, consoleErrors } = watchFailures(page);
  const how = await signIn(page);
  test.skip(how !== "created", "This scenario is about first run and needs a reset workspace.");

  const title = page.locator("#setup-title");
  await expect(title).toBeVisible({ timeout: 60_000 });
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(title).toHaveText(/Choose how Raiker should think/, { timeout: 30_000 });

  // Running, offered — and nothing chosen on the owner's behalf. The profile
  // used to ship `gemma4:31b-cloud`, which this row printed as "Selected".
  const row = page.getByRole("group", { name: "Ollama", exact: true });
  await expect(row.getByText("Running on this device", { exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(row).not.toContainText("Selected:");
  await expect(page.getByText(/gemma/i)).toHaveCount(0);
  await capture(page, join(SHOTS, "01-setup-ollama-running-nothing-chosen.png"), row);

  await row.getByRole("button", { name: "Choose a model" }).click();
  const picker = page.getByRole("dialog", { name: "Ollama models" });
  await expect(picker.getByRole("button", { name: `Use ${MODEL_LABEL}` })).toBeVisible();
  await capture(page, join(SHOTS, "02-setup-ollama-models-it-serves.png"));
  await picker.getByRole("button", { name: `Use ${MODEL_LABEL}` }).click();

  await expect(page.getByText(`${MODEL_LABEL} is selected.`, { exact: false })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Ollama is running here")).toBeVisible();
  await capture(page, join(SHOTS, "03-setup-model-chosen.png"));
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: /Local, and the providers I connect/ }).click();
  await expect(page.getByRole("heading", { name: "Your Raiker is ready" })).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Start using Raiker" }).click();
  await expect(page.locator("#setup-title")).toBeHidden({ timeout: 30_000 });

  // Ready at once: choosing it ran the same exact-model check Check runs.
  await waitForOllamaRow(page, "Running on this device. Raiker checks it and this model on its own.");
  const models = page.locator(".local-row", { has: page.getByRole("heading", { name: "Ollama", exact: true }) });
  await expect(models).toContainText(MODEL_LABEL);
  await expect(models).toContainText("Ready");
  await capture(page, join(SHOTS, "04-models-ollama-ready.png"), models);

  // Remembered: a reload reads the stored choice, and Chat runs on it.
  await page.reload();
  await page.goto(`${BASE}/#/new-chat`);
  await settled(page);
  await expect(page.getByRole("button", { name: `Model for this turn: ${MODEL_LABEL}` }).first()).toBeVisible({
    timeout: 30_000,
  });
  await sendTurn(page, "Say hello in one line.");
  await expect(page.getByText(`Hello from ${MODEL}`).first()).toBeVisible({ timeout: 60_000 });
  await capture(page, join(SHOTS, "05-chat-answered-by-the-chosen-model.png"));

  expect(failures, failures.join("\n")).toEqual([]);
  expect(consoleErrors, consoleErrors.join("\n")).toEqual([]);
});

test("Raiker follows the Ollama service down and back up without being asked", async ({ page }) => {
  test.setTimeout(300_000);
  test.skip(!PIDFILE || !existsSync(PIDFILE), "Needs RAIKER_LIVE_OLLAMA_PIDFILE to stop and start the service.");
  const { failures } = watchFailures(page);
  await signIn(page);
  await expect(page.getByRole("navigation", { name: "All navigation" })).toBeVisible({ timeout: 60_000 });

  stopStandin();
  await waitForOllamaRow(page, /Installed, but not running|Not installed on this machine|not running/i);
  const row = page.locator(".local-row", { has: page.getByRole("heading", { name: "Ollama", exact: true }) });
  await expect(row).not.toContainText("Ready");
  await capture(page, join(SHOTS, "06-models-ollama-stopped.png"), row);

  // Overview names the step that stopped the work, and its one action.
  await page.goto(`${BASE}/#/models?tab=overview`);
  await settled(page);
  await expect(page.getByRole("button", { name: "Start the runtime" }).first()).toBeVisible({ timeout: 30_000 });
  await capture(page, join(SHOTS, "07-overview-start-the-runtime.png"));

  startStandin();
  await waitForOllamaRow(page, "Running on this device. Raiker checks it and this model on its own.");
  await expect(row).toContainText("Ready", { timeout: 60_000 });
  await capture(page, join(SHOTS, "08-models-ollama-back-and-ready.png"), row);
  expect(failures, failures.join("\n")).toEqual([]);
});

async function api<T>(page: Page, method: string, path: string, body?: unknown): Promise<T> {
  return page.evaluate(
    async ({ method, path, body }) => {
      const csrf = document.cookie.match(/(?:^|; )raiker_csrf=([^;]+)/)?.[1];
      const response = await fetch(path, {
        method,
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          ...(csrf ? { "X-Raiker-CSRF": decodeURIComponent(csrf) } : {}),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      return (await response.json()) as T;
    },
    { method, path, body },
  );
}

let projectId = "";

async function ensureProject(page: Page): Promise<string> {
  if (projectId) return projectId;
  const listed = await api<{ projects: { project_id: string; name: string }[] }>(page, "GET", "/api/projects");
  const existing = listed.projects.find((project) => project.name === PROJECT_NAME);
  if (existing) {
    projectId = existing.project_id;
    return projectId;
  }
  const created = await api<{ project_id?: string; project?: { project_id: string } }>(
    page, "POST", "/api/projects", { name: PROJECT_NAME },
  );
  projectId = created.project?.project_id ?? created.project_id ?? "";
  return projectId;
}

// ── Build: the boundary is the server's answer (DEC-06 step 1) ─────────────

test("Build's boundary line is the server's, and names a hosted model as leaving this machine", async ({ page }) => {
  test.setTimeout(420_000);
  const { failures, consoleErrors } = watchFailures(page);
  await signInAsOwner(page, BASE);
  // The key goes into the Connect dialog, as an owner's would.
  await useAnthropic(page);
  await ensureProject(page);
  await page.reload();
  await settled(page);
  await page.getByRole("link", { name: "Build", exact: true }).first().click();
  await settled(page);
  const boundaryRead = page.waitForResponse((response) => response.url().includes("/api/build/boundary?project_id="));
  // COMPOSER-03 — the project is chosen behind `+`, the way an owner does it.
  await page.getByRole("button", { name: "Add to this turn" }).first().click();
  await page.getByRole("menuitem", { name: "Work in a project" }).click();
  await page.getByLabel("Project for this build").selectOption({ label: PROJECT_NAME });
  await expect(page.getByText(`Working in ${PROJECT_NAME}`)).toBeVisible({ timeout: 30_000 });
  await boundaryRead;
  await chooseModelForTurn(page, /Haiku 4\.5/, "Build composer");

  const fromServer = await api<{
    project_name: string | null;
    environment_name: string;
    model: string | null;
    model_off_machine: boolean | null;
    ready: boolean;
  }>(page, "GET", `/api/build/boundary?project_id=${projectId}`);
  expect(fromServer.project_name).toBe(PROJECT_NAME);
  expect(fromServer.model).toContain("haiku");
  expect(fromServer.model_off_machine).toBe(true);
  expect(fromServer.ready).toBe(true);

  await page.getByRole("button", { name: /^Context for this turn/ }).click();
  const inspector = page.getByRole("dialog", { name: "Context for this turn" });
  await expect(inspector).toContainText(PROJECT_NAME);
  await expect(inspector).toContainText(fromServer.environment_name);
  await expect(inspector).toContainText("leaves this machine");
  const terms = await inspector.getByRole("term").allTextContents();
  const order = ["Project", "Runs on", "Model"].map((label) => terms.indexOf(label));
  expect(order.every((index) => index >= 0), terms.join(", ")).toBe(true);
  expect(order).toEqual([...order].sort((left, right) => left - right));
  await capture(page, join(SHOTS, "09-build-boundary-from-the-server.png"));
  await page.keyboard.press("Escape");

  await page.getByLabel("Describe the change").fill(
    "Without using any tools, reply in one short sentence: what is 6 times 7?",
  );
  const run = page.getByRole("button", { name: /^(Run|Plan|Propose)$/ }).first();
  await expect(run).toBeEnabled({ timeout: 60_000 });
  await run.click();
  await expect(page.getByText(/42/).last()).toBeVisible({ timeout: 120_000 });
  await capture(page, join(SHOTS, "10-build-real-turn.png"));
  expect(failures, failures.join("\n")).toEqual([]);
  expect(consoleErrors, consoleErrors.join("\n")).toEqual([]);
});

// ── Chat: the split view, a real turn and its continuity actions ──────────

test("Chat answers on Anthropic and still offers branch, rewind and summarise from the answer", async ({ page }) => {
  test.setTimeout(300_000);
  const { failures, consoleErrors } = watchFailures(page);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/new-chat`);
  await settled(page);
  await chooseModelForTurn(page, /Haiku 4\.5/);
  await sendTurn(page, "In one sentence, name the capital of France.");
  await expect(page.getByText(/Paris/).last()).toBeVisible({ timeout: 120_000 });
  // UX-CHAT-01 moved these into their own controller; they are still offered
  // from the message, under Continuity.
  await page.getByRole("button", { name: "More actions for this message" }).last().click();
  const continuity = page.getByRole("menu", { name: "Continuity" });
  await expect(continuity.getByRole("menuitem", { name: /^Branch/ })).toBeVisible();
  await expect(continuity.getByRole("menuitem", { name: /Summarise up to here/ })).toBeVisible();
  await capture(page, join(SHOTS, "11-chat-continuity-actions.png"));
  await page.keyboard.press("Escape");
  expect(failures, failures.join("\n")).toEqual([]);
  expect(consoleErrors, consoleErrors.join("\n")).toEqual([]);
});

// ── Design: compare, and go back as a new version (DEC-07 step 4) ──────────

test("Design compares two versions side by side and goes back without rewriting history", async ({ page }) => {
  test.setTimeout(240_000);
  test.skip(WORKSPACE === "", "Needs RAIKER_LIVE_WORKSPACE to seed pictures.");
  const { failures, consoleErrors } = watchFailures(page);
  await signInAsOwner(page, BASE);
  await ensureProject(page);
  const seeded = JSON.parse(
    execFileSync(PYTHON, [join(REPO, "scripts", "seed_design_assets.py"), WORKSPACE, "--project", projectId], {
      cwd: REPO,
      encoding: "utf-8",
    }),
  ) as string[];
  await page.goto(`${BASE}/#/design`);
  await settled(page);
  await page.getByRole("button", { name: "Open The same lighthouse with a red lantern room on the canvas" }).first().click();
  const inspector = page.getByRole("complementary", { name: "Inspector" });
  await inspector.getByLabel("Compare with an earlier version").selectOption({ label: "Version 1" });
  const compare = page.getByTestId("design-compare");
  await expect(compare).toContainText("Version 1 · A lighthouse at dusk, oil painting");
  await expect(compare).toContainText("Version 2 (this one)");
  await capture(page, join(SHOTS, "12-design-compare.png"));
  await page.getByRole("button", { name: "Go back to version 1" }).click();
  await expect(compare).toHaveCount(0);
  await expect(inspector).toContainText("Went back to");
  // History intact: three versions now, the first two unchanged.
  await expect(inspector.getByRole("button", { name: /^Version \d:/ })).toHaveCount(3);
  const gallery = await api<{ generations: { generation_id: string; kind: string; restored_generation_id: string | null }[] }>(
    page, "GET", "/api/images",
  );
  const reverted = gallery.generations.find((row) => row.kind === "revert");
  expect(reverted?.restored_generation_id).toBe(seeded[0]);
  expect(gallery.generations.map((row) => row.generation_id)).toEqual(expect.arrayContaining(seeded));
  await capture(page, join(SHOTS, "13-design-went-back-as-a-new-version.png"));
  await page.setViewportSize({ width: 390, height: 844 });
  await inspector.getByLabel("Compare with an earlier version").selectOption({ label: "Version 2" });
  await expect(page.getByTestId("design-compare")).toBeVisible();
  expect(await horizontalBleed(page)).toEqual([]);
  await capture(page, join(SHOTS, "14-design-compare-390.png"));
  expect(failures, failures.join("\n")).toEqual([]);
  expect(consoleErrors, consoleErrors.join("\n")).toEqual([]);
});

// ── Models: the split page still does what it did (UX-MODEL-01) ────────────

test("Models' Runtime tab saves a fallback, and Details and the picker still open", async ({ page }) => {
  test.setTimeout(240_000);
  const { failures, consoleErrors } = watchFailures(page);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/models?tab=runtime`);
  await settled(page);
  await page.getByText("Advanced routing").click();
  const addFallback = page.getByLabel("Add a fallback backend");
  const anthropicOption = await addFallback.locator("option", { hasText: /^Anthropic/ }).first().getAttribute("value");
  await addFallback.selectOption(anthropicOption ?? "");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await page.getByRole("button", { name: "Save sequence" }).click();
  await expect(page.getByText("Saved.").first()).toBeVisible({ timeout: 30_000 });
  await captureElement(page.locator("details.advanced-routing"), join(SHOTS, "15-models-runtime-fallback-saved.png"));
  const saved = await api<{ fallback_sequence: string[] }>(page, "GET", "/api/models");
  expect(saved.fallback_sequence).toContain("anthropic-hosted");
  // Put it back: the round leaves routing as it found it.
  await page.getByRole("button", { name: "Remove", exact: true }).first().click();
  await page.getByRole("button", { name: "Save sequence" }).click();
  await expect(page.getByText("Saved.").first()).toBeVisible({ timeout: 30_000 });

  await page.goto(`${BASE}/#/models?tab=add`);
  await settled(page);
  const ollama = page.locator(".local-row", { has: page.getByRole("heading", { name: "Ollama", exact: true }) });
  await ollama.getByRole("button", { name: /More|actions/i }).first().click();
  await page.getByRole("menuitem", { name: "Details" }).click();
  const details = page.getByRole("dialog", { name: "Ollama" });
  await expect(details).toContainText("Context capacity");
  await capture(page, join(SHOTS, "16-models-details-dialog.png"));
  await page.keyboard.press("Escape");
  await expect(details).toHaveCount(0);
  expect(failures, failures.join("\n")).toEqual([]);
  expect(consoleErrors, consoleErrors.join("\n")).toEqual([]);
});

// ── Every work surface at phone width, after the splits ─────────────────────

test("Chat, Build, Design and Models fit a phone with no console error", async ({ page }) => {
  test.setTimeout(240_000);
  const { failures, consoleErrors } = watchFailures(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await signInAsOwner(page, BASE);
  for (const route of ["new-chat", "build", "design", "models?tab=add", "models?tab=runtime", "models?tab=overview"]) {
    await page.goto(`${BASE}/#/${route}`);
    await settled(page);
    expect(await horizontalBleed(page), route).toEqual([]);
  }
  await capture(page, join(SHOTS, "17-models-overview-390.png"));
  expect(failures, failures.join("\n")).toEqual([]);
  expect(consoleErrors, consoleErrors.join("\n")).toEqual([]);
});
