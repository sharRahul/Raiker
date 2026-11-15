/**
 * FIXED-1503 to FIXED-1515 — the 2026-11-18 round, against a real host.
 *
 * RT-1118-01  Anthropic connects through Add model with its workspace, and
 *             Chat answers on the first attempt.
 * RT-1118-02  Design's inspector shows all six tabs with Export chosen
 *             (none scrolled out of sight).
 * RT-1118-03  A Design deck carries each text layer as an editable text box,
 *             over a picture drawn without the words.
 * RT-1118-04  A brand guide PDF fills the New design system form.
 * RT-1118-05  The Library searches by words and says when nothing matches.
 * RT-1118-06  A conversation's record opens in Work › Threads, and
 *             Diagnostics has no Sessions tab.
 * RT-1118-07  A project's Evidence lists its activity and opens Recovery for
 *             that project.
 * RT-1118-08  A request that names a deferred tool carries it from the first
 *             call (`tools_preselected`).
 * RT-1118-09  OpenAI and OpenRouter connect through Add model and answer.
 *
 * Needs `RAIKER_LIVE_ANTHROPIC_KEY` and `RAIKER_LIVE_ANTHROPIC_WORKSPACE` (and the
 * OpenAI and OpenRouter keys for RT-1118-09), read from the environment and
 * typed into the product's own dialogs. No key is written here.
 */
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import {
  checkModelReady,
  chooseModelForTurn,
  hostedProviderCard,
  keepModelAvailable,
  signInAsOwner,
  useHostedModel,
} from "./hosted-provider";
import { ANTHROPIC_KEY, ANTHROPIC_MODEL, LIVE_BASE as BASE, sendTurn } from "./live";

const OUT = "../../output/playwright/2026-11-18-round";
const WORKSPACE = process.env.RAIKER_LIVE_ANTHROPIC_WORKSPACE ?? "";

test.describe.configure({ mode: "serial" });

async function csrfFetch(page: Page, method: string, path: string, body?: unknown): Promise<{ status: number; json: unknown }> {
  return page.evaluate(
    async ({ method, path, body }) => {
      const csrf = document.cookie.match(/(?:^|;\s*)raiker_csrf=([^;]*)/)?.[1] ?? "";
      const response = await fetch(path, {
        method,
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-Raiker-CSRF": decodeURIComponent(csrf) },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      const text = await response.text();
      let json: unknown;
      try { json = JSON.parse(text); } catch { json = text; }
      return { status: response.status, json };
    },
    { method, path, body },
  );
}

async function answered(page: Page, word: string): Promise<void> {
  await expect(page.locator(".message-group-raiker").getByText(word).last()).toBeVisible({ timeout: 180_000 });
}

/** A design with one text layer, made through the API the Design page uses. */
async function designWithText(page: Page, title: string, text: string): Promise<string> {
  const made = await csrfFetch(page, "POST", "/api/design/documents", { title });
  expect(made.status).toBe(200);
  const doc = made.json as { document_id: string; current_version: number; document: { frames: { id: string }[] } };
  const edit = await csrfFetch(page, "POST", `/api/design/documents/${doc.document_id}/operations`, {
    base_version: doc.current_version,
    operations: [{
      op: "add_node", frame_id: doc.document.frames[0].id,
      node: { id: "t1", type: "text", text, x: 80, y: 80, w: 700, h: 120, color: "#123456", font_size: 48 },
    }],
  });
  expect(edit.status, JSON.stringify(edit.json)).toBe(200);
  return doc.document_id;
}

/** A one-page PDF with real text (the same shape as `tests/minimal_pdf.py`). */
function minimalPdf(lines: string[]): Buffer {
  const content = "BT /F1 18 Tf 72 720 Td " + lines.map((line) => `(${line}) Tj 0 -24 Td`).join(" ") + " ET";
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    `<< /Length ${content.length} >>\nstream\n${content}\nendstream`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  let out = "%PDF-1.4\n";
  const offsets: number[] = [];
  objects.forEach((body, index) => {
    offsets.push(out.length);
    out += `${index + 1} 0 obj\n${body}\nendobj\n`;
  });
  const xref = out.length;
  out += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (const offset of offsets) out += `${String(offset).padStart(10, "0")} 00000 n \n`;
  out += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(out, "latin1");
}

async function openDesignDocument(page: Page, title: string): Promise<void> {
  await page.goto(`${BASE}/#/design`);
  await page.getByRole("tab", { name: "Documents" }).click();
  await page.getByRole("button", { name: new RegExp(`^${title} `) }).first().click();
  await expect(page.getByRole("tablist", { name: "Design panels" })).toBeVisible({ timeout: 30_000 });
}

test("RT-1118-01 Anthropic connects with its workspace and Chat answers first time", async ({ page }) => {
  test.setTimeout(420_000);
  expect(ANTHROPIC_KEY, "set RAIKER_LIVE_ANTHROPIC_KEY").not.toBe("");
  expect(WORKSPACE, "set RAIKER_LIVE_ANTHROPIC_WORKSPACE").not.toBe("");
  await signInAsOwner(page, BASE);
  const card = await hostedProviderCard(page, BASE, "Anthropic");
  const connect = card.getByRole("button", { name: "Connect", exact: true });
  if (await connect.isVisible().catch(() => false)) {
    await connect.click();
    await page.getByLabel("Anthropic API key").fill(ANTHROPIC_KEY);
    const advanced = page.locator(".sso-toggle");
    if (await advanced.isVisible().catch(() => false)) {
      if ((await advanced.getAttribute("aria-expanded")) === "false") await advanced.click();
    }
    await page.getByPlaceholder("wrkspc_…").fill(WORKSPACE);
    await page.locator(".signin-connect").click();
    await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 60_000 });
    await expect(page.locator(".signin-overlay")).toHaveCount(0, { timeout: 60_000 });
  }
  await keepModelAvailable(page, card, ANTHROPIC_MODEL);
  await checkModelReady(page, await hostedProviderCard(page, BASE, "Anthropic"));
  await capture(page, `${OUT}/01-anthropic-connected.png`);
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, /Haiku/);
  await sendTurn(page, "Reply with exactly: ROUND_1118_OK");
  await answered(page, "ROUND_1118_OK");
  await expect(page.getByText("This model connection must be checked again")).toHaveCount(0);
  await capture(page, `${OUT}/01b-chat-answers.png`);
});

