import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

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
