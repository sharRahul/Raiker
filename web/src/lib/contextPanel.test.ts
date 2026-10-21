import { describe, expect, it } from "vitest";
import { contextTabs, filesInUse } from "./contextPanel";
import type { ToolCallRow } from "./chatPresentation";
import type { TurnSourceView } from "./apiTypes";

const EMPTY = { files: [], plan: null, sources: [], activity: [] };
const FILE = { kind: "path" as const, label: "plan.md", detail: "notes/plan.md", path: "notes/plan.md" };

describe("contextTabs", () => {
  it("draws no tab with nothing in it", () => {
    expect(contextTabs(EMPTY)).toEqual([]);
    expect(contextTabs({ ...EMPTY, plan: { session_id: "s", steps: [] } })).toEqual([]);
  });

  it("draws each tab that has content, in a fixed order", () => {
    expect(
      contextTabs({
        files: [FILE],
        plan: { session_id: "s", steps: [{ title: "Read", status: "completed" }] },
        sources: [{ source_id: "src_1" } as TurnSourceView],
        activity: [{ actionId: "a1" } as ToolCallRow],
      }),
    ).toEqual(["context", "plan", "sources", "activity"]);
    expect(contextTabs({ ...EMPTY, activity: [{ actionId: "a1" } as ToolCallRow] })).toEqual(["activity"]);
  });
});

describe("filesInUse", () => {
  it("lists each file once across turns", () => {
    const image = { kind: "image" as const, label: "chart.png", detail: "PNG", attachmentId: "att_2" };
    expect(filesInUse([[FILE], [FILE, image]])).toEqual([FILE, image]);
  });
});
