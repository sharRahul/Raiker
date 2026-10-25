import { describe, expect, it } from "vitest";

import type { ContextUsage, StreamEvent } from "./apiTypes";
import { compressNotice, latestSettledTurnId, threadInsights } from "./threadInsights";

const tool = (action: string, label: string, status: string): StreamEvent =>
  ({ kind: "tool", payload: { tool_name: label.toLowerCase(), action_id: action, label, status } }) as unknown as StreamEvent;

describe("TOOL-131 /insights and /compress", () => {
  it("counts tool calls by label and outcome, and reads cost only when priced", () => {
    const turns = [
      { events: [tool("a", "Search files", "success"), tool("b", "Read file", "success")] },
      { events: [tool("c", "Search files", "failed"), tool("d", "Write file", "waiting")] },
    ];
    const usage = {
      session_turns: 2, model: "claude", session_input_tokens: 1200, session_output_tokens: 300,
      session_cost: "0.0123", currency: "USD", price_unknown: false,
    } as unknown as ContextUsage;
    const insights = threadInsights(turns, usage);
    expect(insights.toolCalls).toBe(4);
    expect(insights.topTools[0]).toEqual({ label: "Search files", count: 2 });
    expect(insights.notDone).toBe(1);
    expect(insights.asked).toBe(1);
    expect(insights.cost).toBe("$0.0123");
    expect(insights.turns).toBe(2);
    expect(insights.modelCalls).toBe(2);
    expect(threadInsights(turns, { ...usage, price_unknown: true }).cost).toBeNull();
    expect(threadInsights(turns, null).inputTokens).toBeNull();
  });

  it("summarises through the latest settled turn", () => {
    expect(
      latestSettledTurnId([
        { streaming: false, response: { turn_id: "t1" } },
        { streaming: false, response: { turn_id: "t2" } },
        { streaming: true, response: null },
      ]),
    ).toBe("t2");
    expect(latestSettledTurnId([])).toBeNull();
  });

  it("words the compaction answer", () => {
    expect(compressNotice({ compacted: true, source_turn_count: 1 })).toMatch(/^Summarised 1 earlier exchange for/);
    expect(compressNotice({ compacted: false, reason_code: "nothing_to_summarise" })).toBe("Everything up to that point is already summarised.");
  });
});
