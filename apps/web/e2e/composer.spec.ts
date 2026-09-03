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
import { capture } from "./capture";
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
      // BUG-256 — the composers read which speech runtime the owner's choice
      // resolved to. This fixture is a default install: no local runtime, so
      // dictation stays on the browser and the fake recognition above is what
      // the microphone drives.
      else if (path === "/api/speech/runtime") body = {
        runtime: { mode: "auto", endpoint: "", model: "", configured: false, effective: "browser" },
        max_audio_bytes: 12_582_912,
      };
      else if (path === "/api/code-repos") body = { repositories: [], active_repo_id: null };
      else if (path === "/api/host") body = { state: "running", detail: "Raiker is running.", pid: 4242, waiting: [], background_work: 0, service: { supported: true, registered: false, mechanism: "systemd --user", label: "raiker.service" } };
      else if (path === "/api/tasks") body = [];
      else if (path === "/api/notifications") body = [];
      else if (path === "/api/sessions") body = [];
      else if (path === "/api/approvals") body = [];
      else if (path === "/api/capabilities") body = [];
      // One configured rule that enforces, one that never fires, and one file
      // that did not parse: the three states the Hooks panel exists to tell
      // apart, so a redesign that collapses them fails here.
      else if (path === "/api/hooks") body = {
        active: true,
        rule_count: 2,
        rules: [
          {
            rule_id: "project:PreToolUse:0", event: "PreToolUse",
            event_summary: "Before policy finalises a tool call.",
            matcher: "shell", if_guard: "shell(rm -rf *)", scope: "project",
            source: "config/hooks.json", dispatched: true, can_decide: true,
            handlers: [{ id: "guard", type: "builtin", target: "block_destructive_shell", timeout_ms: 5000, decision_authority: true, available: true }],
          },
          {
            rule_id: "local:SessionEnd:1", event: "SessionEnd",
            event_summary: "A conversation ends.",
            matcher: "*", if_guard: null, scope: "local",
            source: ".raiker/hooks.json", dispatched: false, can_decide: false,
            handlers: [{ id: "on-end", type: "command", target: "scripts/end.sh", timeout_ms: 5000, decision_authority: false, available: true }],
          },
        ],
        sources: [{ path: "config/hooks.json", scope: "project", exists: true, loaded: true, rule_count: 1, error: null }],
        failed_sources: [{ path: "config/managed-hooks.json", scope: "managed", exists: true, loaded: false, rule_count: 0, error: "invalid_json:2:5" }],
        events: [
          { event: "PreToolUse", summary: "Before policy finalises a tool call.", dispatched: true, can_decide: true },
          { event: "SessionEnd", summary: "A conversation ends.", dispatched: false, can_decide: false },
        ],
        builtins: ["block_destructive_shell"],
        activity: [{ event_id: "evt_1", event_type: "hook_decision", session_id: "sess_1", timestamp: new Date().toISOString(), summary: "deny" }],
        activity_counts: { hook_decision: 1 },
      };
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
  await capture(page, join(shots, "voice-chat-desktop.png"));
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
  await capture(page, join(shots, "voice-build-desktop.png"));

  // Speech language is a queued settings write in General. BUG-256 added a
  // runtime, not a preference: there is no Voice section and nothing asks the
  // owner where audio should be transcribed, so General is the only place this
  // control has ever lived.
  await page.goto("http://raiker.test/#/settings?tab=general");
  await expect(page.getByRole("button", { name: "Voice" })).toHaveCount(0);
  await page.getByLabel("Speech language").selectOption("ja");
  await capture(page, join(shots, "voice-settings.png"));
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
  await capture(page, join(shots, "voice-chat-mobile.png"));
});

test("both composers stay anchored to the bottom on a tablet, not floating mid-page", async ({ page }) => {
  // Below the split-view breakpoint the two surfaces switch to `height: auto` so
  // the transcript, and Build's stacked rail, can take the room they need. The
  // floor has to survive that: without it an empty conversation collapsed to its
  // own content and left the composer in the middle of a tall screen.
  await page.setViewportSize({ width: 820, height: 1180 });

  for (const [route, label] of [
    ["new-chat", "Prompt"],
    ["build", "Describe the change"],
  ] as const) {
    await page.goto(`http://raiker.test/#/${route}`);
    await expect(page.getByLabel(label, { exact: true })).toBeVisible();

    const gap = await page.evaluate(() => {
      const content = document.querySelector(".content")!.getBoundingClientRect();
      const composer = [...document.querySelectorAll("form.composer")]
        .find((form) => (form as HTMLElement).offsetParent !== null)!
        .getBoundingClientRect();
      return content.bottom - composer.bottom;
    });

    // Only the shell's own bottom padding may sit under the composer.
    expect(gap).toBeLessThan(64);
    expect(gap).toBeGreaterThanOrEqual(0);
  }
});

