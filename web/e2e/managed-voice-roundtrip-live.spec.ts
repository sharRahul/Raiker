/** VD-1: real managed engines through the product UI on a disposable packaged host. */
import { expect, test } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const microphoneWav = resolve(import.meta.dirname, "../../output/playwright/windows-managed-voice/microphone.wav");
test.use({ channel: "chromium", launchOptions: { args: [
  "--use-fake-device-for-media-stream",
  `--use-file-for-fake-audio-capture=${microphoneWav}%noloop`,
] } });

test("VD-1 packaged Voice installs, speaks, hears, dictates and removes its verified engines", async ({ page, context }) => {
  test.skip(process.env.RAIKER_LIVE_MANAGED_VOICE !== "1", "Requires a packaged Kokoro host and explicit real downloads");
  test.setTimeout(900_000);
  page.setDefaultTimeout(30_000);
  await page.addInitScript(() => {
    const originalUrl = URL.createObjectURL.bind(URL);
    URL.createObjectURL = (blob) => {
      if (blob instanceof Blob && blob.type.startsWith("audio/")) {
        (window as unknown as { voicePreview: Blob }).voicePreview = blob;
      }
      return originalUrl(blob);
    };
    const original = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    (window as unknown as { voiceStreams: MediaStream[] }).voiceStreams = [];
    navigator.mediaDevices.getUserMedia = async (constraints) => {
      const stream = await original(constraints);
      (window as unknown as { voiceStreams: MediaStream[] }).voiceStreams.push(stream);
      return stream;
    };
  });
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=voice`);
  await page.getByRole("radio", { name: /^Lite/ }).check();
  await page.getByRole("combobox", { name: "Run on", exact: true }).selectOption("cpu");
  await page.getByLabel("English only (faster and more accurate for English)").check();
  await page.getByRole("combobox", { name: "Speech recognition", exact: true }).selectOption("whisper-base.en-q5_1");
  await capture(page, "../../output/playwright/windows-managed-voice/01-selected.png");
  const install = page.getByRole("button", { name: "Install", exact: true });
  if (await install.isVisible()) {
    await install.click();
    const outcome = page.getByRole("status").filter({ hasText: /Installed and verified\.|Install failed:/ }).last();
    await expect(outcome).toBeVisible({ timeout: 600_000 });
    await expect(outcome).toContainText("Installed and verified.");
  }
  const response = page.waitForResponse(r => new URL(r.url()).pathname === "/api/voice/test" && r.request().method() === "POST");
  await page.getByRole("button", { name: "Test", exact: true }).click();
  const result = await (await response).json();
  expect(result.spoke).toBe(true);
  expect(result.heard).toBe(true);
  expect(result.word_error_rate).toBeLessThanOrEqual(0.2);
  await expect(page.getByTestId("voice-test-result")).toContainText("Spoke and heard it back");
  await test.info().attach("managed-voice-result.json", { body: JSON.stringify(result), contentType: "application/json" });
  await capture(page, "../../output/playwright/windows-managed-voice/02-roundtrip.png");

  // Obtain the microphone fixture through the shipped Preview control. This
  // uses the real packaged speaker; no transcription response is substituted.
  const spoken = page.waitForResponse(r => new URL(r.url()).pathname === "/api/voice/speak" && r.request().method() === "POST");
  await page.getByRole("button", { name: "Preview this voice", exact: true }).click();
  const audio = await spoken;
  expect(audio.ok()).toBe(true);
  await expect.poll(() => page.evaluate(() => (window as unknown as { voicePreview?: Blob }).voicePreview?.size ?? 0)).toBeGreaterThan(44);
  const wav = await page.evaluate(async () => Array.from(new Uint8Array(await (window as unknown as { voicePreview: Blob }).voicePreview.arrayBuffer())));
  mkdirSync(dirname(microphoneWav), { recursive: true });
  writeFileSync(microphoneWav, Buffer.from(wav));
  await context.grantPermissions(["microphone"], { origin: BASE });
  await page.goto(`${BASE}/#/new-chat`);
  let promptPosts = 0;
  page.on("request", r => {
    if (r.method() === "POST" && new URL(r.url()).pathname.startsWith("/api/prompts")) promptPosts++;
  });
  await page.getByRole("button", { name: "Dictate", exact: true }).click();
  await expect(page.getByText("Listening…", { exact: true })).toBeVisible();
  // Let the known finite speech fixture finish playing into Chromium capture.
  await page.waitForTimeout(6000);
  await page.getByRole("button", { name: "Done dictating", exact: true }).click();
  await expect(page.getByLabel("Prompt", { exact: true })).toHaveValue(/hello.*this is how I sound on this computer/i, { timeout: 90_000 });
  expect(promptPosts).toBe(0);
  expect(await page.evaluate(() =>
    (window as unknown as { voiceStreams: MediaStream[] }).voiceStreams
      .flatMap(s => s.getTracks()).filter(t => t.readyState === "live").length,
  )).toBe(0);
  await capture(page, "../../output/playwright/windows-managed-voice/04-dictated.png");
  await page.goto(`${BASE}/#/settings?tab=voice`);
  await page.getByRole("button", { name: "Remove", exact: true }).click();
  await expect(page.getByText(/Remove every voice file/)).toBeVisible();
  await page.getByRole("button", { name: "Remove", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: /Voice removed/ })).toBeVisible();
  await expect(page.getByText("On disk: 0 B", { exact: false })).toBeVisible();
  await capture(page, "../../output/playwright/windows-managed-voice/03-removed.png");
});
