/**
 * FIXED-1515 onwards — the 2026-11-19 round, against a real host.
 *
 * RT-1119-01  A persona added in Settings › Personalisation › Personas is
 *             offered first under `@`, sent as a chip, and its answer reads
 *             *Raiker as @Name*; after an edit it says it ran an earlier version.
 * RT-1119-02  A persona whose ceiling leaves out Web: the turn records
 *             `persona_applied` and no web tool ran.
 * RT-1119-03  A local Ollama model answers a Chat turn.
 * RT-1119-04  Work › Threads finds a chat by meaning with the built-in
 *             embedding model (nomic-embed-text on the local Ollama).
 * RT-1119-05  The Library finds a design by meaning.
 * RT-1119-06  A Design deck's shapes and pictures are native slide objects.
 * RT-1119-07  A vector PDF writes Greek and Cyrillic as text.
 * RT-1119-08  A brand guide's swatch-only colours fill the system form.
 * RT-1119-09  Design says what failed when Raiker does not answer.
 * RT-1119-10  OpenAI and OpenRouter connect through Add model and answer.
 *
 * Needs `RAIKER_LIVE_ANTHROPIC_KEY` and `RAIKER_LIVE_ANTHROPIC_WORKSPACE`
 * (connected by the 2026-09-15 spec or RT-1118-01 first), the OpenAI and
 * OpenRouter keys for RT-1119-10, and a local Ollama holding
 * `nomic-embed-text` and `qwen2.5:0.5b`. Keys are read from the environment and
 * typed into the product's own dialogs. No key is written here.
 */
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { chooseModelForTurn, signInAsOwner, useHostedModel } from "./hosted-provider";
import { LIVE_BASE as BASE, sendTurn } from "./live";

const OUT = "../../output/playwright/2026-11-19-round";
const NAME = `Analyst${Date.now().toString().slice(-5)}`;

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

async function addPersona(page: Page, name: string, instructions: string, keep: string[] | null): Promise<void> {
  await page.goto(`${BASE}/#/settings?tab=personalisation`);
  const card = page.getByTestId("personas");
  await expect(card).toBeVisible({ timeout: 60_000 });
  await card.getByRole("button", { name: "Add persona" }).click();
  const dialog = page.getByRole("dialog", { name: "Add persona" });
  await dialog.getByPlaceholder("DataAnalyst").fill(name);
  await dialog.getByPlaceholder("Reads numbers carefully").fill("Leads with the figure");
  await dialog.getByPlaceholder(/Lead with the figures/).fill(instructions);
  if (keep !== null) {
    await dialog.getByLabel("Only some tools").check();
    for (const family of ["Files", "Web", "Messages and calendars", "Memory", "Git and GitHub", "Commands"]) {
      const box = dialog.getByLabel(family, { exact: true });
      if (keep.includes(family)) await box.check();
      else await box.uncheck();
    }
  }
  await dialog.getByRole("button", { name: "Save" }).click();
  await expect(dialog).toBeHidden({ timeout: 30_000 });
  await expect(card.getByText(`@${name}`, { exact: true })).toBeVisible();
}

async function choosePersona(page: Page, name: string): Promise<void> {
  const composer = page.getByRole("group", { name: "Message composer" });
  const box = composer.getByRole("textbox").first();
  await box.click();
  await box.pressSequentially(`@${name.slice(0, 4)}`);
  const menu = page.getByRole("listbox");
  await expect(menu.getByText("Personas", { exact: true }).or(menu.getByRole("option", { name: `@${name}` })).first())
    .toBeVisible({ timeout: 30_000 });
  await menu.getByRole("option", { name: new RegExp(`^@${name}`) }).click();
  await expect(composer.getByLabel("Persona for this message").getByText(`@${name}`)).toBeVisible();
  await expect(box).toHaveValue("");
}

/** A design with layers, made through the API the Design page uses. */
async function design(page: Page, title: string, nodes: Record<string, unknown>[]): Promise<string> {
  const made = await csrfFetch(page, "POST", "/api/design/documents", { title });
  expect(made.status).toBe(200);
  const doc = made.json as { document_id: string; current_version: number; document: { frames: { id: string }[] } };
  const edit = await csrfFetch(page, "POST", `/api/design/documents/${doc.document_id}/operations`, {
    base_version: doc.current_version,
    operations: nodes.map((node) => ({ op: "add_node", frame_id: doc.document.frames[0].id, node })),
  });
  expect(edit.status, JSON.stringify(edit.json)).toBe(200);
  return doc.document_id;
}