test("minimal composers fit representative iPhone, Android, and tablet viewports", async ({ page }) => {
  test.setTimeout(90_000);
  const compactViewports = [
    ["iPhone SE", 375, 667],
    ["iPhone 15", 393, 852],
    ["compact Android", 360, 800],
    ["Pixel", 412, 915],
    ["iPad mini", 768, 1024],
    ["Android tablet", 800, 1280],
  ] as const;

  for (const [device, width, height] of compactViewports) {
    await page.setViewportSize({ width, height });

    for (const [route, label] of [["new-chat", "Prompt"], ["build", "Describe the change"]] as const) {
      await page.goto(`http://raiker.test/#/${route}`);
      await expect(page.getByLabel(label, { exact: true }), `${device} ${route} input`).toBeVisible();
      const activeComposer = page.locator("form.composer:visible");
      await expect(activeComposer.locator(".shortcut-hint"), `${device} ${route} shortcut prose`).toBeHidden();

      const geometry = await page.evaluate(() => {
        const composer = [...document.querySelectorAll("form.composer")]
          .find((form) => (form as HTMLElement).offsetParent !== null)!;
        const send = composer.querySelector("button[type=submit]")!.getBoundingClientRect();
        const box = composer.getBoundingClientRect();
        const descendantBottom = Math.max(...[...composer.querySelectorAll("*")]
          .filter((node) => (node as HTMLElement).offsetParent !== null)
          .map((node) => node.getBoundingClientRect().bottom));
        return {
          rootOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          composerLeft: box.left,
          composerRight: box.right,
          composerBottom: box.bottom,
          descendantBottom,
          sendWidth: send.width,
          sendHeight: send.height,
        };
      });
      expect(geometry.rootOverflow, `${device} ${route} overflow`).toBeLessThanOrEqual(1);
      expect(geometry.composerLeft, `${device} ${route} left edge`).toBeGreaterThanOrEqual(0);
      expect(geometry.composerRight, `${device} ${route} right edge`).toBeLessThanOrEqual(width + 1);
      expect(geometry.composerBottom, `${device} ${route} bottom edge`).toBeLessThanOrEqual(height + 1);
      expect(geometry.descendantBottom, `${device} ${route} control bottom edge`).toBeLessThanOrEqual(height + 1);
      expect(geometry.sendWidth, `${device} ${route} send width`).toBeGreaterThanOrEqual(44);
      expect(geometry.sendHeight, `${device} ${route} send height`).toBeGreaterThanOrEqual(44);

      if (route === "build") {
        await expect(page.getByRole("button", { name: "Governed terminal" })).toBeHidden();
        await expect(page.getByText("Auto follows your Permissions.")).toBeVisible();
      }
    }

  }

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("http://raiker.test/#/new-chat");
  await page.getByRole("button", { name: "Open navigation" }).click();
  const navigation = page.getByRole("navigation", { name: "All navigation" });
  await expect(navigation).toBeVisible();
  await expect(navigation.getByRole("link", { name: "Knowledge Map" })).toHaveCount(0);
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
  await capture(page, join(shots, "bug15-chat-composer.png"));

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
  await capture(page, join(shots, "bug15-build-composer.png"));
});

test("the Hooks tab tells an enforcing rule from a dead one and a broken file", async ({ page }) => {
  await page.goto("http://raiker.test/#/extensions?tab=hooks");

  await expect(page.getByRole("heading", { name: "Hooks", exact: true })).toBeVisible();

  // 1. A file the runtime could not read is visible rather than silent.
  await expect(page.getByText(/could not be read/i)).toBeVisible();
  await expect(page.getByText("invalid_json:2:5")).toBeVisible();

  // 2. A rule that enforces is separated from one that only observes …
  await expect(page.getByText("Can deny or ask")).toBeVisible();

  // 3. … and from one whose event this build never emits.
  await expect(
    page.getByText(/never emits SessionEnd, so this rule is configured but never fires/i),
  ).toBeVisible();

  // The builtin names an owner may write in the file, since there is no form.
  await expect(page.getByRole("heading", { name: "Built-in handlers" })).toBeVisible();

  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await capture(page, join(shots, "hooks-tab.png"));
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
  await capture(page, join(shots, "settings-redesign.png"));
});

test("Models names providers in plain language and offers a real model list", async ({ page }) => {
  // The fixture profile is a hosted Anthropic account, so its card lives on the
  // Hosted tab; Local holds the runtimes that run on this machine.
  await page.goto("http://raiker.test/#/models?tab=hosted");
  await expect(page.getByRole("heading", { name: "Choose where Raiker thinks" })).toBeVisible();
  // The internal profile id is never the thing the owner is shown.
  await expect(page.getByText("anthropic-hosted")).toHaveCount(0);
  // Choosing models is a dialog of switches now, not an inline select: each
  // switch keeps one of the provider's models offered in every picker.
  await page.getByRole("button", { name: /Select models/i }).first().click();
  await expect(page.getByRole("dialog", { name: /models/i })).toBeVisible();
  await expect(page.getByRole("checkbox").first()).toBeVisible();
  await capture(page, join(shots, "models-redesign.png"));
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
  await capture(page, join(shots, "workbench-dashboard-redesign.png"));
});

