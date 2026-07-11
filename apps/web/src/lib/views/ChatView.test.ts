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
    current_model: null,
    advisor_profile_id: null,
    advisor_model_gate_state: "enabled_runtime",
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

  it("lets the user pick a provider and one of its models for the turn", async () => {
    stubFetch({
      ...MODELS_ROUTE,
      "GET /api/models": {
        ...(MODELS_ROUTE["GET /api/models"] as Record<string, unknown>),
        profiles: [
          {
            profile_id: "ollama-local-openai-compatible",
            provider: "ollama",
            model: "<model>",
            default_state: "disabled",
            local_only: true,
            requires_network: false,
            endpoint_kind: "local",
            requires_egress_policy: false,
            requires_budget_policy: false,
            runtime_gate: null,
            off_machine: false,
            selected: false,
            prompt_cache_ttl: null,
          },
        ],
      },
      "GET /api/models/ollama-local-openai-compatible/provider-models": {
        profile_id: "ollama-local-openai-compatible",
        provider: "ollama",
        status: "available",
        reason_code: null,
        models: ["qwen2.5", "llama3.2"],
      },
    });
    streamPromptMock.mockImplementation(
      async (_body: unknown, onEvent: (ev: StreamEvent) => void) => {
        onEvent({
          kind: "final",
          text: "",
          event_type: "",
          payload: {},
          response: finalResponse("OK"),
        } as StreamEvent);
      },
    );

    render(ChatView);
    const providerSelect = screen.getByLabelText("Provider") as HTMLSelectElement;
    // Wait for the profiles fetch to populate the provider options.
    await waitFor(() => expect(providerSelect.options.length).toBeGreaterThan(1));
    await fireEvent.change(providerSelect, {
      target: { value: "ollama-local-openai-compatible" },
    });

    // The provider's catalogue loads on demand and populates the model select.
    await waitFor(() => expect(screen.getByLabelText("Model")).toBeTruthy());
    const modelSelect = screen.getByLabelText("Model") as HTMLSelectElement;
    expect(modelSelect.textContent).toContain("qwen2.5");
    await fireEvent.change(modelSelect, { target: { value: "qwen2.5" } });

    const box = screen.getByRole("textbox", { name: /prompt/i });
    await fireEvent.input(box, { target: { value: "hi" } });
    await fireEvent.keyDown(box, { key: "Enter" });

    await waitFor(() => expect(streamPromptMock).toHaveBeenCalledOnce());
    const body = streamPromptMock.mock.calls[0][0] as Record<string, unknown>;
    expect(body.model_profile).toBe("ollama-local-openai-compatible");
    expect(body.model).toBe("qwen2.5");
  });

  it("attaches workspace paths and sends them with the prompt", async () => {
    stubFetch(MODELS_ROUTE);
    streamPromptMock.mockImplementation(
      async (_body: unknown, onEvent: (ev: StreamEvent) => void) => {
        onEvent({
          kind: "final",
          text: "",
          event_type: "",
          payload: {},
          response: finalResponse("OK"),
        } as StreamEvent);
      },
    );

    render(ChatView);
    // The "+" button reveals the attachment path input.
    await fireEvent.click(screen.getByLabelText("Add attachment"));
    const attach = screen.getByLabelText("Attachment path") as HTMLInputElement;
    await fireEvent.input(attach, { target: { value: "docs/HANDOFF.md" } });
    await fireEvent.click(screen.getByText("Attach"));
    // The chip shows only the file name; the full path stays in the tooltip.
    expect(screen.getByText("HANDOFF.md")).toBeInTheDocument();
    expect(screen.queryByText("docs/HANDOFF.md")).not.toBeInTheDocument();

    const box = screen.getByRole("textbox", { name: /prompt/i });
    await fireEvent.input(box, { target: { value: "summarize the attachment" } });
    await fireEvent.keyDown(box, { key: "Enter" });

    await waitFor(() => expect(streamPromptMock).toHaveBeenCalledOnce());
    const body = streamPromptMock.mock.calls[0][0] as Record<string, unknown>;
    expect(body.attachments).toEqual([{ type: "path", path: "docs/HANDOFF.md" }]);
    // The sent turn shows the attachment chip; the composer input is cleared.
    expect((screen.getByLabelText("Attachment path") as HTMLInputElement).value).toBe("");
  });

  it("uploads an image and sends it as an image attachment reference", async () => {
    stubFetch({
      ...MODELS_ROUTE,
      "POST /api/attachments": {
        ok: true,
        attachment_id: "att_1",
        kind: "image",
        filename: "shot.png",
        media_type: "image/png",
        byte_size: 68,
        sha256: "abc",
      },
    });
    streamPromptMock.mockImplementation(
      async (_body: unknown, onEvent: (ev: StreamEvent) => void) => {
        onEvent({
          kind: "final",
          text: "",
          event_type: "",
          payload: {},
          response: finalResponse("OK"),
        } as StreamEvent);
      },
    );

    render(ChatView);
    await fireEvent.click(screen.getByLabelText("Add attachment"));
    const fileInput = screen.getByLabelText("Upload image") as HTMLInputElement;
    const file = new File([new Uint8Array([137, 80, 78, 71])], "shot.png", {
      type: "image/png",
    });
    await fireEvent.change(fileInput, { target: { files: [file] } });

    // The upload resolves and the chip shows the file name.
    await waitFor(() => expect(screen.getByText("shot.png")).toBeInTheDocument());

    const box = screen.getByRole("textbox", { name: /prompt/i });
    await fireEvent.input(box, { target: { value: "what is in this image?" } });
    await fireEvent.keyDown(box, { key: "Enter" });

    await waitFor(() => expect(streamPromptMock).toHaveBeenCalledOnce());
    const body = streamPromptMock.mock.calls[0][0] as Record<string, unknown>;
    expect(body.attachments).toEqual([{ type: "image", attachment_id: "att_1" }]);
  });

  it("rejects a non-image file client-side with an honest error", async () => {
    stubFetch(MODELS_ROUTE);
    render(ChatView);
    await fireEvent.click(screen.getByLabelText("Add attachment"));
    const fileInput = screen.getByLabelText("Upload image") as HTMLInputElement;
    const file = new File(["#!/bin/sh"], "evil.sh", { type: "text/x-shellscript" });
    await fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() =>
      expect(screen.getByText(/only png, jpeg, webp, or gif/i)).toBeInTheDocument(),
    );
    expect(screen.queryByText("evil.sh")).not.toBeInTheDocument();
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
