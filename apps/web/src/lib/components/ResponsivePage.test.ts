import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const source = readFileSync(resolve(process.cwd(), "src/lib/components/ResponsivePage.svelte"), "utf8");
const app = readFileSync(resolve(process.cwd(), "src/App.svelte"), "utf8");
const stylesheet = readFileSync(resolve(process.cwd(), "src/app.css"), "utf8");

describe("ResponsivePage bounds", () => {
  it("declares reading, workspace, operational, and work-surface planes", () => {
    expect(source).toContain('"reading" | "workspace" | "operational" | "work-surface"');
    expect(stylesheet).toContain("--page-reading: 72rem");
    expect(stylesheet).toContain("--page-workspace: 90rem");
    expect(stylesheet).toContain("--page-operational: 112rem");
    expect(stylesheet).toContain("--prose-measure: 68ch");
    expect(source).toMatch(/\.page\.operational/);
    expect(source).toMatch(/\.page\.work-surface/);
    expect(source).toContain("data-layout={layout}");
  });

  it("maps conversation canvases and operational hubs to their intended planes", () => {
    expect(app).toContain('current === "new-chat" || current === "build"');
    expect(app).toContain('? "work-surface" as const');
    expect(app).toContain('current === "models" || current === "extensions" || current === "observe"');
    expect(app).toContain('? "operational" as const');
  });

  it("does not scale display type with the viewport", () => {
    expect(stylesheet).not.toMatch(/font-size:\s*clamp\([^;]*vw/);
  });
});
