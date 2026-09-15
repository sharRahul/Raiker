// Which guide section explains which surface.
//
// The map exists so a page's "How this works" link and the guide it points at
// cannot drift apart, and it can drift in exactly one way: a slug that names a
// file the guide does not have. The link then renders, reads as a promise, and
// lands on nothing. So the slugs are checked against the guide directory itself
// rather than against a list somebody has to keep in step with it.
import { readdirSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { guideSectionFor, mappedRoutes } from "./guideSections";
import { NAV_ITEMS } from "./nav";

const GUIDE = resolve(process.cwd(), "..", "docs", "guide");

const slugs = new Set(
  readdirSync(GUIDE)
    .filter((name) => name.endsWith(".md") && name.toLowerCase() !== "readme.md")
    .map((name) => name.slice(0, -3).toLowerCase()),
);

describe("guide section map", () => {
  it("points every mapped route at a section the guide actually ships", () => {
    for (const route of mappedRoutes()) {
      const target = guideSectionFor(route);
      expect(target, route).not.toBeNull();
      expect(slugs, `${route} → ${target!.slug}`).toContain(target!.slug);
    }
  });

  it("gives each route a label that names the topic rather than the page", () => {
    for (const route of mappedRoutes()) {
      const label = guideSectionFor(route)!.label;
      expect(label.length, route).toBeGreaterThan(0);
      // A template produced "How projects works". Each label is written out, so
      // none of them is the route name with a word bolted on.
      expect(label.toLowerCase(), route).not.toBe(`how ${route} works`);
    }
  });

  it("has no target for a route the guide does not cover", () => {
    expect(guideSectionFor("no-such-route")).toBeNull();
  });
});

// REM-GUIDE — the trade this map exists for is "remove the inline manual
// chapter, keep one contextual link". It only works where the link exists, so a
// navigable page with no guide target is a page that has to keep teaching on
// itself — which is the duplication the finding is about.
//
// Build was the one that showed why this needs an assertion rather than a
// habit: the product shipped `working-in-build.md` and had no way to open it,
// so the surface with the most to explain was the one that could only explain
// itself inline.
describe("every page the product navigates to can reach the guide", () => {
  // Guide itself is the destination, so it does not link to itself.
  const NOT_EXPLAINED_ELSEWHERE = new Set(["guide"]);

  it("gives every navigation destination a guide target", () => {
    const missing = NAV_ITEMS.map((item) => item.id)
      .filter((id) => !NOT_EXPLAINED_ELSEWHERE.has(id))
      .filter((id) => guideSectionFor(id) === null);
    expect(missing).toEqual([]);
  });

  it("leaves no guide chapter about a surface unreachable from that surface", () => {
    // Chapters that explain the product rather than one page are reached from
    // the guide's own index, which is what it is for.
    const GENERAL = new Set([
      "getting-started",
      "known-limits",
      "managing-the-host",
      "security-and-privacy",
    ]);
    const linked = new Set(mappedRoutes().map((route) => guideSectionFor(route)!.slug));
    const unreachable = [...slugs].filter((slug) => !GENERAL.has(slug) && !linked.has(slug));
    expect(unreachable).toEqual([]);
  });
});
