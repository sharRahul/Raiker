/** Real Notes host and files; no mocked API responses. */
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const SHOTS = join(import.meta.dirname, "..", "..", "output", "playwright", "notes");
async function api(page: Page, method: string, path: string, body?: unknown) {
  return page.evaluate(async ({ method, path, body }) => {
    const csrf = document.cookie.match(/(?:^|; )raiker_csrf=([^;]+)/)?.[1];
    const response = await fetch(path, { method, headers: {
      "Content-Type": "application/json", ...(csrf ? { "X-Raiker-CSRF": decodeURIComponent(csrf) } : {}),
    }, body: body === undefined ? undefined : JSON.stringify(body) });
    if (!response.ok) throw new Error(`${method} ${path}: ${response.status}`);
    return response.json();
  }, { method, path, body });
}

test("RT-NOTES-01 — linked notebook, conflict recovery and folder control", async ({ page }) => {
  test.setTimeout(180_000); page.setDefaultTimeout(30_000);
  const errors: string[] = []; page.on("pageerror", (e) => errors.push(e.message));
  await page.emulateMedia({ reducedMotion: "reduce" });
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/notes`);
  await expect(page.getByRole("heading", { name: "Notes", exact: true })).toBeVisible();
  const initial = await api(page, "GET", "/api/notes");
  expect(initial.root.replaceAll("\\", "/")).toMatch(/\/Notes$/);

  await page.getByRole("button", { name: "New note", exact: true }).click();
  await page.getByRole("textbox", { name: "New note name" }).fill("Beta");
  await page.getByRole("textbox", { name: "New note name" }).press("Enter");
  await expect(page.getByRole("textbox", { name: "Note text" })).toBeVisible();
  await page.getByRole("textbox", { name: "Note text" }).fill("# Beta\n\nA linked idea. #idea");
  await page.getByRole("textbox", { name: "Note text" }).press("Control+s");
  await expect(page.getByRole("status").filter({ hasText: "Saved" })).toBeVisible();

  await page.getByRole("button", { name: "New note", exact: true }).click();
  await page.getByRole("textbox", { name: "New note name" }).fill("Alpha");
  await page.getByRole("textbox", { name: "New note name" }).press("Enter");
  const editor = page.getByRole("textbox", { name: "Note text" });
  await expect(editor).toHaveValue(/# Alpha/);
  await editor.fill("---\nstatus: draft\n---\n# Alpha\n\nSee [[Beta]]. #idea\n\n- [ ] Review linked notes\n");
  await editor.press("Control+s");
  await expect(page.getByRole("status").filter({ hasText: "Saved" })).toBeVisible();
  await page.getByRole("button", { name: "Read", exact: true }).click();
  await expect(page.getByRole("definition")).toContainText("draft");
  await page.getByRole("article").getByRole("link", { name: "Beta", exact: true }).click();
  await expect(page.getByRole("button", { name: "Beta", exact: true })).toBeVisible();
  await expect(page.getByRole("article").getByRole("link", { name: "#idea", exact: true })).toHaveAttribute("href", "#/notes?search=tag%3Aidea");
  await expect(page.getByRole("heading", { name: /Linked mentions 1/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Local graph", exact: true })).toBeVisible();
  await capture(page, join(SHOTS, "notes-linked.png"));
  await page.getByRole("button", { name: "Beta", exact: true }).click();
  await page.getByRole("textbox", { name: "New name", exact: true }).fill("Linked idea");
  await page.getByRole("button", { name: "Rename", exact: true }).click();
  await expect(page.getByRole("button", { name: "Linked idea", exact: true })).toBeVisible();
  const alpha = await api(page, "GET", "/api/notes/note?path=Alpha.md");
  expect(alpha.content).toContain("[[Linked idea]]");

  await page.goto(`${BASE}/#/notes?note=Alpha.md`);
  await expect(page.getByRole("button", { name: "Alpha", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Edit", exact: true }).click();
  await editor.fill("My unsaved version");
  const other = await api(page, "PUT", "/api/notes/note", { path: alpha.path, content: "# Alpha\n\nChanged in another tool.", expected_mtime: alpha.mtime });
  await editor.press("Control+s");
  await expect(page.getByRole("alert")).toContainText("changed somewhere else");
  await page.getByRole("complementary", { name: "Notes", exact: true }).getByRole("link", { name: "Linked idea", exact: true }).click();
  await expect(editor).toHaveValue("My unsaved version");
  await expect(page).toHaveURL(/note=Alpha.md/);
  await page.getByRole("button", { name: "Use the newer version", exact: true }).click();
  await expect(editor).toHaveValue(other.content);
  await expect(page.getByRole("heading", { name: "Local graph", exact: true })).toBeHidden();
  await page.getByRole("button", { name: "Read", exact: true }).click();
  await page.getByRole("searchbox", { name: "Search notes" }).fill("tag:idea");
  await page.getByRole("searchbox", { name: "Search notes" }).press("Enter");
  await expect(page.getByText("1 result", { exact: true })).toBeVisible();

  for (const theme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: theme });
    await page.evaluate((value) => document.documentElement.setAttribute("data-theme", value), theme);
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      const toggle = page.getByRole("banner").getByRole("button", { name: /navigation/ });
      await expect(toggle).toHaveAttribute("aria-label", width === 390 ? /^(Open|Close) navigation$/ : /^(Collapse|Expand) navigation$/);
      const close = page.getByRole("button", { name: "Close navigation", exact: true });
      if (await close.isVisible()) await close.click();
      await expect(page.locator(".drawer-scrim")).toBeHidden();
      await page.waitForFunction(() => document.getAnimations().every((a) => a.playState !== "running"));
      expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(0);
      await capture(page, join(SHOTS, `notes-${theme}-${width}.png`));
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`${BASE}/#/notes`);
  await page.getByRole("button", { name: "Today", exact: true }).click();
  await expect(page).toHaveURL(/note=Daily/);
  await page.getByRole("button", { name: "Move to trash", exact: true }).click();
  const listed = await api(page, "GET", "/api/notes");
  expect(listed.notes.some((n: { path: string }) => n.path.startsWith("Daily/"))).toBe(false);
  await page.goto(`${BASE}/#/memory?tab=controls`);
  await expect(page.getByRole("heading", { name: "Notes folder", exact: true })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Notes folder", exact: true })).toBeVisible();
  await capture(page, join(SHOTS, "notes-folder.png"));
  expect(errors).toEqual([]);
});