async function openDesign(page: Page, title: string): Promise<void> {
  await page.goto(`${BASE}/#/design`);
  await page.getByRole("tab", { name: "Documents" }).click();
  await page.getByRole("button", { name: new RegExp(`^${title} `) }).first().click();
  await expect(page.getByRole("tablist", { name: "Design panels" })).toBeVisible({ timeout: 30_000 });
}

/** A one-page PDF: words, and raw drawing operators painted before them. */
function pdf(lines: string[], drawing = ""): Buffer {
  const content = (drawing ? `${drawing} ` : "") + "BT /F1 18 Tf 72 720 Td " + lines.map((line) => `(${line}) Tj 0 -24 Td`).join(" ") + " ET";
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

test("RT-1119-01 a persona is chosen from @, answers as itself, and says when it changed", async ({ page }) => {
  test.setTimeout(420_000);
  await signInAsOwner(page, BASE);
  await addPersona(page, NAME, "Always end your answer with the word PERSONA_SEEN on its own line.", null);
  await capture(page, `${OUT}/01-personas-settings.png`, page.getByTestId("personas"));
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, /Haiku/);
  await choosePersona(page, NAME);
  await capture(page, `${OUT}/01b-persona-chip.png`, page.getByRole("group", { name: "Message composer" }));
  await sendTurn(page, "Say hello in three words.");
  await answered(page, "PERSONA_SEEN");
  await expect(page.locator(".persona-line").last()).toContainText(`Raiker as @${NAME}`);
  await capture(page, `${OUT}/01c-raiker-as-persona.png`);

  // Edit the persona; the older answer now says it ran an earlier version.
  const url = page.url();
  await page.goto(`${BASE}/#/settings?tab=personalisation`);
  await page.getByRole("button", { name: `Edit @${NAME}` }).click();
  const dialog = page.getByRole("dialog", { name: `Edit @${NAME}` });
  await dialog.getByPlaceholder(/Lead with the figures/).fill("Always end your answer with the word PERSONA_V2.");
  await dialog.getByRole("button", { name: "Save" }).click();
  await expect(dialog).toBeHidden({ timeout: 30_000 });
  await page.goto(url);
  await page.reload();
  await expect(page.locator(".persona-line").last()).toContainText("ran with an earlier version", { timeout: 60_000 });
  await capture(page, `${OUT}/01d-earlier-version.png`);
});

test("RT-1119-02 a persona's ceiling withholds web tools from the turn", async ({ page }) => {
  test.setTimeout(420_000);
  await signInAsOwner(page, BASE);
  const quiet = `Offline${Date.now().toString().slice(-4)}`;
  await addPersona(page, quiet, "Answer from what you already know. Keep it to one sentence.", ["Memory"]);
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, /Haiku/);
  await choosePersona(page, quiet);
  await sendTurn(page, "Search the web for today's weather in Paris, then reply with the word CEILING_DONE.");
  // The turn ends with an answer, not a loop of tool searches (found and fixed
  // this round: `tool_search` offered what the ceiling withholds).
  await expect(page.locator(".message-group-raiker").last().getByRole("button", { name: "Copy response" }))
    .toBeVisible({ timeout: 180_000 });
  await expect(page.locator(".message-group-raiker").last().getByRole("group").filter({ hasText: /Receipt:.*Haiku/ }).first()).toBeVisible();
  const looked = await page.locator(".message-group-raiker").last().getByText(/^Look up a tool/).count();
  expect(looked, "the model searched for a withheld tool at most twice").toBeLessThanOrEqual(2);
  const events = await csrfFetch(page, "GET", "/api/events?event_type=persona_applied&limit=5");
  const applied = (events.json as { summary?: string; turn_id?: string }[]);
  expect(applied.length, JSON.stringify(events.json).slice(0, 300)).toBeGreaterThan(0);
  const turnId = applied[0].turn_id ?? "";
  const detail = await csrfFetch(page, "GET", `/api/turns/${turnId}`);
  const calls = JSON.stringify(detail.json);
  expect(calls).not.toMatch(/"tool_name":\s*"(web_search|web_fetch|weather_lookup)"/);
  await capture(page, `${OUT}/02-ceiling-turn.png`);
});

