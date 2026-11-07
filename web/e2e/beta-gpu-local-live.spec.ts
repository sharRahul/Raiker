/**
 * Beta release plan, owner-machine GPU round (MD-1, MD-2, MD-3), 2026-11-07.
 *
 * Run on the owner's Windows 11 machine with an NVIDIA GeForce RTX 4080 SUPER
 * (16 GB), against a host on RAIKER_LIVE_BASE. Needs the network: the engine
 * comes from ggml-org/llama.cpp on GitHub and the model from Hugging Face.
 *
 * RT-GPU-01  Raiker installs the CUDA llama.cpp build it recommends for this GPU
 * RT-GPU-02  A GGUF downloaded from Hugging Face is verified, served on the GPU,
 *            chosen in Chat and answers
 */
import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";

import { capture } from "./capture";
import { settled } from "./destinations";
import { chooseModelForTurn, signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE, sendTurn } from "./live";

const OUT = join(import.meta.dirname, "..", "..", "output", "playwright", "2026-11-07-gpu-round");
const LIBRARY = join(OUT, "library");

test.describe.configure({ mode: "serial" });

async function open(page: Page, route: string): Promise<void> {
  await page.goto(`${BASE}/#/${route}`);
  await settled(page);
}

test.beforeEach(async ({ page }) => {
  page.setDefaultTimeout(30_000);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await signInAsOwner(page, BASE);
});

test("RT-GPU-01 — Raiker installs the CUDA llama.cpp build it recommends for this GPU", async ({ page }) => {
  test.setTimeout(900_000);
  await open(page, "settings?tab=advanced&kind=models");
  const engine = page.getByRole("region", { name: "llama.cpp engine" });
  const hardware = engine.getByLabel("This computer");
  await expect(hardware).toContainText(/Graphics\s*NVIDIA GeForce RTX 4080/);
  await expect(hardware).toContainText(/Best engine\s*NVIDIA CUDA/);
  const managed = engine.locator('[data-engine-state="managed"]');
  if (!(await managed.isVisible())) {
    await engine.getByLabel("Engine build").selectOption("cuda");
    await engine.getByRole("button", { name: /Install llama.cpp|Reinstall/ }).click();
    await expect(managed).toBeVisible({ timeout: 840_000 });
  }
  await expect(managed).toContainText("NVIDIA CUDA");
  await capture(page, join(OUT, "01-engine-cuda.png"), engine);
});

function gpuProcesses(): string {
  return execFileSync("nvidia-smi", ["--query-compute-apps=process_name,used_memory", "--format=csv,noheader"], {
    encoding: "utf8",
  });
}

test("RT-GPU-02 — a Hugging Face GGUF is verified, served on the GPU, and answers in Chat", async ({ page }) => {
  test.setTimeout(900_000);
  mkdirSync(LIBRARY, { recursive: true });

  // 1. Approve the folder the download may write to.
  await open(page, "settings?tab=advanced&kind=models&modelsPanel=library");
  const folder = page.getByLabel("Absolute model folder");
  if (!(await page.getByText(LIBRARY, { exact: false }).first().isVisible().catch(() => false))) {
    await folder.fill(LIBRARY);
    await page.getByRole("button", { name: "Add and scan" }).click();
    await expect(page.getByText(LIBRARY, { exact: false }).first()).toBeVisible();
  }

  // 2. Find, pin and download a real instruct GGUF. The download is checked
  //    against the hub's LFS SHA-256 before it is indexed (FIXED-1313).
  await open(page, "models?tab=huggingface");
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("searchbox").or(dialog.getByRole("textbox").first()).first().fill("Qwen2.5-0.5B-Instruct-GGUF");
  await page.keyboard.press("Enter");
  await dialog.getByText("Qwen/Qwen2.5-0.5B-Instruct-GGUF", { exact: true }).first().click();
  await dialog.getByRole("button", { name: /Q4_K_M/ }).first().click({ timeout: 60_000 });
  await expect(dialog.getByText(/Pinned to [0-9a-f]{12}/)).toBeVisible();
  await capture(page, join(OUT, "02-download-review.png"));
  await dialog.getByRole("button", { name: "Confirm download" }).click();
  await expect(page.getByText("GGUF downloaded and indexed in your local library.")).toBeVisible({ timeout: 600_000 });
  await page.keyboard.press("Escape");

  // 3. Serve it in the first GGUF slot on the managed CUDA engine.
  await open(page, "settings?tab=advanced&kind=models");
  const gguf = page.getByRole("group", { name: "GGUF" });
  const slot = gguf.getByLabel("GGUF model 1");
  await expect(slot.locator("option", { hasText: /qwen2\.5-0\.5b-instruct/i })).toHaveCount(1, { timeout: 60_000 });
  await slot.selectOption({ label: (await slot.locator("option", { hasText: /qwen2\.5-0\.5b-instruct/i }).textContent())! });
  await gguf.getByRole("button", { name: /^Serve selected/ }).click();
  await expect(page.getByText(/queued\. Track startup in Activity\./)).toBeVisible();
  await expect.poll(() => gpuProcesses(), { timeout: 240_000, intervals: [3_000] }).toMatch(/llama-server/i);
  const onGpu = gpuProcesses();
  // A served model is not ready until its readiness check passes: the
  // composer refuses to send to a model nothing has checked.
  await expect(async () => {
    await gguf.getByRole("button", { name: "Test" }).click();
    await expect(gguf.getByRole("button", { name: "Test" })).toBeEnabled({ timeout: 120_000 });
    await expect(gguf).not.toContainText(/not reachable|could not/i, { timeout: 5_000 });
  }).toPass({ timeout: 300_000, intervals: [5_000] });
  await capture(page, join(OUT, "03-serving.png"), gguf);

  // 4. Choose it for one Chat turn and get a real answer from the GPU.
  await open(page, "new-chat");
  // The composer names a served GGUF by its runtime ("Local GGUF").
  await chooseModelForTurn(page, /Local GGUF/);
  await sendTurn(page, "What is the capital of France? Answer in one word.");
  // The evidence is the completed turn and its receipt, not the wording: a
  // 0.5B model's answer quality is not what this round measures. Before the
  // 2026-11-07 context fix this turn (9,459 tokens) was refused with HTTP 400.
  await expect(page.locator("summary", { hasText: "Local GGUF · no charge · nothing left this computer" }).last()).toBeVisible({ timeout: 180_000 });
  await expect(page.getByText(/Not done/)).toHaveCount(0);
  await capture(page, join(OUT, "04-chat-answer.png"));
  await test.info().attach("nvidia-smi.txt", { body: onGpu, contentType: "text/plain" });
});
