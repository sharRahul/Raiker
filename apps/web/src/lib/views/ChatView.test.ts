// Regression coverage for the streamed transcript: events and the final
// response must actually re-render (Svelte 5 signals track the $state-proxied
// turn, so mutations must go through it — this suite caught the raw-object
// mutation bug where the UI stayed on "Working…" after the stream finished).
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AgentResponse, StreamEvent } from "../apiTypes";
import { stubFetch } from "../test-helpers";

const streamPromptMock = vi.hoisted(() => vi.fn());
vi.mock("../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api")>();
  return { ...actual, streamPrompt: streamPromptMock };
});

import ChatView from "./ChatView.svelte";

afterEach(() => {
  vi.unstubAllGlobals();
  streamPromptMock.mockReset();
});

const MODELS_ROUTE = {
  "GET /api/models": {
    profiles: [],
    current_profile_id: null,
    hosted_model_gate_state: "enabled_runtime",
    private_network_model_gate_state: "enabled_runtime",
    model_egress_allowlist_configured: false,
    remote_profile_count: 0,
    fallback_sequence: [],
    no_silent_hosted_fallback: true,
  },
};

function finalResponse(message: string): AgentResponse {
  return {
    request_id: "req_1",
    session_id: "sess_1",
    turn_id: "turn_1",
    status: "completed",
    message,
    events_path: null,
    checkpoint_path: null,
    client: { type: "web_ui", name: "raiker-web", version: "0" },
    approval: null,
    last_event_id: "evt_1",
    schema_version: "1.0",
  } as unknown as AgentResponse;
}

describe("ChatView streaming transcript", () => {
  it("renders streamed lifecycle events and settles on the final response", async () => {
    stubFetch(MODELS_ROUTE);
    streamPromptMock.mockImplementation(
      async (_body: unknown, onEvent: (ev: StreamEvent) => void) => {
        onEvent({
          kind: "lifecycle",
          text: "",
          event_type: "intent_classified",
          payload: { intent: "chat" },
          response: null,
        } as StreamEvent);
        onEvent({
          kind: "text_delta",
          text: "READY",
          event_type: "",
          payload: {},
          response: null,
        } as StreamEvent);
        onEvent({
          kind: "final",
          text: "",
          event_type: "",
          payload: {},
          response: finalResponse("READY"),
        } as StreamEvent);
      },
    );

    render(ChatView);
    const box = screen.getByRole("textbox", { name: /prompt/i });
    await fireEvent.input(box, { target: { value: "hi" } });
    await fireEvent.keyDown(box, { key: "Enter" });

    // The final message must render and the working indicator must clear —
    // the stream resolved, so nothing may stay stuck on "Working".
    await waitFor(() => {
      expect(screen.getByText("READY")).toBeInTheDocument();
    });
    expect(screen.queryByText(/working/i)).not.toBeInTheDocument();
    expect(streamPromptMock).toHaveBeenCalledOnce();
  });

  it("shows a cache-hit chip from the model_request_completed usage", async () => {
    stubFetch(MODELS_ROUTE);
    streamPromptMock.mockImplementation(
      async (_body: unknown, onEvent: (ev: StreamEvent) => void) => {
        onEvent({
          kind: "lifecycle",
          text: "",
          event_type: "model_request_completed",
          payload: { provider: "anthropic", usage: { cache_read_tokens: 128, cache_hit: 1 } },
          response: null,
        } as StreamEvent);
        onEvent({
          kind: "final",
          text: "",
          event_type: "",
          payload: {},
          response: finalResponse("DONE"),
        } as StreamEvent);
      },
    );

    render(ChatView);
    const box = screen.getByRole("textbox", { name: /prompt/i });
    await fireEvent.input(box, { target: { value: "hi" } });
    await fireEvent.keyDown(box, { key: "Enter" });

    await waitFor(() => {
      expect(screen.getByText(/cache hit · 128 tok/i)).toBeInTheDocument();
    });
  });

  it("shows an honest error when the stream cannot be reached", async () => {
    stubFetch(MODELS_ROUTE);
    streamPromptMock.mockRejectedValue(new Error("connection refused"));

    render(ChatView);
    const box = screen.getByRole("textbox", { name: /prompt/i });
    await fireEvent.input(box, { target: { value: "hi" } });
    await fireEvent.keyDown(box, { key: "Enter" });

    await waitFor(() => {
      expect(screen.getByText(/could not reach the local runtime/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/working/i)).not.toBeInTheDocument();
  });
});
