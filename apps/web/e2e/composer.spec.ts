// The mocked regression suite: the built app served from `dist`, every API call
// answered from the fixture below, and no credential or network of any kind.
// It is the only spec in `e2e/` that is not `*-live.spec.ts`, which is what lets
// CI run it (see `.github/workflows/web.yml` and the `mocked` Playwright
// project) while the live scenarios stay a deliberate, credentialled local run.
//
// BUG-41 — this file used to assert a Workbench and a Settings page that the
// FIXED-46/FIXED-48 redesigns had already replaced: `Start a new chat` and
// `Schedule a task` quick actions, and a "Make Raiker feel like yours" heading.
// Nothing ran it, so the drift was invisible. The assertions below are written
// against the surfaces as they are now, and the suite is in CI so the next
// redesign cannot silently outrun it.
import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { readFile } from "node:fs/promises";
import { extname, join } from "node:path";

const dist = join(import.meta.dirname, "..", "dist");
const shots = join(import.meta.dirname, "..", "..", "..", "output", "playwright");
const model = {
  profile_id: "anthropic-hosted", provider: "anthropic", model: "claude-sonnet-4-5",
  default_state: "enabled_runtime", local_only: false, requires_network: true,
  endpoint_kind: "remote_hosted", requires_egress_policy: true, requires_budget_policy: true,
  runtime_gate: "hosted_model_runtime", off_machine: true, selected: true,
  connection_configured: true, configured: true, ready: true, readiness_state: "ready",
  billable: true, supports_reasoning: true,
  supports_reasoning_effort: true, reasoning_effort_values: ["low", "medium", "high"],
  context_window_tokens: 200000,
};

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    class FakeRecognition {
      continuous = false;
      interimResults = false;
      lang = "";
      onresult: ((event: unknown) => void) | null = null;
      onerror: ((event: unknown) => void) | null = null;
      onend: (() => void) | null = null;
      constructor() { (window as unknown as { __voiceRecognition: FakeRecognition }).__voiceRecognition = this; }
      start() { document.documentElement.dataset.voiceListening = "true"; }
      stop() { delete document.documentElement.dataset.voiceListening; this.onend?.(); }
      abort() { delete document.documentElement.dataset.voiceListening; this.onend?.(); }
      emitFinal(text: string) {
        this.onresult?.({
          resultIndex: 0,
          results: [Object.assign([{ transcript: text }], { isFinal: true })],
        });
      }
    }
    Object.assign(window, { SpeechRecognition: FakeRecognition });
  });
  let settings: Record<string, unknown> = {};
  await page.route("http://raiker.test/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.startsWith("/api/")) {
      const path = url.pathname;
      let body: unknown = {};
      if (path === "/api/health") body = { status: "ok" };
      else if (path === "/api/auth/bootstrap-status") body = { can_register: false };
      else if (path === "/api/auth/login") body = { stage: "session", principal_id: "principal_owner", token: "test-token", ticket: null };
      else if (path === "/api/runtime-mode") body = { mode_name: "local_single_user_runtime", status: "active", allowed_modes: ["local_single_user_runtime"] };
      else if (path === "/api/diagnostics") body = { summary: {}, counts: {}, readiness: {}, missing_config: [], provider_health: [] };
      else if (path === "/api/projects") body = { projects: [], active_project_id: null };
      else if (path === "/api/settings") {
        if (route.request().method() === "PUT") {
          const submitted = route.request().postDataJSON() as { settings?: Record<string, unknown> };
          settings = submitted.settings ?? settings;
        }
        body = { settings, status: { vault: "configured", mfa_enrolled: false, username: "owner" } };
      }
      else if (path === "/api/models") body = { profiles: [model], current_profile_id: model.profile_id, current_model: model.model, fallback_sequence: [] };
      else if (path.endsWith("/provider-models")) body = { profile_id: model.profile_id, provider: model.provider, status: "available", reason_code: null, models: ["claude-sonnet-4-5", "claude-opus-4-1"] };
      else if (path === "/api/settings/composer-approval-mode") body = { approval_mode: "manual" };
      else if (path === "/api/code-repos") body = { repositories: [], active_repo_id: null };
      else if (path === "/api/host") body = { state: "running", detail: "Raiker is running.", pid: 4242, waiting: [], background_work: 0, service: { supported: true, registered: false, mechanism: "systemd --user", label: "raiker.service" } };
      else if (path === "/api/tasks") body = [];
      else if (path === "/api/notifications") body = [];
      else if (path === "/api/sessions") body = [];
      else if (path === "/api/approvals") body = [];
      else if (path === "/api/capabilities") body = [];
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
      return;
    }
    const relative = url.pathname === "/" ? "index.html" : url.pathname.slice(1);
    const file = join(dist, relative);
    const types: Record<string, string> = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".woff2": "font/woff2" };
    await route.fulfill({ body: await readFile(file), contentType: types[extname(file)] ?? "application/octet-stream" });
  });
  await page.goto("http://raiker.test/#/new-chat");
  await page.getByLabel("Username").fill("owner");
  await page.getByLabel("Password", { exact: true }).fill("test-password");
  await page.getByRole("button", { name: /unlock/i }).click();
  await expect(page.getByLabel("Prompt", { exact: true })).toBeVisible();
});

