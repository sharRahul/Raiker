import { test } from "@playwright/test";
import { capture } from "./capture";
import { join } from "node:path";
import {
  checkModelReady,
  connectHostedProvider,
  hostedProviderCard,
  keepOffered,
  offeredModelIds,
  openModelDialog,
  signInAsOwner,
} from "./hosted-provider";

/**
 * What the **Test** control on a hosted provider card actually does.
 *
 * The card's readiness chip is the gate the composer reads, so "Not checked"
 * surviving a Test is the difference between a product that can send a turn and
 * one that cannot. This spec does not assert an outcome — it records the network
 * the click produces and the chip text over time, so the result is evidence
 * rather than a guess.
 */

const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "output", "playwright");
const KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";

test("Test on a connected provider card resolves the pinned model's readiness", async ({
  page,
}) => {
  test.setTimeout(900_000);
  test.skip(KEY.length === 0, "no Anthropic key supplied");

  const calls: string[] = [];
  page.on("request", (r) => {
    if (r.url().includes("/api/")) calls.push(`→ ${r.method()} ${r.url().replace(BASE, "")}`);
  });
  page.on("response", (r) => {
    if (r.url().includes("/api/")) calls.push(`← ${r.status()} ${r.url().replace(BASE, "")}`);
  });

  // BUG-248 — the shared sign-in rather than a copy of it.
  await signInAsOwner(page, BASE);

  // The Models redesign removed the Hosted tab this spec waited for; the
  // provider cards live under Add now, and the shared helpers know where.
  const unconnected = await (await hostedProviderCard(page, BASE, "Anthropic"))
    .getByRole("button", { name: "Connect", exact: true })
    .isVisible()
    .catch(() => false);
  const card = unconnected
    ? await connectHostedProvider(page, BASE, "Anthropic", "Anthropic API key", KEY)
    : await hostedProviderCard(page, BASE, "Anthropic");

  const dialog = await openModelDialog(page, card);
  const values = await offeredModelIds(dialog);
  console.log("CATALOGUE:", JSON.stringify(values));
  const model = values.includes("claude-haiku-4-5-20251001")
    ? "claude-haiku-4-5-20251001"
    : values.find((v) => v.length > 0)!;
  await keepOffered(dialog, model);
  console.log("PINNED:", model);

  const pinned = await hostedProviderCard(page, BASE, "Anthropic");
  console.log("BEFORE TEST:", (await pinned.innerText()).replace(/\s+/g, " "));
  calls.length = 0;
  // **Test** has to settle on an outcome for the pinned model — not stay at
  // "Not checked" — which is what this probe exists to show.
  await checkModelReady(page, pinned);
  console.log("AFTER TEST:", (await pinned.innerText()).replace(/\s+/g, " "));
  console.log("NETWORK DURING TEST:\n" + calls.join("\n"));
  await capture(page, join(SHOTS, "review-readiness-probe.png"));
});
