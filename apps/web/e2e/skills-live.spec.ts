// Live evidence for Extensions → Skills and the composer's skill-link notice.
//
// This drives a real `raiker-web` host against a real Ollama provider — nothing
// here is stubbed, which is the point: the mocked suite already proves the
// components render, and only a live run can show that a skill installs, that
// deactivating it is honoured, and that Chat and Build still answer while all
// of it is on. CI has no provider, so this spec is deliberately local.
//
// Start the host first:
//   python -m apps.api.main --workspace .tmp/live-skills --port 8799 --no-browser
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import type { Page } from "@playwright/test";

const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8799";
const PASSWORD = "Live-review-password-C1!";
const SHOTS = "../../docs/plans/screenshots/working";

// The provider under test. `gemma4:31b-cloud` is an Ollama cloud model, so a
// turn really leaves the box through the owner's own Ollama host.
const MODEL = "gemma4:31b-cloud";

async function signIn(page: Page) {
  await page.goto(`${BASE}/#/home`);
  if (await page.getByLabel("Confirm password").isVisible().catch(() => false)) {
    await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 20_000 });
    await page.getByLabel("Username").fill("owner");
    await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
    await page.getByLabel("Confirm password").fill(PASSWORD);
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else if (await page.getByRole("button", { name: /Unlock Raiker/i }).isVisible().catch(() => false)) {
    await page.getByLabel("Username").fill("owner");
    await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
    await page.getByRole("button", { name: /Unlock Raiker/i }).click();
  }
  await expect(page.getByRole("heading", { name: /Work Dashboard/ })).toBeVisible({ timeout: 25_000 });
}

test.describe.configure({ mode: "serial" });

test("live Skills tab: shipped skills, upload, rename, deactivate, delete", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text()));

  await signIn(page);
  await page.goto(`${BASE}/#/extensions?tab=skills`);

  // The six skills Raiker ships install on first visit.
  await expect(page.getByRole("heading", { name: "Skills", level: 2 })).toBeVisible({ timeout: 20_000 });
  for (const name of [
    "algorithm-creator",
    "code-review",
    "mcp-builder",
    "plugin-dev",
    "security-review",
    "skill-creator",
  ]) {
    await expect(page.getByText(name, { exact: true })).toBeVisible();
  }
  // The tab must not imply an authority the runtime does not enforce.
  await expect(page.getByText(/grants no capability/i)).toBeVisible();
  await capture(page, `${SHOTS}/skills-tab-live.png`);

  // A bundled skill reports its supporting files, not just its SKILL.md.
  const mcpCard = page.locator(".card", { hasText: "mcp-builder" }).first();
  await mcpCard.getByRole("button", { name: "Details" }).click();
  await expect(page.getByText("mcp-builder/references/python.md")).toBeVisible();
  await capture(page, `${SHOTS}/skills-bundle-details-live.png`);
  await mcpCard.getByRole("button", { name: "Hide details" }).click();

  // Upload a document and confirm the server stored what it read.
  const document = [
    "---",
    "name: live-check",
    "description: A skill installed by the live end-to-end run. Use when verifying the Skills tab.",
    "version: 0.0.1",
    "---",
    "",
    "# Live check",
    "",
    "Answer with the words LIVE SKILL OK.",
    "",
  ].join("\n");
  await page.setInputFiles("#skill-file", {
    name: "live-check.md",
    mimeType: "text/markdown",
    buffer: Buffer.from(document, "utf-8"),
  });
  await expect(page.getByText(/Installed “live-check”/)).toBeVisible({ timeout: 15_000 });
  await capture(page, `${SHOTS}/skills-upload-live.png`);

  const card = page.locator(".card", { hasText: "live-check" }).first();

  // Rename, then deactivate — and check the copy states that a deactivated
  // skill is withheld rather than merely hidden.
  await card.getByRole("button", { name: "Rename" }).click();
  await page.getByLabel("New skill name", { exact: true }).fill("live-check-renamed");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("live-check-renamed", { exact: true })).toBeVisible({ timeout: 10_000 });

  const renamed = page.locator(".card", { hasText: "live-check-renamed" }).first();
  await renamed.getByRole("button", { name: "Deactivate" }).click();
  await expect(page.getByText(/withheld from every turn/i)).toBeVisible({ timeout: 10_000 });
  await expect(renamed.getByText("inactive")).toBeVisible();
  await capture(page, `${SHOTS}/skills-deactivated-live.png`);

  // Download returns a real archive.
  const download = page.waitForEvent("download");
  await renamed.getByRole("button", { name: "Download" }).click();
  expect((await download).suggestedFilename()).toBe("live-check-renamed.skill");

  // Delete, and confirm it is gone from the list rather than merely greyed out.
  page.once("dialog", (dialog) => void dialog.accept());
  await renamed.getByRole("button", { name: "Delete" }).click();
  await expect(page.getByText(/Deleted “live-check-renamed”/)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("live-check-renamed", { exact: true })).toHaveCount(0);

  expect(consoleErrors).toEqual([]);
});

