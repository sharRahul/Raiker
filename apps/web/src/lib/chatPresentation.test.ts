import { describe, expect, it } from "vitest";
import type { StreamEvent } from "./apiTypes";
import {
  collectReasoning,
  familyIcon,
  hasRunningTool,
  toolActivity,
} from "./chatPresentation";

function toolEvent(payload: Record<string, unknown>): StreamEvent {
  return { kind: "tool", text: "", event_type: "", payload, response: null } as StreamEvent;
}

describe("tool activity", () => {
  // BUG-206 — the defect this replaces: a turn that ran tools rendered exactly
  // like one that ran none, because the broker's events reached the durable log
  // and never the stream. A row per call, in call order, is the whole fix.
  it("opens a row when a call starts and settles the same row when it finishes", () => {
    const events = [
      toolEvent({
        action_id: "act_1",
        tool_name: "read_file",
        family: "file-read",
        label: "Read file",
        action: "docs/ARCHITECTURE.md",
        status: "running",
      }),
      toolEvent({
        action_id: "act_1",
        tool_name: "read_file",
        family: "file-read",
        label: "Read file",
        action: "docs/ARCHITECTURE.md",
        status: "success",
      }),
    ];

    const rows = toolActivity(events);
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      actionId: "act_1",
      label: "Read file",
      action: "docs/ARCHITECTURE.md",
      state: "success",
    });
    expect(hasRunningTool(rows)).toBe(false);
  });

  it("keeps a batch in call order, and reports one still running", () => {
    const rows = toolActivity([
      toolEvent({ action_id: "a", tool_name: "glob", label: "Find files", status: "running" }),
      toolEvent({ action_id: "b", tool_name: "grep", label: "Search files", status: "running" }),
      toolEvent({ action_id: "a", tool_name: "glob", label: "Find files", status: "success" }),
    ]);
    expect(rows.map((row) => row.actionId)).toEqual(["a", "b"]);
    expect(hasRunningTool(rows)).toBe(true);
  });

  // An independent read batch runs concurrently (B4), so the *broker's* events
  // arrive in whatever order the worker threads finished. The runtime opens the
  // rows from the validated proposals first, so first-seen order is proposal
  // order — which is what "in call order" means to a person reading the turn.
  it("keeps proposal order even when the calls settle out of order", () => {
    const rows = toolActivity([
      toolEvent({ action_id: "a", tool_name: "list_directory", label: "List folder", status: "running" }),
      toolEvent({ action_id: "b", tool_name: "read_file", label: "Read file", status: "running" }),
      toolEvent({ action_id: "b", tool_name: "read_file", label: "Read file", status: "success" }),
      toolEvent({ action_id: "a", tool_name: "list_directory", label: "List folder", status: "success" }),
    ]);
    expect(rows.map((row) => row.label)).toEqual(["List folder", "Read file"]);
    expect(rows.every((row) => row.state === "success")).toBe(true);
  });

  it("says a parked call is waiting rather than leaving it pulsing", () => {
    const rows = toolActivity([
      toolEvent({ action_id: "a", tool_name: "write_file", label: "Write file", status: "running" }),
      toolEvent({ action_id: "a", tool_name: "write_file", label: "Write file", status: "waiting" }),
    ]);
    expect(rows[0].state).toBe("waiting");
    expect(hasRunningTool(rows)).toBe(false);
  });

  // BUG-206 slice E — what the separate refusal card at the bottom of the turn
  // used to say. It is the same row now, with its reasons and its remedy on it.
  it("renders a refused call as a row, with its reasons and remediation", () => {
    const rows = toolActivity([
      toolEvent({
        action_id: "act_9",
        tool_name: "shell",
        family: "shell",
        label: "Run command",
        action: "git",
        status: "refused",
        reasons: ["capability_disabled", "no_grant"],
        remediation_route: "capabilities",
      }),
    ]);
    expect(rows[0]).toEqual({
      actionId: "act_9",
      toolName: "shell",
      family: "shell",
      label: "Run command",
      action: "git",
      state: "refused",
      reasons: ["capability_disabled", "no_grant"],
      remediationRoute: "capabilities",
    });
  });

  it("opens an already-settled row for a call that failed before it started", () => {
    const rows = toolActivity([
      toolEvent({
        action_id: "act_3",
        tool_name: "write_file",
        family: "file-write",
        label: "Write file",
        action: "out.md",
        status: "failed",
        reason: "path_outside_workspace",
      }),
    ]);
    expect(rows[0].state).toBe("failed");
    expect(rows[0].reasons).toEqual(["path_outside_workspace"]);
  });

  it("ignores anything that is not a tool event, and any row that names no tool", () => {
    const rows = toolActivity([
      { kind: "text_delta", text: "hello", event_type: "", payload: {} } as StreamEvent,
      { kind: "lifecycle", text: "", event_type: "plan_created", payload: {} } as StreamEvent,
      toolEvent({ action_id: "x", status: "running" }),
    ]);
    expect(rows).toEqual([]);
  });

  it("gives an unrecognised family the neutral tool glyph rather than nothing", () => {
    expect(familyIcon("file-read")).toBe("file");
    expect(familyIcon("shell")).toBe("terminal");
    expect(familyIcon("something-new")).toBe("tool");
  });
});

describe("reasoning", () => {
  // BUG-207 — the disclosure this replaces held three fixed sentences chosen by
  // lifecycle event type. Nothing stands in for absent reasoning any more.
  it("concatenates the model's own reasoning in arrival order", () => {
    const events = [
      { kind: "reasoning_delta", text: "17 * 23 = ", event_type: "", payload: {} },
      { kind: "text_delta", text: "The answer", event_type: "", payload: {} },
      { kind: "reasoning_delta", text: "391.", event_type: "", payload: {} },
    ] as unknown as StreamEvent[];
    expect(collectReasoning(events)).toBe("17 * 23 = 391.");
  });

  it("is empty when the turn produced none, rather than substituting copy", () => {
    const events = [
      { kind: "text_delta", text: "Hello.", event_type: "", payload: {} },
      { kind: "lifecycle", text: "internal", event_type: "intent_classified", payload: {} },
    ] as unknown as StreamEvent[];
    expect(collectReasoning(events)).toBe("");
  });
});
