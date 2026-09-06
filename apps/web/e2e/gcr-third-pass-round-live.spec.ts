/**
 * The 2026-09-05 third-pass round, driven against a real host.
 *
 * Ten findings of
 * `docs/plans/GENERIC_STATIC_CODE_REVIEW_THIRD_PASS_2026-09-05.md` closed in one
 * change, and three of them have a surface an owner touches. This spec is the
 * evidence for those three, taken the way an owner would take it:
 *
 * * **FIXED-420 (the P0).** A failed conversion's cleanup names the exact files
 *   that conversion created, and never the model-library folder they were
 *   written into — which is where every earlier conversion that *succeeded*
 *   also lives. The unrelated model beside the wreckage is still there
 *   afterwards.
 * * **FIXED-422.** Retry is offered on a terminal job, and the API refuses one
 *   that is not.
 * * **FIXED-427.** The host's background passes are reported on Observability
 *   instead of failing in silence.
 *
 * The provider key is entered through the Connect dialog, as a person would.
 * Whatever the provider says about it is recorded rather than assumed: this
 * spec is about Raiker's own surfaces, and it does not need a turn to prove
 * any of them.
 */
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { connectHostedProvider, signInAsOwner } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
/** A folder on this machine that plays the part of the owner's model library. */
const LIBRARY = process.env.RAIKER_LIVE_LIBRARY ?? "/tmp/raiker-live-models";
const REVISION = "d".repeat(40);

/** Seed the library the way an owner's would look: one model that worked. */
function seedLibrary(): { converted: string; earlier: string; source: string } {
  const converted = join(LIBRARY, "converted");
  const source = join(LIBRARY, "snapshot");
  mkdirSync(converted, { recursive: true });
  mkdirSync(source, { recursive: true });
  writeFileSync(
    join(source, "config.json"),
    JSON.stringify({ architectures: ["LlamaForCausalLM"] }),
  );
  writeFileSync(join(source, "model.safetensors"), "safetensors bytes");
  const earlier = join(converted, "gemma-2b.Q4_K_M.gguf");
  writeFileSync(earlier, "an earlier conversion that worked");
  return { converted, earlier, source };
}