test("governed voice stays editable and visually consistent in Chat, Build, mobile, and Settings", async ({ page }) => {
  const promptPosts: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && new URL(request.url()).pathname.startsWith("/api/prompts")) {
      promptPosts.push(request.postData() ?? "");
    }
  });

  const chat = page.getByLabel("Prompt", { exact: true });
  await page.getByRole("button", { name: "Dictate" }).click();
  await page.evaluate(() => (window as unknown as { __voiceRecognition: { emitFinal(text: string): void } }).__voiceRecognition.emitFinal("check the repository"));
  await expect(chat).toHaveValue("check the repository");
  expect(promptPosts).toHaveLength(0);
  await expect(page.getByText("Listening…", { exact: true })).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.getByRole("button", { name: "Done dictating" }).click();
  expect(promptPosts).toHaveLength(0);
  await page.screenshot({ path: join(shots, "voice-chat-desktop.png"), fullPage: true });
  await page.getByRole("button", { name: "Send" }).click();
  await expect.poll(() => promptPosts.length).toBe(1);
  expect(JSON.parse(promptPosts[0])).toMatchObject({ text: "check the repository", input_mode: "dictated" });

  await page.getByRole("navigation", { name: "All navigation" }).getByRole("link", { name: "Build" }).click();
  const build = page.getByLabel("Describe the change");
  await build.fill("keep this");
  await page.getByRole("button", { name: "Dictate" }).click();
  await page.evaluate(() => (window as unknown as { __voiceRecognition: { emitFinal(text: string): void } }).__voiceRecognition.emitFinal("discard this"));
  await page.getByRole("button", { name: "Cancel dictation" }).click();
  await expect(build).toHaveValue("keep this");
  await page.screenshot({ path: join(shots, "voice-build-desktop.png"), fullPage: true });

  await page.goto("http://raiker.test/#/settings?tab=general");
  await page.getByLabel("Speech language").selectOption("ja");
  await page.screenshot({ path: join(shots, "voice-settings.png"), fullPage: true });
  await Promise.all([
    page.waitForRequest((request) => request.method() === "PUT" && new URL(request.url()).pathname === "/api/settings"),
    page.getByRole("button", { name: /save changes/i }).click(),
  ]);
  await page.goto("http://raiker.test/#/settings?tab=general");
  await expect(page.getByLabel("Speech language")).toHaveValue("ja");

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("http://raiker.test/#/new-chat");
  await expect(page.getByRole("button", { name: "Dictate" })).toBeVisible();
  const mobileDrawer = page.locator("#all-navigation");
  await expect(mobileDrawer).toHaveAttribute("aria-hidden", "true");
  await expect.poll(async () => (await mobileDrawer.boundingBox())?.x ?? 0).toBeLessThan(-200);
  await page.screenshot({ path: join(shots, "voice-chat-mobile.png"), fullPage: true });
});

