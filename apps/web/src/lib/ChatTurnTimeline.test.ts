import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import ChatTurnTimeline from "./ChatTurnTimeline.svelte";
import type { AgentResponse, StreamEvent } from "./apiTypes";

function lifecycle(eventType: string, payload: Record<string, unknown> = {}): StreamEvent {
  return { kind: "lifecycle", text: "", event_type: eventType, payload, response: null };
}
function delta(text: string): StreamEvent {
  return { kind: "text_delta", text, event_type: "", payload: {}, response: null };
}

// A representative fixture stream covering all four phases plus answer text.
const FIXTURE: StreamEvent[] = [
  lifecycle("prompt_normalised", { text_length: 5 }),
  lifecycle("intent_classified", { intent: "qa", confidence: 0.9 }),
  lifecycle("risk_classified", { risk_level: "low", requires_approval: false }),
  lifecycle("plan_skipped", {}),
  lifecycle("model_request_started", { provider: "mock", model: "test" }),
  lifecycle("model_request_completed", { finish_reason: "stop", tool_call_count: 0 }),
  delta("Hello "),
  delta("world."),
  lifecycle("verification_completed", { status: "ok" }),
];

describe("ChatTurnTimeline", () => {
  it("renders gather/plan/act/verify phases and the streamed answer from a fixture stream", () => {
    render(ChatTurnTimeline, { props: { events: FIXTURE, finalResponse: null, streaming: true } });
    expect(screen.getByText("Gather")).toBeInTheDocument();
    expect(screen.getByText("Plan")).toBeInTheDocument();
    expect(screen.getByText("Act")).toBeInTheDocument();
    expect(screen.getByText("Verify")).toBeInTheDocument();
    expect(screen.getByText("Hello world.")).toBeInTheDocument();
  });

  it("shows a denied turn inline with a plain-English reason", () => {
    const final: AgentResponse = {
      request_id: "req_1",
      session_id: "sess_1",
      turn_id: "turn_1",
      status: "denied",
      message: "Action denied by policy: denied_by_policy",
      approval: null,
    };
    render(ChatTurnTimeline, { props: { events: FIXTURE, finalResponse: final, streaming: false } });
    expect(screen.getByText(/Action denied by policy/)).toBeInTheDocument();
    expect(screen.getByText(/Policy blocked this action/i)).toBeInTheDocument();
  });

  it("renders an ActionProposalCard for a needs_approval turn (not executed)", () => {
    const final: AgentResponse = {
      request_id: "req_2",
      session_id: "sess_1",
      turn_id: "turn_2",
      status: "needs_approval",
      message: "Approval required for local action. No command was executed.",
      approval: {
        action_id: "act_1",
        tool_name: "write_file",
        arguments: { path: "notes.txt", content: "hello" },
        risk_level: "high",
        reasons: ["approval_required"],
        message: "Approval required. The action was not executed.",
      },
    };
    render(ChatTurnTimeline, { props: { events: FIXTURE, finalResponse: final, streaming: false } });
    expect(screen.getByText("write_file")).toBeInTheDocument();
    expect(screen.getAllByText(/not executed/i).length).toBeGreaterThan(0);
    expect(screen.getByText("notes.txt")).toBeInTheDocument();
    expect(screen.getByText(/needs human approval first/i)).toBeInTheDocument();
  });
});
