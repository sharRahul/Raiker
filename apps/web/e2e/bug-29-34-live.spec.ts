import { expect, test } from "@playwright/test";
import { join } from "node:path";
import { hostedProviderCard } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
const PASSWORD = "Bug-review-password-C1!";
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const OPENROUTER_KEY = process.env.RAIKER_LIVE_OPENROUTER_KEY ?? "";

test.describe.configure({ mode: "serial" });

test("BUG-29 through BUG-34 live product review", async ({ page, request }) => {
  test.setTimeout(480_000);
  expect(ANTHROPIC_KEY).not.toBe("");
  expect(OPENROUTER_KEY).not.toBe("");

  await page.goto(`${BASE}/#/models`);
  await expect(page.getByText(/Verifying runtime/)).toBeHidden({ timeout: 20_000 });
  if (await page.getByLabel("Confirm password").isVisible()) {
    await page.getByLabel("Username").fill("owner");
    await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
    await page.getByLabel("Confirm password").fill(PASSWORD);
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else if (await page.getByRole("button", { name: /Unlock Raiker/i }).isVisible()) {
    await page.getByLabel("Username").fill("owner");
    await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
    await page.getByRole("button", { name: /Unlock Raiker/i }).click();
  }
  await expect(page.getByRole("heading", { name: "Models", level: 1 })).toBeVisible({ timeout: 20_000 });

  for (const [provider, label, key] of [
    ["Anthropic", "Anthropic API key", ANTHROPIC_KEY],
    ["OpenRouter", "OpenRouter API key", OPENROUTER_KEY],
  ] as const) {
    const card = await hostedProviderCard(page, BASE, provider);
    await card.getByRole("button", { name: /^(Connect|Reconnect)$/ }).click();
    await page.getByLabel(label).fill(key);
    await page.locator(".signin-connect").click();
    await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 20_000 });
  }

  const ollama = page.locator(".local-row").filter({ hasText: "Ollama" });
  if (!(await ollama.getByText("selected", { exact: true }).isVisible())) {
    await ollama.getByRole("button", { name: /Choose model/ }).click();
    const available = ollama.getByLabel("Available models");
    await expect(available).toBeVisible({ timeout: 30_000 });
    await available.selectOption("gemma4:31b-cloud");
    await ollama.getByRole("button", { name: "Use model" }).click();
  }
  await expect(ollama.getByText(/Gemma 4:31B Cloud/)).toBeVisible({ timeout: 20_000 });

  await ollama.getByRole("button", { name: "Details" }).click();
  await expect(page.getByText("Context capacity")).toBeVisible();
  await page.screenshot({ path: join(SHOTS, "173-BUG-33-capacity-admin-live.png"), fullPage: true });
  await page.getByRole("button", { name: "Close model details" }).click();

  await page.goto(`${BASE}/#/settings`);
  await page.getByRole("button", { name: "Runtime configuration" }).click();
  await page.getByText("Add SSH or Daytona profile").click();
  await page.getByLabel("Display name").fill("Review build host");
  await page.getByRole("textbox", { name: "Host", exact: true }).fill("build.example.com");
  await page.getByLabel("Remote user").fill("raiker");
  await page.getByLabel("Credential environment variable").fill("RAIKER_REVIEW_SSH_KEY");
  await page.getByRole("button", { name: "Save environment" }).click();
  await expect(page.getByText(/SSH environment saved/)).toBeVisible();
  await page.screenshot({ path: join(SHOTS, "174-BUG-31-execution-environments-live.png"), fullPage: true });

  await page.goto(`${BASE}/#/brain`);
  await page.getByRole("button", { name: "Add workspace source" }).click();
  await page.getByLabel("Workspace-relative path").fill(".");
  await page.getByRole("button", { name: "Review indexing plan" }).click();
  await expect(page.getByRole("heading", { name: "Indexing plan" })).toBeVisible({ timeout: 20_000 });
  await page.screenshot({ path: join(SHOTS, "175-BUG-30-source-review-live.png"), fullPage: true });
  await page.getByRole("button", { name: "Add reviewed source" }).click();
  await page.getByRole("button", { name: "Graph settings" }).click();
  await page.getByLabel("Graph settings").getByText("Always alive").click();
  await page.reload();
  await page.getByLabel("Username").fill("owner");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: /Unlock Raiker/i }).click();
  await expect(page.getByRole("application", { name: /knowledge graph/i })).toBeVisible({ timeout: 20_000 });

  const attachment = {
    name: "governance-note.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("Governed memory and execution review."),
  };
  await page.goto(`${BASE}/#/new-chat`);
  await page.getByRole("button", { name: "Add attachment" }).click();
  await page.getByLabel("Upload document").setInputFiles(attachment);
  await expect(page.locator(".attachment-row > .attachment-card").filter({ hasText: "governance-note.txt" })).toBeVisible({ timeout: 20_000 });
  await page.getByPlaceholder("How can I help you today?").fill("Reply with exactly: CHAT LIVE");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("CHAT LIVE", { exact: true })).toBeVisible({ timeout: 180_000 });
  const chatCard = page.locator(".message-group-user .attachment-card").first();
  await expect(chatCard).toBeVisible();
  expect(await chatCard.evaluate((node) => node.closest(".message-bubble-user"))).toBeNull();
  await page.screenshot({ path: join(SHOTS, "176-chat-attachment-outside-bubble-live.png"), fullPage: true });

  await page.goto(`${BASE}/#/build`);
  await page.getByRole("button", { name: "Add attachment" }).click();
  await page.getByLabel("Upload document").setInputFiles(attachment);
  await expect(page.locator(".attachment-row > .attachment-card").filter({ hasText: "governance-note.txt" })).toBeVisible({ timeout: 20_000 });
  await page.getByLabel("Describe the change").fill("Reply without tools with exactly: BUILD LIVE");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("BUILD LIVE", { exact: true })).toBeVisible({ timeout: 180_000 });
  const buildCard = page.locator(".user-message .attachment-card").first();
  await expect(buildCard).toBeVisible();
  expect(await buildCard.evaluate((node) => node.closest(".message-bubble-user"))).toBeNull();
  await page.screenshot({ path: join(SHOTS, "177-build-attachment-outside-bubble-live.png"), fullPage: true });

  await page.goto(`${BASE}/#/memory`);
  await expect(page.getByRole("heading", { name: "Memory", level: 2 })).toBeVisible();
  await expect(page.getByText("Advanced memory management")).toBeVisible();
  await page.screenshot({ path: join(SHOTS, "178-BUG-29-memory-lifecycle-live.png"), fullPage: true });

  await page.goto(`${BASE}/#/new-chat`);
  await page.getByPlaceholder("How can I help you today?").fill(
    "Use the write_file tool now to create approval-reload-live.txt containing exactly reload approval live.",
  );
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("Waiting for approval", { exact: true })).toBeVisible({ timeout: 180_000 });
  const login = await request.post(`${BASE}/api/auth/login`, { data: { username: "owner", password: PASSWORD } });
  expect(login.ok()).toBeTruthy();
  const token = (await login.json()).token as string;
  const sessionResponse = await request.get(`${BASE}/api/sessions`, { headers: { Authorization: `Bearer ${token}` } });
  expect(sessionResponse.ok()).toBeTruthy();
  const sessions = await sessionResponse.json() as Array<{ session_id: string; title?: string }>;
  const parked = sessions.find((session) => session.title?.includes("Use the write_file tool")) ?? sessions[0];
  expect(parked?.session_id).toBeTruthy();
  await page.goto(`${BASE}/#/new-chat?session=${parked.session_id}`);
  await expect(page.getByText("Waiting for approval", { exact: true })).toBeVisible({ timeout: 20_000 });
  await page.reload();
  await page.getByLabel("Username").fill("owner");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: /Unlock Raiker/i }).click();
  await expect(page.getByText("Waiting for approval", { exact: true })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("link", { name: "Review approval" })).toBeVisible();
  await expect(page.getByText("Loading conversation…")).toBeHidden({ timeout: 20_000 });
  await page.screenshot({ path: join(SHOTS, "179-BUG-34-reloaded-approval-live.png"), fullPage: true });
});