test.describe("third-pass round", () => {
  test.describe.configure({ mode: "serial" });

  test("the Anthropic key is entered through the UI and answered in words", async ({
    page,
  }) => {
    test.setTimeout(240_000);
    await signInAsOwner(page, BASE);
    test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");

    const card = await connectHostedProvider(page, BASE, "Anthropic", "Anthropic API key", KEY);
    await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 60_000 });
    await card.getByRole("button", { name: "Test", exact: true }).click();
    // The closed set of outcomes `checkModelReady` uses, plus this round's own
    // reason. What matters is that it is a *sentence*, never a bare status:
    // FIXED-388 found "check your network" being said about a provider that had
    // answered in full.
    await expect(
      card.getByText(
        /can reach|cannot execute|not reachable|rejected|no credit|no quota|needs a workspace|identity-linked/i,
      ),
    ).toBeVisible({ timeout: 120_000 });
    await expect(card.getByText(/http_\d{3}/)).toHaveCount(0);
    await capture(page, "../../docs/plans/screenshots/working/gcr-round-anthropic-connection.png");
  });

  test("a failed conversion's cleanup names its own files, not the library", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    const { converted, earlier, source } = seedLibrary();
    await signInAsOwner(page, BASE);

    // Approve the library root, the way the Local library tab does.
    await page.goto(`${BASE}/#/models?tab=local`);
    const path = page.getByLabel("Absolute model folder");
    await expect(path).toBeVisible({ timeout: 60_000 });
    await path.fill(LIBRARY);
    await page.getByRole("button", { name: "Add and scan" }).click();
    await expect(page.locator("code", { hasText: LIBRARY }).first()).toBeVisible({
      timeout: 60_000,
    });

    // Start a conversion. There is no container runtime on this host, so it
    // fails — which is exactly the state the finding is about.
    const started = await page.evaluate(
      async ([output, src, revision]) => {
        const csrf = document.cookie
          .split("; ")
          .find((part) => part.startsWith("raiker_csrf="))
          ?.slice("raiker_csrf=".length);
        const response = await fetch("/api/model-conversion", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(csrf ? { "X-Raiker-CSRF": decodeURIComponent(csrf) } : {}),
          },
          body: JSON.stringify({
            source: src,
            output,
            revision,
            quantization: "Q4_K_M",
            confirmed: true,
          }),
        });
        return { status: response.status, body: await response.json() };
      },
      [converted, source, REVISION] as const,
    );
    expect(started.status, JSON.stringify(started.body)).toBe(200);

    // The half-written intermediate a failed conversion leaves behind, in the
    // shared output folder beside the model that succeeded.
    const intermediate = join(converted, `snapshot-${REVISION.slice(0, 12)}.bf16.gguf`);
    writeFileSync(intermediate, "half a conversion");

    await page.goto(`${BASE}/#/models?tab=activity`);
    const job = page.locator("article").filter({ hasText: "convert" }).first();
    await expect(job).toBeVisible({ timeout: 60_000 });
    await expect(job.getByText("failed").first()).toBeVisible({ timeout: 60_000 });
    // FIXED-422 — Retry is offered on a terminal, reconstructable job.
    await expect(job.getByRole("button", { name: "Retry" })).toBeVisible();

    await job.getByRole("button", { name: "Delete partial files" }).click();
    const confirm = page.getByRole("alertdialog", {
      name: "Delete the files this job left behind?",
    });
    await expect(confirm).toBeVisible({ timeout: 30_000 });
    // The whole finding, on one screen: the exact artifact, and not the folder.
    await expect(confirm.getByText(intermediate)).toBeVisible();
    await expect(confirm.getByText(earlier)).toHaveCount(0);
    await expect(confirm.getByText(/only what this job created/i)).toBeVisible();
    await capture(
      page,
      "../../docs/plans/screenshots/working/gcr-19-cleanup-names-its-own-artifacts.png",
      confirm,
    );

    await confirm.getByRole("button", { name: "Delete files" }).click();
    await expect(confirm).toBeHidden({ timeout: 60_000 });
    // Deleted what it named, and nothing beside it.
    await expect
      .poll(() => existsSync(intermediate), { timeout: 30_000 })
      .toBe(false);
    expect(existsSync(earlier)).toBe(true);
    expect(existsSync(converted)).toBe(true);
  });

  test("Retry is refused on a job that has not finished", async ({ page }) => {
    test.setTimeout(180_000);
    await signInAsOwner(page, BASE);
    // FIXED-422 — the API half. A queued or running job is not retried; it is
    // already running, and a second worker over the same destination is the
    // defect. Driven through the page's own session rather than a raw client.
    const outcome = await page.evaluate(async () => {
      const csrf = document.cookie
        .split("; ")
        .find((part) => part.startsWith("raiker_csrf="))
        ?.slice("raiker_csrf=".length);
      const headers = {
        "Content-Type": "application/json",
        ...(csrf ? { "X-Raiker-CSRF": decodeURIComponent(csrf) } : {}),
      };
      const started = await fetch("/api/model-operations", {
        method: "POST",
        headers,
        body: JSON.stringify({ kind: "pull", target: "tiny", confirmed: true }),
      });
      const operation = await started.json();
      const retried = await fetch(
        `/api/model-operations/${operation.operation_id}/retry`,
        { method: "POST", headers, body: "{}" },
      );
      return { status: retried.status, body: await retried.json() };
    });
    expect(outcome.status).toBe(422);
    expect(JSON.stringify(outcome.body)).toContain("operation_not_retryable");
  });

  test("the host's background passes are reported, not merely survived", async ({
    page,
  }) => {
    test.setTimeout(180_000);
    await signInAsOwner(page, BASE);
    await page.goto(`${BASE}/#/observe`);
    const card = page.locator("section").filter({ hasText: "Background passes" }).first();
    await expect(card).toBeVisible({ timeout: 60_000 });
    // The tick runs every fifteen seconds, so a host that has been up for one
    // has recorded its passes. FIXED-427: a pass that is fine is one line.
    await expect(card.getByText(/scheduled tasks/i)).toBeVisible({ timeout: 90_000 });
    await expect(card.getByText("ok").first()).toBeVisible({ timeout: 90_000 });
    await capture(
      page,
      "../../docs/plans/screenshots/working/gcr-38-background-passes.png",
      card,
    );
  });
});
