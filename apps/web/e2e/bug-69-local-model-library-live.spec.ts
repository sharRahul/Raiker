import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { join } from "node:path";
import { mkdirSync, writeFileSync } from "node:fs";

const BASE = "http://127.0.0.1:8765";
const PASSWORD = "Bug-69-live-review-password-1!";
const ROOT = join(
  import.meta.dirname,
  "..",
  "..",
  "..",
  "output",
  "playwright",
  "bug69-model-library",
);
const SHOT = join(
  import.meta.dirname,
  "..",
  "..",
  "..",
  "output",
  "playwright",
  "bug69-local-library-live.png",
);

function ggufString(value: string) {
  const text = Buffer.from(value);
  const length = Buffer.alloc(8);
  length.writeBigUInt64LE(BigInt(text.length));
  return Buffer.concat([length, text]);
}

test("BUG-69 approved local root detects a GGUF without a system-wide scan", async ({
  page,
}) => {
  test.setTimeout(90_000);
  mkdirSync(ROOT, { recursive: true });
  const fixed = Buffer.alloc(20);
  fixed.writeUInt32LE(3, 0);
  fixed.writeBigUInt64LE(0n, 4);
  fixed.writeBigUInt64LE(2n, 12);
  const stringType = Buffer.alloc(4);
  stringType.writeUInt32LE(8);
  writeFileSync(
    join(ROOT, "raiker-live.Q4_K_M.gguf"),
    Buffer.concat([
      Buffer.from("GGUF"),
      fixed,
      ggufString("general.name"),
      stringType,
      ggufString("Raiker Live GGUF"),
      ggufString("general.architecture"),
      stringType,
      ggufString("llama"),
    ]),
  );
  await page.goto(`${BASE}/#/models?tab=local`);
  if (await page.getByRole("button", { name: /Unlock Raiker/i }).isVisible()) {
    await page.getByLabel("Username").fill("owner");
    await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
    await page.getByRole("button", { name: /Unlock Raiker/i }).click();
    await page.goto(`${BASE}/#/models?tab=local`);
  }
  await page.getByRole("tab", { name: "Local" }).click();
  await page.getByLabel("Absolute model folder").fill(ROOT);
  await page.getByRole("button", { name: "Add and scan" }).click();
  await expect(page.getByText("Raiker Live GGUF")).toBeVisible({
    timeout: 30_000,
  });
  await expect(
    page.getByText(/will not search the rest of your computer/i),
  ).toHaveCount(0);
  await expect(page.getByText("llama · Q4_K_M")).toBeVisible();
  await capture(page, SHOT);
});
