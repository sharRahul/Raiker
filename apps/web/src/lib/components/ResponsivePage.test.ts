import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const source = readFileSync(resolve(process.cwd(), "src/lib/components/ResponsivePage.svelte"), "utf8");

describe("ResponsivePage bounds", () => {
  it("declares separate reading and workspace planes", () => {
    expect(source).toContain('layout?: "reading" | "workspace"');
    expect(source).toMatch(/\.page \{ width: min\(100%, 90rem\); margin: 0 auto; \}/);
    expect(source).toMatch(/\.page\.reading \{ width: min\(100%, 72rem\); \}/);
    expect(source).toContain("data-layout={layout}");
  });
});