test("RT-1119-03 a local Ollama model answers a Chat turn", async ({ page }) => {
  test.setTimeout(420_000);
  await signInAsOwner(page, BASE);
  // Models › Add: the local Ollama row, its model chosen through its own dialog.
  await page.goto(`${BASE}/#/models?tab=add`);
  await page.getByRole("button", { name: /^On this computer/ }).click();
  const row = page.locator(".local-row", { has: page.getByRole("heading", { name: "Ollama", exact: true }) });
  await expect(row).toBeVisible({ timeout: 90_000 });
  await row.getByRole("button", { name: /Choose a model|Select models/ }).first().click();
  const picker = page.getByRole("dialog", { name: /Ollama models/ });
  await expect(picker.getByText(/^Loading models from/)).toBeHidden({ timeout: 120_000 });
  const box = picker.locator('input[type="checkbox"][value="qwen2.5:0.5b"]');
  await expect(box).toBeAttached({ timeout: 60_000 });
  if (!(await box.isChecked())) await box.click();
  await expect(box).toBeChecked({ timeout: 30_000 });
  await picker.getByRole("button", { name: "Done" }).click();
  await capture(page, `${OUT}/03-ollama-row.png`, row);
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, /qwen/i);
  await sendTurn(page, "Reply with exactly the word: LOCAL_OK");
  await answered(page, "LOCAL_OK");
  await capture(page, `${OUT}/03-ollama-answers.png`);
});

test("RT-1119-04 Threads finds a chat by meaning with the built-in embedding model", async ({ page }) => {
  test.setTimeout(600_000);
  await signInAsOwner(page, BASE);
  // Semantic recall runs where the Models permission is Always allow; Memory's
  // own index build creates the nomic-embed-text space on the local Ollama.
  const allowed = await csrfFetch(page, "POST", "/api/capability-modes/model_provider_runtime/allow", {
    reason: "Live check of search by meaning with the built-in embedding model",
  });
  expect(allowed.status, JSON.stringify(allowed.json)).toBeLessThan(300);
  const built = await csrfFetch(page, "POST", "/api/memory/embedding-index", { provider: "ollama", model: "nomic-embed-text" });
  test.info().annotations.push({ type: "embedding-index", description: JSON.stringify(built.json).slice(0, 300) });
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, /Haiku/);
  await sendTurn(page, "In one line: cheap flights to Kyoto in April. End with KYOTO_OK.");
  await answered(page, "KYOTO_OK");
  await page.goto(`${BASE}/#/work?tab=threads`);
  const search = page.getByRole("searchbox").first();
  await expect(search).toBeVisible({ timeout: 60_000 });
  await search.fill("Japan holiday");
  await search.press("Enter");
  await expect(page.getByText(/Related by meaning/).first()).toBeVisible({ timeout: 120_000 });
  await capture(page, `${OUT}/04-threads-by-meaning.png`);
});

test("RT-1119-05 the Library finds a design by meaning", async ({ page }) => {
  test.setTimeout(300_000);
  await signInAsOwner(page, BASE);
  await design(page, "Poster for the Kyoto cherry blossom trip", [
    { id: "t", type: "text", text: "Sakura season", x: 60, y: 60, w: 600, h: 80, font_size: 40 },
  ]);
  await page.goto(`${BASE}/#/work?tab=library`);
  const search = page.getByRole("searchbox", { name: "Search the Library" });
  await expect(search).toBeVisible({ timeout: 60_000 });
  await search.fill("Japan holiday");
  await expect(page.getByText(/Related by meaning/).first()).toBeVisible({ timeout: 120_000 });
  await capture(page, `${OUT}/05-library-by-meaning.png`);
});

test("RT-1119-06 a deck's shapes and pictures are native slide objects", async ({ page }) => {
  test.setTimeout(240_000);
  await signInAsOwner(page, BASE);
  await design(page, "Native deck round", [
    { id: "card", type: "rect", x: 40, y: 40, w: 500, h: 260, fill: "#1144aa", radius: 24 },
    { id: "dot", type: "ellipse", x: 600, y: 60, w: 160, h: 160, fill: "#ff7043" },
    { id: "t", type: "text", text: "Quarterly plan", x: 80, y: 120, w: 440, h: 80, font_size: 44, color: "#ffffff" },
  ]);
  await openDesign(page, "Native deck round");
  await page.getByRole("tablist", { name: "Design panels" }).getByRole("tab", { name: "Export", exact: true }).click();
  const exportPanel = page.getByRole("region", { name: "Export" });
  await exportPanel.getByRole("combobox").first().selectOption("pptx");
  await exportPanel.getByRole("button", { name: "Export", exact: true }).click();
  await expect(exportPanel.getByRole("button", { name: /· v/ }).first()).toBeVisible({ timeout: 60_000 });
  await capture(page, `${OUT}/06-native-deck-export.png`, exportPanel);
  const docs = await csrfFetch(page, "GET", "/api/design/documents");
  const doc = ((docs.json as { documents?: { document_id: string; title: string }[] }).documents ?? [])
    .find((row) => row.title === "Native deck round");
  const listed = await csrfFetch(page, "GET", `/api/design/documents/${doc!.document_id}/exports`);
  const deck = ((listed.json as { exports?: { export_id: string; format: string }[] }).exports ?? [])
    .find((row) => row.format === "pptx");
  const names = await page.evaluate(async (id) => {
    const bytes = new Uint8Array(await (await fetch(`/api/design/exports/${id}/bytes`)).arrayBuffer());
    // File names in a zip's central directory are plain bytes.
    return new TextDecoder("latin1").decode(bytes).match(/ppt\/media\/[A-Za-z0-9-]+\.png/g) ?? [];
  }, deck!.export_id);
  expect(names.filter((name) => name.includes("frame")), "no flattened frame picture").toEqual([]);
});

