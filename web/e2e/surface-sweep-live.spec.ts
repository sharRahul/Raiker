/**
 * Every pop-up surface, opened the way an owner opens it, and photographed.
 *
 * The page sweep (`all-pages-live.spec.ts`) photographs destinations. It never
 * opens a dialog, menu, popover, drawer or sheet, so a 2026-11-14 review that
 * relied on it missed every one of them. This sweep opens each surface
 * through the real UI on a live host and captures it, at the width and theme
 * given by `SWEEP_WIDTH` (default 1440) and `SWEEP_THEME` (light | dark).
 *
 * A surface the sweep could not open is recorded in `opened.json` with the
 * reason rather than failing the run: the point is an inventory a person
 * reviews, and one missing button must not hide the other sixty surfaces.
 * The run fails only when fewer than `SWEEP_MIN` surfaces opened.
 */
import { expect, test, type Page } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { VISUAL_DESTINATIONS } from "./destinations";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const WIDTH = Number(process.env.SWEEP_WIDTH ?? 1440);
const HEIGHT = WIDTH < 700 ? 844 : 1000;
const THEME = (process.env.SWEEP_THEME ?? "light") as "light" | "dark";
const ONLY = process.env.SWEEP_ONLY ? new RegExp(process.env.SWEEP_ONLY) : null;
const DIR = `../output/playwright/surfaces/${THEME}-${WIDTH}`;

type Step = (page: Page) => Promise<void>;

/** Role first; then a `<summary>` disclosure; then any visible text. */
async function openBy(page: Page, scope: string, name: string | RegExp, role: string): Promise<void> {
  const root = page.locator(scope);
  const candidates = [
    root.getByRole(role as "button", { name }),
    root.locator("summary", { hasText: name }),
    root.getByText(name),
  ];
  for (const candidate of candidates) {
    const first = candidate.first();
    if (await first.isVisible().catch(() => false)) {
      await first.click({ timeout: 8_000 });
      return;
    }
  }
  await candidates[0].first().click({ timeout: 8_000 });
}
const click = (name: string | RegExp, role: "button" | "link" | "menuitem" | "tab" = "button"): Step =>
  async (page) => openBy(page, "body", name, role);
const clickIn = (scope: string, name: string | RegExp): Step => async (page) =>
  openBy(page, scope, name, "button");
const press = (key: string): Step => async (page) => {
  await page.keyboard.press(key);
};

interface Surface {
  name: string;
  route: string;
  steps: Step[];
}

