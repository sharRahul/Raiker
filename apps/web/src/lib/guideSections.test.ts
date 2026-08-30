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

const GUIDE = resolve(process.cwd(), "..", "..", "docs", "guide");

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