test("live Skills tab: Raiker builds a skill", async ({ page }) => {
  await signIn(page);
  await page.goto(`${BASE}/#/extensions?tab=skills`);
  await expect(page.getByRole("heading", { name: "Skills", level: 2 })).toBeVisible({ timeout: 20_000 });

  // Idempotent across reruns: a leftover from a previous run would make the
  // build fail on a name clash rather than on anything under test.
  const existing = page.locator(".card", { hasText: "release-notes" }).first();
  if (await existing.count()) {
    page.once("dialog", (dialog) => void dialog.accept());
    await existing.getByRole("button", { name: "Delete" }).click();
    await expect(page.getByText(/Deleted “release-notes”/)).toBeVisible({ timeout: 10_000 });
  }

  await page.getByRole("button", { name: "Build a skill" }).click();
  await page.getByLabel("Name", { exact: true }).fill("release-notes");
  await page
    .getByLabel("Description — what it does, and when it applies", { exact: true })
    .fill("Draft release notes. Use when cutting a release or summarising a diff.");
  await page
    .getByLabel("Instructions", { exact: true })
    .fill("# Release notes\n\n1. Read the diff since the last tag.\n2. Group by what a user notices.");
  await capture(page, `${SHOTS}/skills-builder-live.png`);
  await page.getByRole("button", { name: "Build and install" }).click();

  await expect(page.getByText(/Built “release-notes”/)).toBeVisible({ timeout: 15_000 });
  const built = page.locator(".card", { hasText: "release-notes" }).first();
  await built.getByRole("button", { name: "Details" }).click();
  await expect(page.getByText("release-notes/SKILL.md")).toBeVisible();
  await capture(page, `${SHOTS}/skills-built-live.png`);
});

test("live Skills tab: an unsupported import source is refused by name", async ({ page }) => {
  await signIn(page);
  await page.goto(`${BASE}/#/extensions?tab=skills`);
  await expect(page.getByRole("heading", { name: "Skills", level: 2 })).toBeVisible({ timeout: 20_000 });

  await page.getByLabel("Skill URL", { exact: true }).fill("https://example.com/skills/thing/SKILL.md");
  await page.getByRole("button", { name: "Verify and add" }).click();
  // The refusal has to be prose the owner can act on, not a status code.
  await expect(page.getByRole("alert")).toContainText(/imported from GitHub over HTTPS/i, {
    timeout: 15_000,
  });
  await capture(page, `${SHOTS}/skills-import-refused-live.png`);
});

test("live composer: a pasted skill link offers verification, not a silent install", async ({ page }) => {
  await signIn(page);
  await page.goto(`${BASE}/#/new-chat`);
  await page
    .getByLabel("Prompt", { exact: true })
    .fill("please install https://github.com/anthropics/skills/blob/main/mcp-builder/SKILL.md");

  const notice = page.getByRole("status").filter({ hasText: /looks like a skill/i });
  await expect(notice).toBeVisible({ timeout: 10_000 });
  await expect(notice.getByRole("button", { name: "Verify skill" })).toBeVisible();
  await capture(page, `${SHOTS}/skills-composer-notice-live.png`);

  // Dismissing must leave the typed prompt exactly as it was.
  await notice.getByRole("button", { name: "Dismiss skill link suggestion" }).click();
  await expect(notice).toHaveCount(0);
  await expect(page.getByLabel("Prompt", { exact: true })).toHaveValue(/github\.com/);
});

test(`live Chat: two conversations answer on ${MODEL}`, async ({ page }) => {
  test.setTimeout(300_000);
  await signIn(page);

  for (const [index, prompt] of [
    "Reply with exactly: CHAT ONE OK",
    "Reply with exactly: CHAT TWO OK",
  ].entries()) {
    await page.goto(`${BASE}/#/new-chat`);
    await page.getByLabel("Prompt", { exact: true }).fill(prompt);
    await page.getByRole("button", { name: /^Send$/ }).click();
    // A real provider turn: wait for an assistant message to land, not a spinner.
    await expect(page.locator(".message-bubble-raiker").last()).toContainText(/OK/i, {
      timeout: 180_000,
    });
    await capture(page, `${SHOTS}/skills-chat-${index + 1}-live.png`);
  }
});