test("Chat and Build composers stay polished and usable", async ({ page }) => {
  const chat = page.getByLabel("Prompt", { exact: true });
  await expect(chat).toHaveAttribute("placeholder", "How can I help you today?");
  // The Chat composer is deliberately minimal: no surface switch, no duplicate
  // capacity chip. What is left is what a prompt needs.
  await expect(page.getByRole("group", { name: "Chat or Build" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Model context capacity" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Model for this turn/ })).toBeVisible();
  await page.getByRole("button", { name: /Model for this turn/ }).click();
  await expect(page.getByRole("menu", { name: "Models" })).toBeVisible();
  await page.getByRole("menuitemradio", { name: /Sonnet 4\.5/i }).click();
  await page.screenshot({ path: join(shots, "bug15-chat-composer.png"), fullPage: true });

  await page.getByRole("navigation", { name: "All navigation" }).getByRole("link", { name: "Build" }).click();
  await expect(page.getByLabel("Describe the change")).toBeVisible();
  // The posture is one chip and one menu now, matching where every reference
  // coding agent keeps the same control.
  const mode = page.getByRole("button", { name: /^How much Raiker may do this turn:/ });
  await expect(mode).toBeVisible();
  await mode.click();
  await expect(page.getByRole("menu", { name: "Mode" })).toBeVisible();
  for (const option of ["Plan", "Edit", "Auto"]) {
    await expect(page.getByRole("menuitemradio", { name: new RegExp(`^${option}`) })).toBeVisible();
  }
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: /Model for this turn/ }).click();
  await expect(page.getByRole("menu", { name: "Models" })).toBeVisible();
  await page.screenshot({ path: join(shots, "bug15-build-composer.png"), fullPage: true });
});

test("Settings presents one section rail rather than a wall of fields", async ({ page }) => {
  await page.goto("http://raiker.test/#/settings");
  // Scoped to the content region: the top bar carries the same page name, and an
  // unscoped heading query would pass on that alone.
  const main = page.getByRole("main");
  await expect(main.getByRole("heading", { name: "Settings", exact: true })).toBeVisible();

  // The rail is the redesign: personal sections first, system configuration
  // named as such, and nothing that was folded away reachable as a stray tab.
  const rail = page.getByRole("navigation", { name: "Settings sections" });
  for (const section of [
    "General",
    "Notifications",
    "Personalisation",
    "Security & sign-in",
    "Account",
    "Runtime configuration",
  ]) {
    await expect(rail.getByRole("button", { name: section })).toBeVisible();
  }
  await expect(rail.getByRole("button", { name: "Storage" })).toHaveCount(0);

  // Personalisation is where the density and typography choices live (BUG-37),
  // so a redesign that drops them takes this test with it.
  await rail.getByRole("button", { name: "Personalisation" }).click();
  const density = page.getByRole("radiogroup", { name: "Density" });
  await expect(density).toBeVisible();
  for (const mode of ["Compact", "Comfortable", "Spacious"]) {
    await expect(density.getByRole("radio", { name: new RegExp(mode) })).toBeVisible();
  }
  await page.screenshot({ path: join(shots, "settings-redesign.png"), fullPage: true });
});

test("Models names providers in plain language and offers a real model list", async ({ page }) => {
  // The fixture profile is a hosted Anthropic account, so its card lives on the
  // Hosted tab; Local holds the runtimes that run on this machine.
  await page.goto("http://raiker.test/#/models?tab=hosted");
  await expect(page.getByRole("heading", { name: "Choose where Raiker thinks" })).toBeVisible();
  // The internal profile id is never the thing the owner is shown.
  await expect(page.getByText("anthropic-hosted")).toHaveCount(0);
  await page.getByRole("button", { name: /Change model/i }).first().click();
  await expect(page.getByRole("combobox", { name: "Available models" })).toBeVisible();
  await page.screenshot({ path: join(shots, "models-redesign.png"), fullPage: true });
});

test("new-account Workbench is a board over the work, not a second composer", async ({ page }) => {
  await page.goto("http://raiker.test/#/workbench");
  await expect(page.getByRole("heading", { name: "Welcome to your Work Dashboard" })).toBeVisible();

  // The removed box. The Workbench composer could not send anything: it handed
  // the prompt to Chat, Build or Tasks, which re-showed it in that surface's own
  // composer. What is left is the live answer to "what is Raiker doing".
  await expect(page.getByLabel("What would you like Raiker to do?")).toHaveCount(0);
  await expect(page.getByRole("tablist", { name: "Work mode" })).toHaveCount(0);
  for (const group of ["Running now", "Standing agents", "Scheduled runs"]) {
    await expect(page.getByRole("heading", { name: group })).toBeVisible();
  }
  await expect(page.getByText("Nothing is running.")).toBeVisible();
  await expect(page.getByText("No agent is standing.")).toBeVisible();
  await expect(page.getByText("Nothing is scheduled.")).toBeVisible();

  // Starting work is a link to the surface that owns a composer, so there is
  // exactly one composer per kind of work.
  const start = page.getByRole("navigation", { name: "Start work" });
  for (const action of [
    "Start a conversation",
    "Start a build",
    "Plan a task or agent",
    "Open a project",
  ]) {
    await expect(start.getByRole("link", { name: new RegExp(action) })).toBeVisible();
  }

  await expect(page.getByRole("heading", { name: "Needs your attention" })).toBeVisible();
  await expect(page.getByText("Runtime issues", { exact: true })).toBeVisible();
  await page.screenshot({ path: join(shots, "workbench-dashboard-redesign.png"), fullPage: true });
});
