import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { MORE_AREAS, NAV_ITEMS } from "./nav";
import { SETTINGS_SECTIONS } from "./settingsSections";

const source = (name: string) =>
  readFileSync(resolve(process.cwd(), "src", "lib", "views", name), "utf8");

describe("quiet UI copy", () => {
  it("removes static page ledes and redundant chat menu hints", () => {
    for (const view of [
      "ActivityView.svelte",
      "DesignView.svelte",
      "DiagnosticsView.svelte",
      "ObserveView.svelte",
      "SessionsView.svelte",
      "SkillsView.svelte",
      "WorkInActionView.svelte",
    ]) {
      expect(source(view)).not.toContain('class="page-lead"');
    }
    expect(source("ChatView.svelte")).not.toContain('class="menu-hint"');
  });
});

/*
 * QUI-G02 — words that do not belong in what an owner reads.
 *
 * "User-facing" here means what the markup puts on screen or reads aloud: text
 * between tags, and the aria-label, title, placeholder, label, alt and detail
 * attributes, in every component, plus navigation and Settings labels. Code,
 * comments and styles are not scanned.
 *
 * Travel vocabulary and "Observability" are refused everywhere (README, QUI-L11).
 * "MCP" is the name of a protocol, kept only where MCP servers are added and
 * managed (Connections and its advanced tab). "runtime" is kept in Settings ›
 * Developer & runtime, and in that section's own name where a link points to it.
 */
const SRC = resolve(process.cwd(), "src");

function svelteFiles(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) svelteFiles(path, out);
    else if (name.endsWith(".svelte") && !name.includes(".test.")) out.push(path);
  }
  return out;
}

function shownText(source: string): string[] {
  const markup = source
    .replace(/<script[\s\S]*?<\/script>/g, "")
    .replace(/<style[\s\S]*?<\/style>/g, "")
    .replace(/<!--[\s\S]*?-->/g, "");
  const texts: string[] = [];
  for (const match of markup.matchAll(/>([^<>{}]+)</g)) texts.push(match[1]);
  for (const match of markup.matchAll(/\b(?:aria-label|title|placeholder|label|alt|detail)="([^"{]+)"/g)) texts.push(match[1]);
  return texts.map((text) => text.replace(/\s+/g, " ").trim()).filter((text) => text !== "");
}

const EVERYWHERE = ["Observability", "journey", "destination", "expedition", "waypoint", "trail", "quest", "arrived"];
const MCP_PLACES = ["lib/views/ConnectionsView.svelte", "lib/views/ExtensionsView.svelte", "lib/views/McpView.svelte"];
// The components behind the Developer & runtime sections of SETTINGS_SECTIONS.
const RUNTIME_PLACES = [
  "lib/views/settings/Runtime.svelte",
  "lib/views/settings/WebAccess.svelte",
  "lib/views/settings/GitHubConnection.svelte",
  "lib/views/settings/GitCredential.svelte",
  "lib/views/settings/MemoryEngine.svelte",
  "lib/views/settings/Updates.svelte",
];

function offences(word: string, allowed: readonly string[] = [], except: RegExp | null = null): string[] {
  const pattern = new RegExp(`\\b${word}\\b`, "i");
  const found: string[] = [];
  for (const file of svelteFiles(SRC)) {
    const where = relative(SRC, file).replaceAll("\\", "/");
    if (allowed.includes(where)) continue;
    for (const text of shownText(readFileSync(file, "utf8"))) {
      const checked = except ? text.replace(except, "") : text;
      if (pattern.test(checked)) found.push(`${where}: ${text}`);
    }
  }
  return found;
}

describe("quiet UI word list (QUI-G02)", () => {
  it.each(EVERYWHERE)("never shows %s", (word) => {
    expect(offences(word)).toEqual([]);
  });

  it("names MCP only where MCP servers are managed", () => {
    expect(offences("MCP", MCP_PLACES)).toEqual([]);
  });

  it("says runtime only in Settings › Developer & runtime", () => {
    expect(offences("runtime", RUNTIME_PLACES, /Runtime configuration/g)).toEqual([]);
  });

  it("keeps the words out of navigation and Settings labels", () => {
    const labels = [
      ...NAV_ITEMS.flatMap((item) => [item.label, item.hint ?? ""]),
      ...MORE_AREAS.map((area) => area.label),
      ...SETTINGS_SECTIONS.map((section) => section.label),
    ];
    for (const word of [...EVERYWHERE, "MCP"]) {
      const pattern = new RegExp(`\\b${word}\\b`, "i");
      expect(labels.filter((label) => pattern.test(label)), word).toEqual([]);
    }
  });
});
