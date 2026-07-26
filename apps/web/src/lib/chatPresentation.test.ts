import { describe, expect, it } from "vitest";
import type { StreamEvent } from "./apiTypes";
import { reactionForResponse, thinkingSteps } from "./chatPresentation";

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

  it("adds one warm reaction when Raiker's response signals appreciation", () => {
    expect(reactionForResponse("You're welcome — happy to help!")).toEqual({
      emoji: "❤️",
      label: "Heart",
    });
  });

  it("does not attach a reaction to a neutral factual response", () => {
    expect(reactionForResponse("Paris is the capital of France.")).toBeNull();
  });
});