test("desktop view audit covers every route, Models tab, and Settings section", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1920, height: 1080 });

  const canonical = [
    ["workbench", "Workbench", "operational"],
    ["new-chat", "Chat", "work-surface"],
    ["build", "Build", "work-surface"],
    ["search-chat", "Threads", "reading"],
    ["tasks", "Tasks", "operational"],
    ["projects", "Projects", "operational"],
    ["memory", "Memory", "operational"],
    ["brain", "Knowledge Map", "operational"],
    ["approvals", "Approvals", "operational"],
    ["capabilities", "Permissions", "operational"],
    ["models?tab=local", "Models", "operational"],
    ["extensions?tab=connectors", "Extensions", "operational"],
    ["extensions?tab=mcp", "Extensions", "operational"],
    ["extensions?tab=skills", "Extensions", "operational"],
    ["extensions?tab=hooks", "Extensions", "operational"],
    ["extensions?tab=plugins", "Extensions", "operational"],
    ["extensions?tab=channels", "Extensions", "operational"],
    ["observe?tab=overview", "Observability", "operational"],
    ["observe?tab=sessions", "Observability", "operational"],
    ["observe?tab=activity", "Observability", "operational"],
    ["observe?tab=checkpoints", "Observability", "operational"],
    ["observe?tab=diagnostics", "Observability", "operational"],
    ["observe?tab=work", "Observability", "operational"],
    ["observe?tab=notifications", "Observability", "operational"],
    ["guide", "Guide", "reading"],
    ["settings?tab=general", "Settings", "workspace"],
  ] as const;
  const modelTabs = ["hosted", "huggingface", "activity", "routing", "pricing", "posture"] as const;
  const settingsSections = [
    "notification", "personalisation", "security", "privacy", "account",
    "web-access", "git-credential", "runtime",
  ] as const;
  const settingsLabels: Record<string, string> = {
    general: "General",
    notification: "Notifications",
    personalisation: "Personalisation",
    security: "Security & sign-in",
    privacy: "Privacy",
    account: "Account",
    "web-access": "Web access",
    "git-credential": "Git credential",
    runtime: "Runtime configuration",
  };
  const states = [
    ...canonical,
    ...modelTabs.map((tab) => [`models?tab=${tab}`, "Models", "operational"] as const),
    ...settingsSections.map((tab) => [`settings?tab=${tab}`, "Settings", "workspace"] as const),
  ];

  for (const [route, title, layout] of states) {
    await page.goto(`http://raiker.test/#/${route}`);
    const canvas = page.getByTestId("responsive-page");
    await expect(canvas, route).toHaveAttribute("data-layout", layout);
    await expect(page.locator("header .page-title"), route).toHaveText(title);
    await expect(page.locator("header .page-hint"), route).not.toBeEmpty();

    const requestedTab = new URLSearchParams(route.split("?", 2)[1] ?? "").get("tab");
    if (requestedTab && (route.startsWith("models") || route.startsWith("extensions") || route.startsWith("observe"))) {
      await expect(page.locator(`[role="tab"][data-tab="${requestedTab}"]`), route).toHaveAttribute("aria-selected", "true");
    }
    if (requestedTab && route.startsWith("settings")) {
      const selectedSection = page.locator('.section-rail [aria-current="page"]');
      await expect(selectedSection, route).toHaveCount(1);
      await expect(selectedSection, route).toHaveText(settingsLabels[requestedTab]);
    }

    const geometry = await page.evaluate(() => {
      const canvas = document.querySelector<HTMLElement>('[data-testid="responsive-page"]')!;
      const main = document.querySelector<HTMLElement>("main#main")!;
      const canvasBox = canvas.getBoundingClientRect();
      const mainBox = main.getBoundingClientRect();
      const emptyIcons = [...document.querySelectorAll("main#main svg, header svg, nav svg")]
        .filter((svg) => svg.getBoundingClientRect().width > 0 && svg.children.length === 0).length;
      const control = document.querySelector<HTMLElement>("main#main button, main#main input, main#main select");
      const visibleChild = ([...canvas.children] as HTMLElement[])
        .find((child) => child.getBoundingClientRect().width > 0);
      return {
        overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        emptyIcons,
        centeringError: Math.abs((canvasBox.left - mainBox.left) - (mainBox.right - canvasBox.right)),
        firstChildRatio: visibleChild ? visibleChild.getBoundingClientRect().width / canvasBox.width : 1,
        controlFont: control ? Number.parseFloat(getComputedStyle(control).fontSize) : 0,
      };
    });
    expect(geometry.overflow, route).toBeLessThanOrEqual(1);
    expect(geometry.emptyIcons, route).toBe(0);
    expect(geometry.centeringError, route).toBeLessThanOrEqual(1);
    if (route === "tasks") expect(geometry.firstChildRatio, route).toBeGreaterThanOrEqual(0.9);
    if (geometry.controlFont > 0) expect(geometry.controlFont, route).toBeLessThanOrEqual(16);
  }
});