const SURFACES: Surface[] = [
  // Shell
  { name: "shell-command-palette", route: "home", steps: [press("Control+k")] },
  { name: "shell-all-pages", route: "home", steps: [click("More pages and settings")] },
  { name: "shell-help", route: "home", steps: [click("Help")] },
  { name: "shell-notifications", route: "home", steps: [click("Notifications")] },
  { name: "shell-host", route: "home", steps: [click(/^Host/)] },
  { name: "shell-stop", route: "home", steps: [click(/^Stop all work/)] },
  { name: "shell-shortcuts", route: "home", steps: [press("Shift+?")] },
  // Chat
  { name: "chat-add-menu", route: "new-chat", steps: [click("Add to this turn")] },
  { name: "chat-tools-menu", route: "new-chat", steps: [click("Tools")] },
  { name: "chat-approval-mode", route: "new-chat", steps: [click(/^How much Raiker does without asking/)] },
  { name: "chat-model-picker", route: "new-chat", steps: [click(/^Model for this turn/)] },
  { name: "chat-conversation-actions", route: "new-chat", steps: [click("Conversation actions")] },
  { name: "chat-thread-actions", route: "work?tab=threads", steps: [
    async (page) => page.locator("main a[href*='session']").first().click({ timeout: 8_000 }),
    async (page) => page.waitForTimeout(1500),
    click("Conversation actions"),
  ] },
  { name: "chat-thread-context", route: "work?tab=threads", steps: [
    async (page) => page.locator("main a[href*='session']").first().click({ timeout: 8_000 }),
    async (page) => page.waitForTimeout(1500),
    click(/^Context for this turn/),
  ] },
  { name: "chat-thread-export", route: "work?tab=threads", steps: [
    async (page) => page.locator("main a[href*='session']").first().click({ timeout: 8_000 }),
    async (page) => page.waitForTimeout(1500),
    click("Conversation actions"),
    click(/^Export conversation/, "menuitem"),
  ] },
  // Home
  { name: "home-composer-posture", route: "home", steps: [clickIn("main", /^Standard|^How much/)] },
  // Build
  { name: "build-repository", route: "build", steps: [click(/repository/i)] },
  { name: "build-mode", route: "build", steps: [click(/Run within limits|Plan|Suggest changes/)] },
  { name: "build-more", route: "build", steps: [clickIn("main", /^More|•••|Build actions/)] },
  { name: "build-files", route: "build", steps: [click("Files")] },
  { name: "build-background", route: "build", steps: [click("Background work")] },
  { name: "build-terminal", route: "build", steps: [click("Terminal")] },
  { name: "build-model-picker", route: "build", steps: [click(/^Model for this turn/)] },
  // Design
  { name: "design-tools-menu", route: "design", steps: [clickIn("form", "Tools")] },
  { name: "design-add-menu", route: "design", steps: [click("Add to this turn")] },
  { name: "design-documents", route: "design?view=documents", steps: [] },
  // Work
  { name: "tasks-schedule-menu", route: "work?tab=tasks", steps: [clickIn("main", /^Runs now/)] },
  { name: "tasks-details", route: "work?tab=tasks", steps: [clickIn("main", /^Runs now/), click(/Title, priority/)] },
  { name: "tasks-history", route: "work?tab=tasks", steps: [clickIn("main", /^History/)] },
  { name: "goals-new", route: "work?tab=goals", steps: [click("New goal")] },
  { name: "projects-name", route: "work?tab=projects", steps: [click(/Name your first project|Create project/)] },
  { name: "projects-attach", route: "work?tab=projects", steps: [click(/Attach existing folder/)] },
  { name: "threads-filters", route: "work?tab=threads", steps: [] },
  // Models
  { name: "models-add-source", route: "models", steps: [click("Add model")] },
  { name: "models-add-local", route: "models?tab=add&source=local", steps: [] },
  { name: "models-add-account", route: "models?tab=add&source=account", steps: [] },
  { name: "models-add-huggingface", route: "models?tab=add&source=huggingface", steps: [] },
  { name: "models-add-custom", route: "models?tab=add&source=custom", steps: [] },
  { name: "models-anthropic-connect", route: "models?tab=add&source=account", steps: [
    async (page) => page.locator("article", { hasText: "OpenAI" }).getByRole("button", { name: "Connect", exact: true }).first().click({ timeout: 8_000 }),
  ] },
  { name: "models-card-overflow", route: "models?tab=add&source=account", steps: [click(/^More actions for Anthropic/)] },
  { name: "models-details", route: "models", steps: [click(/Details and connection/)] },
  { name: "models-configure-provider", route: "models", steps: [click(/Configure provider/)] },
  { name: "models-choose-default", route: "models", steps: [click(/^Choose a model$/)] },
  { name: "models-change-default", route: "models", steps: [click(/^Change$/)] },
  { name: "models-default-models", route: "models", steps: [click(/Default models/)] },
  { name: "models-usage", route: "models", steps: [click(/Usage and spending/)] },
  { name: "models-compare", route: "models", steps: [click("Compare")] },
  // Memory
  { name: "memory-advanced", route: "memory?tab=controls", steps: [click(/Advanced memory management/)] },
  { name: "memory-add-files", route: "memory?tab=sources", steps: [click(/Add files/)] },
  { name: "memory-map-settings", route: "memory?tab=map", steps: [clickIn("main", /settings|Map settings|Display/i)] },
  { name: "memory-map-add", route: "memory?tab=map", steps: [click(/Add source/)] },
  // Connections
  { name: "connections-add", route: "connections?tab=services", steps: [click(/Add connection/)] },
  { name: "connections-vault", route: "connections?tab=services", steps: [clickIn("main", /^Set up$/)] },
  { name: "connections-add-channel", route: "connections?tab=channels", steps: [click("Add channel")] },
  { name: "connections-delivery", route: "connections?tab=channels", steps: [click(/Delivery environment/)] },
  { name: "connections-mcp-example", route: "connections?tab=advanced&kind=mcp", steps: [click(/Developer example/)] },
  { name: "connections-skills", route: "connections?tab=advanced&kind=skills", steps: [] },
  { name: "connections-hooks", route: "connections?tab=advanced&kind=hooks", steps: [] },
  { name: "connections-plugins", route: "connections?tab=advanced&kind=plugins", steps: [] },
  // Permissions
  { name: "permissions-change", route: "capabilities", steps: [clickIn("main", /^Change$/)] },
  { name: "permissions-turn-on-build", route: "capabilities", steps: [click(/What this turns on/)] },
  { name: "permissions-files", route: "capabilities", steps: [click(/Files and code/)] },
  { name: "permissions-advanced", route: "capabilities", steps: [click(/^Advanced/)] },
  // Approvals
  { name: "approvals-history", route: "approvals", steps: [click("History", "tab")] },
  // Diagnostics
  { name: "diagnostics-technical", route: "diagnostics?tab=overview", steps: [click(/Technical details/)] },
  { name: "diagnostics-working", route: "diagnostics?tab=overview", steps: [click(/What is working/)] },
  { name: "diagnostics-share", route: "diagnostics?tab=overview", steps: [click(/Share or export/)] },
  { name: "diagnostics-health", route: "diagnostics?tab=overview", steps: [click(/Health, in detail/)] },
  { name: "diagnostics-audit-filters", route: "diagnostics?tab=activity", steps: [click(/Filters and export/)] },
  { name: "diagnostics-workstations", route: "diagnostics?tab=work", steps: [click("Workstations")] },
  // Settings
  { name: "settings-password", route: "settings?tab=security", steps: [clickIn("main", /^Change$/)] },
  { name: "settings-two-step", route: "settings?tab=security", steps: [clickIn("main", /^Turn on$/)] },
  { name: "settings-devices", route: "settings?tab=security", steps: [clickIn("main", /^Manage$/)] },
  { name: "settings-remote", route: "settings?tab=security", steps: [clickIn("main", /^Set up$/)] },
  { name: "settings-connection-details", route: "settings?tab=security", steps: [clickIn("main", /^Details$/)] },
  { name: "settings-scan", route: "settings?tab=security", steps: [clickIn("main", /^Review$/)] },
  { name: "settings-standing-grants", route: "settings?tab=security", steps: [
    async (page) => page.locator("main").getByRole("button", { name: /^Manage$/ }).last().click({ timeout: 8_000 }),
  ] },
  { name: "settings-delete-account", route: "settings?tab=account", steps: [click(/Delete my account/)] },
  { name: "settings-support", route: "settings?tab=account", steps: [click(/Support details/)] },
  { name: "settings-backup-holds", route: "settings?tab=backups", steps: [click(/What a backup holds/)] },
  { name: "settings-feedback-form", route: "settings?tab=general", steps: [click(/What the form includes/)] },
  { name: "settings-layout-type", route: "settings?tab=personalisation", steps: [click(/Layout & type/)] },
  { name: "settings-change-history", route: "settings?tab=advanced", steps: [click(/View change history/)] },
  { name: "settings-add-profile", route: "settings?tab=advanced", steps: [click(/Add execution profile/)] },
  { name: "settings-disable-runtime", route: "settings?tab=advanced", steps: [click(/Disable agent runtime/)] },
  { name: "settings-runtime-details", route: "settings?tab=advanced", steps: [clickIn("main", /^Details$/)] },
  { name: "settings-memory-engine", route: "settings?tab=advanced&kind=memory-engine", steps: [] },
  { name: "settings-model-serving", route: "settings?tab=advanced&kind=models", steps: [] },
  { name: "settings-usage", route: "settings?tab=advanced&kind=usage", steps: [] },
  { name: "settings-execution-create", route: "settings?tab=execution-profiles", steps: [click(/Create Balanced/)] },
  { name: "settings-privacy-kept", route: "settings?tab=privacy", steps: [click(/What is kept, and what is not/)] },
  { name: "settings-web-flag", route: "settings?tab=web-access", steps: [click(/Set outside this app/)] },
  { name: "settings-voice-lite", route: "settings?tab=voice", steps: [click(/^Lite/)] },
  { name: "settings-notification-test", route: "settings?tab=notification", steps: [] },
  // Last, because it reopens the setup wizard for the whole workspace; the
  // next entry skips it again so a later run starts clean.
  { name: "settings-setup-again", route: "settings?tab=general", steps: [click(/Run setup again/)] },
  { name: "setup-skipped", route: "home", steps: [
    async (page) => {
      const skip = page.getByRole("button", { name: "Skip setup" });
      if (await skip.isVisible().catch(() => false)) await skip.click();
    },
  ] },
];

