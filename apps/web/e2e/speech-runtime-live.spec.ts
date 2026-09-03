/**
 * BUG-256 — dictation that runs entirely on this machine, proved end to end.
 *
 * The browser records with a fake capture device, the clip is converted in the
 * page and posted to Raiker, Raiker forwards it to a transcription server on
 * loopback, and the words come back into the composer. Nothing in that path
 * leaves the machine, which is the property the control now claims.
 */
import { createServer, type Server } from "node:http";
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { dismissFirstRunModelSetup, signInAsOwner } from "./hosted-provider";

const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";
const SHOTS = "../../docs/plans/screenshots/working";
const TRANSCRIPT = "dictated entirely on this machine";

// A fake capture device, so the microphone opens without a person at the
// keyboard. The audio it produces is a tone; what is being proved here is the
// path, and the transcript comes from the stand-in runtime below.
test.use({
  launchOptions: {
    args: [
      "--use-fake-device-for-media-stream",
      "--use-fake-ui-for-media-stream",
      ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? [] : []),
    ],
    ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
      : {}),
  },
});

let runtime: Server;
let runtimeUrl = "";
let received = 0;

test.beforeAll(async () => {
  runtime = createServer((request, response) => {
    received += 1;
    const chunks: Buffer[] = [];
    request.on("data", (chunk) => chunks.push(chunk as Buffer));
    request.on("end", () => {
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify({ text: TRANSCRIPT }));
    });
  });
  await new Promise<void>((resolve) => runtime.listen(0, "127.0.0.1", resolve));
  const address = runtime.address();
  runtimeUrl = `http://127.0.0.1:${typeof address === "object" && address ? address.port : 0}`;
});

test.afterAll(async () => {
  await new Promise<void>((resolve) => runtime.close(() => resolve()));
});

test("dictation can be made to run on this machine, and says so", async ({ page }) => {
  test.setTimeout(300_000);
  await signInAsOwner(page, BASE);
  await dismissFirstRunModelSetup(page);

  // ── The runtime is configured where the other local runtimes are ──
  await page.goto(`${BASE}/#/models?tab=local`);
  const speech = page.getByRole("article", { name: "Speech runtime" });
  await expect(speech).toBeVisible({ timeout: 30_000 });
  await expect(speech.getByText("Not set up")).toBeVisible();
  await speech.getByLabel("Speech runtime address").fill(runtimeUrl);
  await speech.getByRole("button", { name: "Save and test" }).click();
  await expect(speech.getByText("Answered. Dictation can run on this device.")).toBeVisible({
    timeout: 60_000,
  });
  await expect(speech.getByText("Configured")).toBeVisible();
  await capture(page, `${SHOTS}/bug-256-speech-runtime-models.png`, speech);

  // ── The choice is the owner's, and Settings says which one is in use ──
  await page.goto(`${BASE}/#/settings?tab=voice`);
  await expect(page.getByRole("heading", { name: "Voice" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Dictation runs on this device.")).toBeVisible();
  await page.getByRole("radio", { name: /^On this device/ }).click();
  await expect(page.getByText("Dictation runs on this device.")).toBeVisible();
  // The address field is disabled while a save is in flight; capture the
  // settled page so the evidence shows the controls as an owner finds them.
  await expect(page.getByRole("button", { name: "Save and test" })).toBeEnabled();
  await capture(page, `${SHOTS}/bug-256-voice-settings.png`);

  // ── The disclosure under the microphone matches that choice ──
  await page.goto(`${BASE}/#/new-chat`);
  const disclosure = page.getByLabel("About dictation privacy").first();
  await expect(disclosure).toBeVisible({ timeout: 30_000 });
  await disclosure.click();
  await expect(
    page.getByText(/transcribed by the speech runtime on this machine/).first(),
  ).toBeVisible();
  await disclosure.click();

  // ── And the words reach the composer ──
  const before = received;
  await page.getByLabel("Dictate").first().click();
  await expect(page.getByText("Listening…")).toBeVisible({ timeout: 30_000 });
  await page.waitForTimeout(1500);
  await page.getByLabel("Done dictating").click();
  await expect(page.getByRole("textbox", { name: /prompt|message/i }).first()).toHaveValue(
    new RegExp(TRANSCRIPT),
    { timeout: 120_000 },
  );
  expect(received).toBeGreaterThan(before);
  await capture(page, `${SHOTS}/bug-256-dictated-on-device.png`);
});
