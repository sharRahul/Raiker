import { describe, expect, it } from "vitest";
import type { StreamEvent } from "./apiTypes";
import { reactionForPrompt, refusedCalls, thinkingSteps } from "./chatPresentation";

describe("chat presentation", () => {
  it("turns recognised lifecycle events into safe conversational thinking steps", () => {
    const events = [
      { kind: "lifecycle", event_type: "intent_classified", text: "raw internal data" },
      { kind: "lifecycle", event_type: "model_request_started", text: "provider metadata" },
      { kind: "tool", event_type: "tool_started", text: "raw tool detail" },
      { kind: "lifecycle", event_type: "intent_classified", text: "duplicate" },
    ] as StreamEvent[];

    expect(thinkingSteps(events)).toEqual([
      "Understanding what you need.",
      "Putting together a response.",
    ]);
  });

  it("adds Raiker's reaction to the user's greeting", () => {
    expect(reactionForPrompt("Hello Raiker")).toEqual({
      emoji: "👋",
      label: "Waving hand",
    });
  });

  it("does not attach a reaction to a neutral user prompt", () => {
    expect(reactionForPrompt("What is the capital of France?")).toBeNull();
  });

  // BUG-52 — a refused call no longer ends the turn, so Chat has to say it was
  // refused. Order is the model's own proposal order: an owner reading two
  // refusals needs them to line up with the calls they refused.
  it("lists the calls policy refused, in the order they were refused", () => {
    const events = [
      { kind: "lifecycle", event_type: "intent_classified", payload: {} },
      {
        kind: "lifecycle",
        event_type: "model_tool_call_refused",
        payload: { tool_name: "read_file", reasons: ["path_outside_workspace"] },
      },
      {
        kind: "lifecycle",
        event_type: "model_tool_call_refused",
        payload: {
          tool_name: "shell",
          reasons: ["capability_disabled", "no_grant"],
          remediation_route: "capabilities",
        },
      },
    ] as unknown as StreamEvent[];

    expect(refusedCalls(events)).toEqual([
      { toolName: "read_file", reasons: ["path_outside_workspace"] },
      {
        toolName: "shell",
        reasons: ["capability_disabled", "no_grant"],
        remediationRoute: "capabilities",
      },
    ]);
  });

  it("ignores a refusal event that names no tool rather than rendering a blank row", () => {
    const events = [
      { kind: "lifecycle", event_type: "model_tool_call_refused", payload: { reasons: ["x"] } },
      { kind: "lifecycle", event_type: "model_tool_call_refused", payload: { tool_name: "grep" } },
    ] as unknown as StreamEvent[];

    expect(refusedCalls(events)).toEqual([{ toolName: "grep", reasons: [] }]);
  });
});