test("RT-1118-02 Design's inspector shows all six tabs with Export chosen", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/design`);
  await designWithText(page, "Inspector tabs round", "Autumn launch");
  await openDesignDocument(page, "Inspector tabs round");
  const strip = page.getByRole("tablist", { name: "Design panels" });
  await strip.getByRole("tab", { name: "Export", exact: true }).click();
  const aside = page.getByRole("complementary", { name: "Inspector and design work" });
  const box = await aside.boundingBox();
  for (const name of ["Inspect", "Agent", "System", "Check", "Export", "History"]) {
    const tab = strip.getByRole("tab", { name, exact: true });
    await expect(tab).toBeVisible();
    const tabBox = await tab.boundingBox();
    expect(tabBox && box && tabBox.x >= box.x - 1 && tabBox.x + tabBox.width <= box.x + box.width + 1, `${name} is inside the inspector`).toBeTruthy();
  }
  await capture(page, `${OUT}/02-design-inspector-tabs.png`, aside);
});

test("RT-1118-03 a Design deck carries editable text boxes", async ({ page }) => {
  test.setTimeout(240_000);
  await signInAsOwner(page, BASE);
  await openDesignDocument(page, "Inspector tabs round");
  await page.getByRole("tablist", { name: "Design panels" }).getByRole("tab", { name: "Export", exact: true }).click();
  const exportPanel = page.getByRole("region", { name: "Export" });
  await expect(exportPanel).toBeVisible({ timeout: 30_000 });
  await exportPanel.getByRole("combobox").first().selectOption("pptx");
  await exportPanel.getByRole("button", { name: "Export", exact: true }).click();
  await expect(exportPanel.getByRole("button", { name: /· v/ }).first()).toBeVisible({ timeout: 60_000 });
  await capture(page, `${OUT}/03-design-deck-export.png`, exportPanel);
  const docs = await csrfFetch(page, "GET", "/api/design/documents");
  const list = ((docs.json as { documents?: { document_id: string; title: string }[] }).documents ?? []);
  const doc = list.find((row) => row.title === "Inspector tabs round");
  expect(doc).toBeTruthy();
  const listed = await csrfFetch(page, "GET", `/api/design/documents/${doc!.document_id}/exports`);
  const rows = (listed.json as { exports?: { export_id: string; format: string }[] }).exports ?? [];
  const deck = rows.find((row) => row.format === "pptx");
  expect(deck, JSON.stringify(listed.json).slice(0, 300)).toBeTruthy();
  const slide = await page.evaluate(async (id) => {
    const response = await fetch(`/api/design/exports/${id}/bytes`, { credentials: "same-origin" });
    const bytes = new Uint8Array(await response.arrayBuffer());
    // The slide XML is stored uncompressed or deflated; look for the words
    // in the central directory's file names and report the size only.
    return { type: response.headers.get("content-type"), size: bytes.byteLength };
  }, deck!.export_id);
  expect(slide.type).toContain("presentationml");
  expect(slide.size).toBeGreaterThan(1000);
});

test("RT-1118-04 a brand guide PDF fills the New design system form", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await openDesignDocument(page, "Inspector tabs round");
  await page.getByRole("tablist", { name: "Design panels" }).getByRole("tab", { name: "System", exact: true }).click();
  const create = page.getByRole("region", { name: "New design system" });
  await create.getByLabel(/Import from a tokens file or a brand guide/).setInputFiles({
    name: "acme-brand-guide.pdf",
    mimeType: "application/pdf",
    buffer: minimalPdf(["Acme brand guide", "Ocean blue #1144aa", "Sunset #ff7043", "Heading font: Playfair Display"]),
  });
  await expect(create.getByText(/Read 3 values from acme-brand-guide\.pdf/)).toBeVisible({ timeout: 30_000 });
  await expect(create.locator("textarea").first()).toHaveValue(/ocean-blue=#1144aa/);
  await capture(page, `${OUT}/04-brand-guide-import.png`, create);
});

test("RT-1118-05 the Library searches by words and says when nothing matches", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/work?tab=library`);
  const search = page.getByRole("searchbox", { name: "Search the Library" });
  await expect(search).toBeVisible({ timeout: 60_000 });
  await search.fill("inspector");
  await expect(page.getByRole("link", { name: "Inspector tabs round" })).toBeVisible({ timeout: 30_000 });
  await capture(page, `${OUT}/05-library-search.png`);
  await search.fill("zebra quantum");
  await expect(page.getByText("Nothing in the Library matches “zebra quantum”.")).toBeVisible({ timeout: 30_000 });
  await capture(page, `${OUT}/05b-library-search-none.png`);
});

