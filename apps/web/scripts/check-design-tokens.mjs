#!/usr/bin/env node
/**
 * The rule `app.css` has always stated, now enforced.
 *
 * Its header says: "Components use tokens only — never raw colours — so both
 * themes stay in lockstep." Nothing checked it, and by the time anyone counted,
 * 183 distinct raw colours were living in 20 components. What that produces is
 * not one ugly page; it is a product that is *almost* uniform, which is the
 * thing you notice without being able to point at it.
 *
 * Two checks, because the audit that found the 183 found a second, quieter
 * problem underneath them.
 *
 * 1. RAW COLOUR IN A COMPONENT STYLE BLOCK.
 *    A literal cannot follow a theme. The worst case found was a whole view
 *    that hard-coded a dark palette, hard-coded a light one over it, then
 *    patched a tokenised dark theme back on top — twice.
 *
 * 2. A `var()` POINTING AT A TOKEN THAT DOES NOT EXIST.
 *    This is the quiet one. CSS fails silently: an undefined custom property
 *    with no fallback makes the whole declaration invalid, so `border-radius`
 *    becomes 0 and a colour just inherits. Ten of these were live — cards with
 *    square corners next to cards with round ones, an error message rendering
 *    in body grey. None of it is visible in review; all of it is visible as
 *    "this doesn't look quite right".
 *
 * Exemptions are listed here with a reason each, never inline, so that adding
 * one is a visible decision rather than a comment somebody skims past.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const SRC = join(ROOT, "src");
const APP_CSS = join(SRC, "app.css");

/**
 * Files allowed to carry raw colour, and why. Both are cases where the colour
 * is not chrome: it is the content.
 */
const RAW_COLOUR_ALLOWED = new Map([
  [
    "src/lib/views/WorkInActionView.svelte",
    "A CSS illustration — a lamp, a desk, a face. Illustration paint is artwork, not surface, and has no theme to follow.",
  ],
  [
    "src/lib/components/TabStrip.svelte",
    "`mask-image` gradients, where #000 and transparent are the mask's alpha channel rather than a visible colour.",
  ],
  [
    "src/lib/views/LoginView.svelte",
    "`filter: drop-shadow()` on the sign-in artwork; the elevation ramp is a box-shadow scale and does not apply to a filter.",
  ],
]);

/** Custom properties that are legitimately set from markup via `style="--x: …"`. */
const SET_FROM_MARKUP = new Set([
  "--sz",
  "--depth",
  "--logo-size",
  "--link-width",
  "--content-h",
  "--explorer-w",
]);

const COLOUR = /#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(/;

function walk(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    if (entry === "node_modules") continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, out);
    else if (entry.endsWith(".svelte")) out.push(full);
  }
  return out;
}

/** The lines of a component's `<style>` block, with their 1-based numbers. */
function styleLines(text) {
  const lines = text.split("\n");
  const out = [];
  let inside = false;
  for (let i = 0; i < lines.length; i += 1) {
    if (/<style\b/.test(lines[i])) { inside = true; continue; }
    if (/<\/style>/.test(lines[i])) { inside = false; continue; }
    if (inside) out.push([i + 1, lines[i]]);
  }
  return out;
}

const files = walk(SRC);
const appCss = readFileSync(APP_CSS, "utf8");

// Every token the product defines: app.css plus anything a component sets itself.
const defined = new Set();
for (const source of [appCss, ...files.map((f) => readFileSync(f, "utf8"))]) {
  for (const m of source.matchAll(/(--[a-z0-9-]+)\s*:/gi)) defined.add(m[1]);
}
for (const t of SET_FROM_MARKUP) defined.add(t);

const failures = [];

for (const file of files) {
  const rel = relative(ROOT, file).replaceAll("\\", "/");
  const text = readFileSync(file, "utf8");
  const allowed = RAW_COLOUR_ALLOWED.has(rel);

  for (const [line, content] of styleLines(text)) {
    if (!allowed && COLOUR.test(content)) {
      const found = content.match(COLOUR)[0];
      failures.push(
        `${rel}:${line}  raw colour \`${found}\` in a style block.\n` +
          `    Use a token from app.css. If this genuinely is not chrome, add the file to\n` +
          `    RAW_COLOUR_ALLOWED in scripts/check-design-tokens.mjs with a reason.`,
      );
    }
    for (const m of content.matchAll(/var\(\s*(--[a-z0-9-]+)/gi)) {
      if (!defined.has(m[1])) {
        failures.push(
          `${rel}:${line}  \`var(${m[1]})\` names a token nothing defines.\n` +
            `    CSS fails silently here: the declaration is dropped, so this renders as nothing.`,
        );
      }
    }
  }
}

if (failures.length > 0) {
  console.error(`\ndesign tokens: ${failures.length} problem(s)\n`);
  for (const f of failures) console.error(`  ${f}\n`);
  process.exit(1);
}
console.log(`design tokens: ${files.length} components clean`);
