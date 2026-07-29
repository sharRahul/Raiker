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
      else if (path === "/api/settings") body = { settings: {} };
      else if (path === "/api/models") body = { profiles: [model], current_profile_id: model.profile_id, current_model: model.model, fallback_sequence: [] };
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
  await page.screenshot({ path: "../../output/playwright/bug15-chat-composer.png", fullPage: true });

  await page.getByRole("link", { name: "Build" }).click();
  await expect(page.getByLabel("Describe the change")).toBeVisible();
  await expect(page.getByRole("group", { name: "How much Raiker may do" })).toBeVisible();
  await page.screenshot({ path: "../../output/playwright/bug15-build-composer.png", fullPage: true });
});
