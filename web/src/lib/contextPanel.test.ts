import { describe, expect, it } from "vitest";
import { contextTabs, filesInUse, memoriesInUse } from "./contextPanel";
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

describe("memoriesInUse", () => {
  it("lists each recalled memory once, in first-recalled order", () => {
    const a = { memory_id: "a", turn_id: "t1", text: "A", scope: "user", pinned: false };
    const b = { memory_id: "b", turn_id: "t1", text: "B", scope: "project", pinned: false };
    expect(memoriesInUse([a, b, { ...a, turn_id: "t2" }]).map((m) => m.memory_id)).toEqual(["a", "b"]);
    expect(contextTabs({ files: [], memories: [a], plan: null, sources: [], activity: [] })).toEqual(["memories"]);
  });
});