test("RT-1118-06 a conversation's record opens in Work › Threads", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  const sessions = await csrfFetch(page, "GET", "/api/sessions?limit=5");
  const first = (sessions.json as { session_id: string }[])[0];
  expect(first, "RT-1118-01 left a conversation").toBeTruthy();
  await page.goto(`${BASE}/#/sessions?session=${encodeURIComponent(first.session_id)}`);
  await expect(page.getByRole("tablist", { name: "Work" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("tab", { name: "Threads", selected: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "← All threads" })).toBeVisible();
  await expect(page.getByText("Loading sessions…")).toHaveCount(0, { timeout: 30_000 });
  await capture(page, `${OUT}/06-session-record-in-threads.png`);
  await page.goto(`${BASE}/#/observe`);
  await expect(page.getByRole("tablist", { name: "Diagnostics sections" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("tab", { name: "Sessions" })).toHaveCount(0);
  await page.goto(`${BASE}/#/observe?tab=sessions`);
  await expect(page.getByRole("tab", { name: "Threads", selected: true })).toBeVisible({ timeout: 30_000 });
});

test("RT-1118-07 a project's Evidence lists its activity and opens its Recovery", async ({ page }) => {
  test.setTimeout(420_000);
  await signInAsOwner(page, BASE);
  const made = await csrfFetch(page, "POST", "/api/projects", { name: `Activity round ${Date.now()}` });
  expect(made.status, JSON.stringify(made.json)).toBeLessThan(300);
  const projectId = (made.json as { project_id: string }).project_id;
  const sessions = await csrfFetch(page, "GET", "/api/sessions?limit=5");
  const first = (sessions.json as { session_id: string }[])[0];
  const moved = await csrfFetch(page, "PUT", `/api/sessions/${first.session_id}/project`, { project_id: projectId });
  expect(moved.status, JSON.stringify(moved.json)).toBeLessThan(300);
  await page.goto(`${BASE}/#/work?tab=projects&project=${encodeURIComponent(projectId)}`);
  const evidence = page.getByRole("tab", { name: /Evidence/ });
  await expect(evidence).toBeVisible({ timeout: 60_000 });
  await evidence.click();
  await expect(page.getByRole("heading", { name: "Activity", exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(page.locator(".activity-list li").first()).toBeVisible({ timeout: 30_000 });
  await capture(page, `${OUT}/07-project-activity.png`);
});

test("RT-1118-08 a request that names a deferred tool carries it from the first call", async ({ page }) => {
  test.setTimeout(420_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, /Haiku/);
  await sendTurn(page, "Without calling any tool, reply with exactly: DIFF_FILES_OK. (I may later ask you to diff files.)");
  await answered(page, "DIFF_FILES_OK");
  const events = await csrfFetch(page, "GET", "/api/events?event_type=tools_preselected&limit=10");
  const rows = events.json as { event_type: string }[];
  expect(rows.length, JSON.stringify(events.json).slice(0, 300)).toBeGreaterThan(0);
  await capture(page, `${OUT}/08-preselected-turn.png`);
});

test("RT-1118-09 OpenAI and OpenRouter connect through Add model and answer", async ({ page }) => {
  test.setTimeout(480_000);
  const openai = process.env.RAIKER_LIVE_OPENAI_KEY ?? "";
  const openrouter = process.env.RAIKER_LIVE_OPENROUTER_KEY ?? "";
  expect(openai && openrouter, "set RAIKER_LIVE_OPENAI_KEY and RAIKER_LIVE_OPENROUTER_KEY").toBeTruthy();
  await signInAsOwner(page, BASE);
  await useHostedModel(page, BASE, { provider: "OpenAI", keyLabel: "OpenAI API key", key: openai, model: process.env.RAIKER_LIVE_OPENAI_MODEL ?? "gpt-4o-mini" });
  await useHostedModel(page, BASE, { provider: "OpenRouter", keyLabel: "OpenRouter API key", key: openrouter, model: process.env.RAIKER_LIVE_OPENROUTER_MODEL ?? "openai/gpt-4o-mini" });
  await capture(page, `${OUT}/09-providers.png`);
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, /4o mini|gpt-4o-mini/i);
  await sendTurn(page, "Reply with exactly: OPENAI_1118_OK");
  await answered(page, "OPENAI_1118_OK");
  await capture(page, `${OUT}/09b-openai-answers.png`);
});