test("RT-1119-07 a vector PDF writes Greek and Cyrillic as text", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  const id = await design(page, "Unicode PDF round", [
    { id: "t", type: "text", text: "Ζωή Привет Łódź", x: 60, y: 60, w: 700, h: 80, font_size: 40 },
  ]);
  const read = await csrfFetch(page, "GET", `/api/design/documents/${id}`);
  const frame = (read.json as { document: { frames: { id: string }[] } }).document.frames[0].id;
  const made = await csrfFetch(page, "POST", `/api/design/documents/${id}/exports`, { frame_id: frame, format: "vector_pdf" });
  expect(made.status, JSON.stringify(made.json)).toBe(200);
  const settings = (made.json as { settings: Record<string, unknown> }).settings;
  expect(settings.text_encoding).toBe("unicode");
  expect(settings.characters_replaced).toBe(0);
  await openDesign(page, "Unicode PDF round");
  await capture(page, `${OUT}/07-unicode-design.png`);
});

test("RT-1119-08 a brand guide's swatch-only colours fill the system form", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await openDesign(page, "Native deck round");
  await page.getByRole("tablist", { name: "Design panels" }).getByRole("tab", { name: "System", exact: true }).click();
  const create = page.getByRole("region", { name: "New design system" });
  const swatches = "0.067 0.267 0.667 rg 72 500 60 60 re f 1 0.44 0.26 rg 200 500 60 60 re f "
    + "BT /F1 12 Tf 72 480 Td (Deep Sea) Tj ET BT /F1 12 Tf 200 480 Td (Coral) Tj ET";
  await create.getByLabel(/Import from a tokens file or a brand guide/).setInputFiles({
    name: "swatch-guide.pdf",
    mimeType: "application/pdf",
    buffer: pdf(["Brand colours"], swatches),
  });
  await expect(create.getByText(/Read 2 values from swatch-guide\.pdf/)).toBeVisible({ timeout: 30_000 });
  await expect(create.locator("textarea").first()).toHaveValue(/deep-sea=#1144aa/);
  await capture(page, `${OUT}/08-brand-guide-swatches.png`, create);
});

test("RT-1119-09 Design says what failed when Raiker does not answer", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/design`);
  await page.getByRole("tab", { name: "Documents" }).click();
  await page.route("**/api/design/documents", async (route) => {
    if (route.request().method() === "POST") await route.abort("connectionrefused");
    else await route.continue();
  });
  await page.getByRole("button", { name: /^Create/ }).first().click();
  await expect(page.getByText(/The design was not created\. Nothing was changed\. Raiker did not answer/))
    .toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("That change was refused.")).toHaveCount(0);
  await capture(page, `${OUT}/09-design-failure-copy.png`);
  await page.unroute("**/api/design/documents");
});

test("RT-1119-10 OpenAI and OpenRouter connect through Add model and answer", async ({ page }) => {
  test.setTimeout(480_000);
  const openai = process.env.RAIKER_LIVE_OPENAI_KEY ?? "";
  const openrouter = process.env.RAIKER_LIVE_OPENROUTER_KEY ?? "";
  expect(openai && openrouter, "set RAIKER_LIVE_OPENAI_KEY and RAIKER_LIVE_OPENROUTER_KEY").toBeTruthy();
  await signInAsOwner(page, BASE);
  await useHostedModel(page, BASE, { provider: "OpenAI", keyLabel: "OpenAI API key", key: openai, model: process.env.RAIKER_LIVE_OPENAI_MODEL ?? "gpt-4o-mini" });
  await useHostedModel(page, BASE, { provider: "OpenRouter", keyLabel: "OpenRouter API key", key: openrouter, model: process.env.RAIKER_LIVE_OPENROUTER_MODEL ?? "openai/gpt-4o-mini" });
  await capture(page, `${OUT}/10-providers.png`);
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, /4o mini|gpt-4o-mini/i);
  await sendTurn(page, "Reply with exactly: OPENAI_1119_OK");
  await answered(page, "OPENAI_1119_OK");
  await capture(page, `${OUT}/10b-openai-answers.png`);
});
