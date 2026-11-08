/**
 * VD-2 (beta plan) — the microphone, with Chromium's fake capture device, on a
 * running host. A stand-in transcription server on loopback answers for the
 * speech runtime, so what is proved is the page's own handling of the device:
 *
 * VD2-01  Permission denied: the owner is told how to allow it; the draft stays
 * VD2-02  Cancel: nothing is transcribed or sent; the microphone is released
 * VD2-03  The microphone goes away mid-recording: released, said, draft restored
 * VD2-04  The 6-minute limit: the page stops, says so, and transcribes what it has
 * VD2-05  No source touches the browser's SpeechRecognition (FIXED-1314)
 */
import { createServer, type Server } from "node:http";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";

import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const SHOTS = join(import.meta.dirname, "..", "..", "output", "playwright", "2026-11-08-voice");
const TRANSCRIPT = "words from the fake microphone";

type Probe = { __streams: MediaStream[]; __recogniserTouched?: boolean };

// The fake device only: no fake permission UI, so each test decides whether
// the microphone is allowed (`grantPermissions`) or refused (nothing granted).
// The full Chromium build: the headless shell has no media capture and
// answers every request with NotSupportedError.
test.use({ channel: "chromium", launchOptions: { args: ["--use-fake-device-for-media-stream"] } });
test.describe.configure({ mode: "serial", timeout: 120_000 });

let runtime: Server;
let runtimeUrl = "";
let received = 0;