test("open and capture every pop-up surface", async ({ page }) => {
  test.setTimeout(1_800_000);
  mkdirSync(DIR, { recursive: true });
  await page.setViewportSize({ width: WIDTH, height: HEIGHT });
  await page.emulateMedia({ colorScheme: THEME });
  await signInAsOwner(page, BASE);
  const results: { name: string; opened: boolean; reason?: string }[] = [];
  for (const surface of SURFACES) {
    if (ONLY && !ONLY.test(surface.name)) continue;
    try {
      // Start each surface from a fresh document: an open dialog can rewrite
      // the address to the route the next surface asks for, and a hash change
      // to the same address is no navigation at all.
      await page.goto("about:blank");
      await page.goto(`${BASE}/#/${surface.route}`);
      await expect(page.locator("main#main")).toBeVisible({ timeout: 20_000 });
      await page.waitForLoadState("networkidle").catch(() => {});
      await page.waitForTimeout(900);
      for (const step of surface.steps) {
        await step(page);
        await page.waitForTimeout(500);
      }
      await page.waitForTimeout(400);
      await page.screenshot({ path: `${DIR}/${surface.name}.png` });
      results.push({ name: surface.name, opened: true });
    } catch (error) {
      results.push({ name: surface.name, opened: false, reason: String(error).split("\n").filter((line) => /intercepts|Timeout|resolved/.test(line)).join(" | ").slice(0, 400) });
    }
    await page.keyboard.press("Escape").catch(() => {});
  }
  writeFileSync(`${DIR}/opened.json`, JSON.stringify(results, null, 2));
  const opened = results.filter((entry) => entry.opened).length;
  expect(opened).toBeGreaterThanOrEqual(Number(process.env.SWEEP_MIN ?? 1));
});

test("capture every destination and sub-page, full length", async ({ page }) => {
  test.skip(process.env.SWEEP_PAGES !== "1", "set SWEEP_PAGES=1");
  test.setTimeout(1_800_000);
  const dir = `${DIR}/pages`;
  mkdirSync(dir, { recursive: true });
  await page.setViewportSize({ width: WIDTH, height: HEIGHT });
  await page.emulateMedia({ colorScheme: THEME });
  await signInAsOwner(page, BASE);
  for (const { route, name } of VISUAL_DESTINATIONS) {
    if (ONLY && !ONLY.test(name)) continue;
    await page.goto(`${BASE}/#/${route}`);
    await expect(page.locator("main#main")).toBeVisible({ timeout: 20_000 });
    await page.waitForLoadState("networkidle").catch(() => {});
    await page.waitForTimeout(1200);
    await page.screenshot({ path: `${dir}/${name}.png`, fullPage: true });
  }
});
