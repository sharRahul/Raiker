import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { extname, join } from "node:path";

const dist = join(import.meta.dirname, "..", "dist");
const model = {
  profile_id: "anthropic-hosted", provider: "anthropic", model: "claude-sonnet-4-5",
  default_state: "enabled_runtime", local_only: false, requires_network: true,
  endpoint_kind: "remote_hosted", requires_egress_policy: true, requires_budget_policy: true,
  runtime_gate: "hosted_model_runtime", off_machine: true, selected: true,
  connection_configured: true, configured: true, billable: true, supports_reasoning: true,
  supports_reasoning_effort: true, reasoning_effort_values: ["low", "medium", "high"],
  context_window_tokens: 200000,
};

test.beforeEach(async ({ page }) => {
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
      else if (path === "/api/settings") body = { settings: {}, status: { vault: "configured", mfa_enrolled: false, username: "owner" } };
      else if (path === "/api/models") body = { profiles: [model], current_profile_id: model.profile_id, current_model: model.model, fallback_sequence: [] };
      else if (path.endsWith("/provider-models")) body = { profile_id: model.profile_id, provider: model.provider, status: "available", reason_code: null, models: ["claude-sonnet-4-5", "claude-opus-4-1"] };
      else if (path === "/api/settings/composer-approval-mode") body = { approval_mode: "manual" };
      else if (path === "/api/code-repos") body = { repositories: [], active_repo_id: null };
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
  await expect(page.getByLabel("Prompt")).toBeVisible();
});

test("Chat and Build composers stay polished and usable", async ({ page }) => {
  const chat = page.getByLabel("Prompt");
  await expect(chat).toHaveAttribute("placeholder", "How can I help you today?");
  await expect(page.getByRole("button", { name: /Model for this turn/ })).toBeVisible();
  await page.getByRole("button", { name: /Model for this turn/ }).click();
  await expect(page.getByRole("menu", { name: "Models" })).toBeVisible();
  await page.getByRole("menuitemradio", { name: /Sonnet 4\.5/i }).click();
  await page.screenshot({ path: "../../output/playwright/bug15-chat-composer.png", fullPage: true });

  await page.getByRole("link", { name: "Build" }).click();
  await expect(page.getByLabel("Describe the change")).toBeVisible();
  await expect(page.getByRole("group", { name: "How much Raiker may do" })).toBeVisible();
  await page.getByRole("button", { name: /Model for this turn/ }).click();
  await expect(page.getByRole("menu", { name: "Models" })).toBeVisible();
  await page.screenshot({ path: "../../output/playwright/bug15-build-composer.png", fullPage: true });
});

test("Settings and Models present focused, human-readable controls", async ({ page }) => {
  await page.goto("http://raiker.test/#/settings");
  await expect(page.getByRole("heading", { name: "Make Raiker feel like yours" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Storage" })).toHaveCount(0);
  await page.screenshot({ path: "../../output/playwright/settings-redesign.png", fullPage: true });

  await page.goto("http://raiker.test/#/models");
  await expect(page.getByRole("heading", { name: "Choose where Raiker thinks" })).toBeVisible();
  await expect(page.getByText("anthropic-hosted")).toHaveCount(0);
  await page.getByRole("button", { name: /Change model/i }).first().click();
  await expect(page.getByRole("combobox", { name: "Available models" })).toBeVisible();
  await page.screenshot({ path: "../../output/playwright/models-redesign.png", fullPage: true });
});

test("new-account Workbench is welcoming and action oriented", async ({ page }) => {
  await page.goto("http://raiker.test/#/workbench");
  await expect(page.getByRole("heading", { name: "Welcome to your Work Dashboard" })).toBeVisible();
  await expect(page.getByText("Pick up where you left off", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("link", { name: /Start a new chat/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Create a project/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Create a task/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Schedule a task/ })).toBeVisible();
  await expect(page.getByText("Resume a conversation", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Runtime issues", { exact: true })).toBeVisible();
  await page.screenshot({
    path: "../../docs/plans/screenshots/working/workbench-dashboard-redesign.png",
    fullPage: true,
  });
});