test.beforeAll(async () => {
  runtime = createServer((request, response) => {
    if (request.url?.includes("transcriptions")) received += 1;
    request.resume();
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

async function chatWithDraft(page: Page, draft: string): Promise<void> {
  await page.goto(`${BASE}/#/new-chat`);
  await page.getByLabel("Prompt", { exact: true }).fill(draft);
}

const prompt = (page: Page) => page.getByLabel("Prompt", { exact: true });
const streamsOpened = (page: Page) =>
  page.waitForFunction(() => (window as unknown as Probe).__streams.length > 0);

test.beforeEach(async ({ page }) => {
  page.setDefaultTimeout(30_000);
  // Keep every stream the page opens reachable, so a test can end its track
  // the way an unplugged device or a revoked permission does.
  await page.addInitScript(() => {
    (window as unknown as Probe).__streams = [];
    const devices = navigator.mediaDevices;
    if (!devices?.getUserMedia) return;
    const original = devices.getUserMedia.bind(devices);
    devices.getUserMedia = async (constraints) => {
      const stream = await original(constraints);
      (window as unknown as Probe).__streams.push(stream);
      return stream;
    };
  });
  await signInAsOwner(page, BASE);
});

test("VD2-00 — the speech runtime is set up on this machine", async ({ page }) => {
  await page.goto(`${BASE}/#/settings?tab=advanced&kind=models`);
  const speech = page.getByRole("article", { name: "Speech engine" });
  await speech.getByLabel("Speech engine address").fill(runtimeUrl);
  await speech.getByRole("button", { name: "Save and test" }).click();
  await expect(speech.getByText("Answered. Dictation can run on this device.")).toBeVisible({ timeout: 60_000 });
});

test("VD2-01 — permission denied keeps the draft and says how to allow it", async ({ page, context }) => {
  await context.clearPermissions();
  await chatWithDraft(page, "my own words");
  await page.getByRole("button", { name: "Dictate", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Allow microphone access for Raiker" })).toBeVisible();
  await expect(prompt(page)).toHaveValue("my own words");
  await capture(page, join(SHOTS, "vd2-01-denied.png"));
});

test("VD2-02 — cancel transcribes and sends nothing, and releases the microphone", async ({ page, context }) => {
  await context.grantPermissions(["microphone"], { origin: BASE });
  const before = received;
  const posts: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && new URL(request.url()).pathname.startsWith("/api/prompts")) {
      posts.push(request.url());
    }
  });
  await chatWithDraft(page, "keep this draft");
  await page.getByRole("button", { name: "Dictate", exact: true }).click();
  await expect(page.getByText("Listening…", { exact: true })).toBeVisible();
  await streamsOpened(page);
  await page.getByRole("button", { name: "Cancel dictation" }).click();
  await expect(prompt(page)).toHaveValue("keep this draft");
  await page.waitForTimeout(1500);
  expect(received).toBe(before);
  expect(posts).toEqual([]);
  const live = await page.evaluate(() =>
    (window as unknown as Probe).__streams
      .flatMap((stream) => stream.getTracks())
      .filter((track) => track.readyState === "live").length,
  );
  expect(live).toBe(0);
});

test("VD2-03 — a microphone lost mid-recording is released and said", async ({ page, context }) => {
  await context.grantPermissions(["microphone"], { origin: BASE });
  const before = received;
  await chatWithDraft(page, "draft before the device went away");
  await page.getByRole("button", { name: "Dictate", exact: true }).click();
  await expect(page.getByText("Listening…", { exact: true })).toBeVisible();
  await streamsOpened(page);
  // What Chromium does when the device is unplugged or the site's permission
  // is revoked: the track stops and fires `ended`.
  await page.evaluate(() => {
    for (const stream of (window as unknown as Probe).__streams) {
      for (const track of stream.getTracks()) {
        track.stop();
        track.dispatchEvent(new Event("ended"));
      }
    }
  });
  await expect(page.getByRole("alert").filter({ hasText: "The microphone stopped while recording" })).toBeVisible();
  await expect(prompt(page)).toHaveValue("draft before the device went away");
  expect(received).toBe(before);
  await capture(page, join(SHOTS, "vd2-03-microphone-lost.png"));
});

test("VD2-04 — the page stops at six minutes, says so, and transcribes what it has", async ({ page, context }) => {
  await context.grantPermissions(["microphone"], { origin: BASE });
  await page.clock.install();
  await chatWithDraft(page, "");
  await page.getByRole("button", { name: "Dictate", exact: true }).click();
  await expect(page.getByText("Listening…", { exact: true })).toBeVisible();
  await streamsOpened(page);
  // Two real seconds of the fake device's tone, so the clip has audio in it.
  await new Promise((resolve) => setTimeout(resolve, 2_000));
  // The installed clock also runs in real time, so leave a margin either side.
  await page.clock.fastForward(5 * 60 * 1000 + 50 * 1000);
  await expect(page.getByText("Stopped at the 6-minute limit")).toHaveCount(0);
  await expect(page.getByText("Listening…", { exact: true })).toBeVisible();
  await page.clock.fastForward(10_000);
  await expect(page.getByRole("status").filter({ hasText: "Stopped at the 6-minute limit" })).toBeVisible();
  await page.clock.resume();
  await expect(prompt(page)).toHaveValue(TRANSCRIPT, { timeout: 30_000 });
  await capture(page, join(SHOTS, "vd2-04-limit.png"));
});

test("VD2-05 — dictation never touches the browser's speech recogniser", async ({ page, context }) => {
  await context.grantPermissions(["microphone"], { origin: BASE });
  await page.addInitScript(() => {
    for (const name of ["SpeechRecognition", "webkitSpeechRecognition"]) {
      Object.defineProperty(window, name, {
        configurable: true,
        get() {
          (window as unknown as Probe).__recogniserTouched = true;
          return undefined;
        },
      });
    }
  });
  await chatWithDraft(page, "");
  await page.getByRole("button", { name: "Dictate", exact: true }).click();
  await expect(page.getByText("Listening…", { exact: true })).toBeVisible();
  await streamsOpened(page);
  await page.waitForTimeout(2_000);
  await page.getByRole("button", { name: "Done dictating" }).click();
  await expect(prompt(page)).toHaveValue(TRANSCRIPT, { timeout: 30_000 });
  expect(await page.evaluate(() => (window as unknown as Probe).__recogniserTouched ?? false)).toBe(false);
});