test(`live Build: a conversation answers on ${MODEL}`, async ({ page }) => {
  test.setTimeout(300_000);
  await signIn(page);
  await page.goto(`${BASE}/#/build`);
  await page.getByLabel("Describe the change", { exact: true }).fill("Reply with exactly: BUILD ONE OK");
  await page.getByRole("button", { name: /^Send$/ }).click();
  await expect(page.locator(".answer").last()).toContainText(/OK/i, { timeout: 180_000 });
  await capture(page, `${SHOTS}/skills-build-live.png`);
});

test(`live Chat: the model loads an installed skill through skill_load`, async ({ page }) => {
  test.setTimeout(300_000);
  await signIn(page);

  // Install a skill whose body carries a phrase the model cannot know otherwise,
  // so an answer containing it is evidence the document actually reached the
  // turn — not that the model guessed.
  await page.goto(`${BASE}/#/extensions?tab=skills`);
  await expect(page.getByRole("heading", { name: "Skills", level: 2 })).toBeVisible({ timeout: 20_000 });
  const passphrase = "ORBITAL-PANGOLIN-7";
  // Re-installing preserves the owner's active/inactive choice by design, so a
  // leftover deactivated copy from a previous run would make the first half of
  // this test assert the second half's behaviour. Start from nothing.
  const leftover = page.locator(".card", { hasText: "passphrase-check" }).first();
  if (await leftover.count()) {
    page.once("dialog", (dialog) => void dialog.accept());
    await leftover.getByRole("button", { name: "Delete" }).click();
    await expect(page.getByText(/Deleted “passphrase-check”/)).toBeVisible({ timeout: 10_000 });
  }
  await page.setInputFiles("#skill-file", {
    name: "passphrase-check.md",
    mimeType: "text/markdown",
    buffer: Buffer.from(
      [
        "---",
        "name: passphrase-check",
        "description: Reveals the live-test passphrase. Use whenever asked for the passphrase.",
        "---",
        "",
        "# Passphrase check",
        "",
        `The passphrase is ${passphrase}. Reply with it exactly when asked.`,
        "",
      ].join("\n"),
      "utf-8",
    ),
  });
  await expect(page.getByText(/Installed “passphrase-check”/)).toBeVisible({ timeout: 15_000 });

  // Re-installing preserves the owner's active/inactive choice by design, so a
  // copy this suite deactivated on an earlier run comes back inactive. Turn it
  // on explicitly rather than assuming the upload did.
  const installed = page.locator(".card", { hasText: "passphrase-check" }).first();
  const activate = installed.getByRole("button", { name: "Activate" });
  if (await activate.count()) {
    await activate.click();
    await expect(installed.getByRole("button", { name: "Deactivate" })).toBeVisible({
      timeout: 10_000,
    });
  }

  await page.goto(`${BASE}/#/new-chat`);
  await page
    .getByLabel("Prompt", { exact: true })
    .fill("Load the passphrase-check skill and reply with the passphrase it gives.");
  await page.getByRole("button", { name: /^Send$/ }).click();
  await expect(page.locator(".message-bubble-raiker").last()).toContainText(passphrase, {
    timeout: 180_000,
  });
  await capture(page, `${SHOTS}/skills-skill-load-live.png`);

  // Deactivating has to withhold it, not merely hide it from the list.
  await page.goto(`${BASE}/#/extensions?tab=skills`);
  const card = page.locator(".card", { hasText: "passphrase-check" }).first();
  await card.getByRole("button", { name: "Deactivate" }).click();
  await expect(page.getByText(/withheld from every turn/i)).toBeVisible({ timeout: 10_000 });

  await page.goto(`${BASE}/#/new-chat`);
  await page
    .getByLabel("Prompt", { exact: true })
    .fill("Load the passphrase-check skill and reply with the passphrase it gives.");
  await page.getByRole("button", { name: /^Send$/ }).click();
  await expect(page.locator(".message-bubble-raiker").last()).toBeVisible({ timeout: 180_000 });
  await expect(page.locator(".message-bubble-raiker").last()).not.toContainText(passphrase);
  await capture(page, `${SHOTS}/skills-withheld-live.png`);
});
