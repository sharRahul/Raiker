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
    chat_profiles: [],
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

  it("keeps model runtime metadata out of the conversation", async () => {
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

    await waitFor(() => expect(screen.getByText("DONE")).toBeInTheDocument());
    expect(screen.queryByText(/cache hit|128 tok|completed/i)).not.toBeInTheDocument();
  });

  it("lists only configured models and sends the selected profile without a model override", async () => {
    stubFetch({
      ...MODELS_ROUTE,
      "GET /api/models": {
        ...(MODELS_ROUTE["GET /api/models"] as Record<string, unknown>),
        profiles: [
          {
            profile_id: "ollama-local-openai-compatible",
            provider: "ollama",
            model: "qwen2.5",
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
            context_window_tokens: 131072,
            configured: true,
          },
        ],
        chat_profiles: [
          {
            profile_id: "ollama-local-openai-compatible",
            provider: "ollama",
            model: "qwen2.5",
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
            context_window_tokens: 131072,
            configured: true,
          },
        ],
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
    const modelSelect = screen.getByLabelText("Model") as HTMLSelectElement;
    await waitFor(() => expect(modelSelect.options.length).toBeGreaterThan(1));
    expect(modelSelect.textContent).toContain("Ollama · qwen2.5");
    await fireEvent.change(modelSelect, {
      target: { value: "ollama-local-openai-compatible" },
    });

    const box = screen.getByRole("textbox", { name: /prompt/i });
    await fireEvent.input(box, { target: { value: "hi" } });
    await fireEvent.keyDown(box, { key: "Enter" });

    await waitFor(() => expect(streamPromptMock).toHaveBeenCalledOnce());
    const body = streamPromptMock.mock.calls[0][0] as Record<string, unknown>;
    expect(body.model_profile).toBe("ollama-local-openai-compatible");
    expect(body.model).toBeUndefined();
  });

  it("sends the server's safe-only planning mode when Never plan is selected", async () => {
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
    await fireEvent.change(screen.getByLabelText("Planning"), {
      target: { value: "never_safe_only" },
    });
    const box = screen.getByRole("textbox", { name: /prompt/i });
    await fireEvent.input(box, { target: { value: "hi" } });
    await fireEvent.keyDown(box, { key: "Enter" });

    await waitFor(() => expect(streamPromptMock).toHaveBeenCalledOnce());
    const body = streamPromptMock.mock.calls[0][0] as Record<string, unknown>;
    expect(body.planning_mode).toBe("never_safe_only");
  });

  it("names the persisted selection in the configured model dropdown", async () => {
    stubFetch({
      ...MODELS_ROUTE,
      "GET /api/models": {
        ...(MODELS_ROUTE["GET /api/models"] as Record<string, unknown>),
        profiles: [
          {
            profile_id: "ollama-local-openai-compatible",
            provider: "ollama",
            model: "gemma4:31b-cloud",
            default_state: "disabled",
            local_only: true,
            requires_network: false,
            endpoint_kind: "local",
            requires_egress_policy: false,
            requires_budget_policy: false,
            runtime_gate: null,
            off_machine: false,
            selected: true,
            prompt_cache_ttl: null,
            context_window_tokens: 131072,
            configured: true,
          },
        ],
        chat_profiles: [
          {
            profile_id: "ollama-local-openai-compatible",
            provider: "ollama",
            model: "gemma4:31b-cloud",
            default_state: "disabled",
            local_only: true,
            requires_network: false,
            endpoint_kind: "local",
            requires_egress_policy: false,
            requires_budget_policy: false,
            runtime_gate: null,
            off_machine: false,
            selected: true,
            prompt_cache_ttl: null,
            context_window_tokens: 131072,
            configured: true,
          },
        ],
      },
    });

    render(ChatView);
    const providerSelect = screen.getByLabelText("Model") as HTMLSelectElement;
    await waitFor(() => expect(providerSelect.options.length).toBeGreaterThan(1));
    // The default option must name the actual persisted selection, not just
    // say "Selected model" — the user has to see what will serve the turn.
    expect(providerSelect.options[0].textContent).toContain("Ollama");
    expect(providerSelect.options[0].textContent).toContain("gemma4:31b-cloud");
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

  it("uploads a document and sends it as a document attachment reference", async () => {
    stubFetch({
      ...MODELS_ROUTE,
      "POST /api/attachments": {
        ok: true,
        attachment_id: "att_doc",
        kind: "document",
        filename: "notes.txt",
        media_type: "text/plain",
        byte_size: 42,
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
    const fileInput = screen.getByLabelText("Upload document") as HTMLInputElement;
    const file = new File(["hello raiker"], "notes.txt", { type: "text/plain" });
    await fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => expect(screen.getByText("notes.txt")).toBeInTheDocument());

    const box = screen.getByRole("textbox", { name: /prompt/i });
    await fireEvent.input(box, { target: { value: "summarize this document" } });
    await fireEvent.keyDown(box, { key: "Enter" });

    await waitFor(() => expect(streamPromptMock).toHaveBeenCalledOnce());
    const body = streamPromptMock.mock.calls[0][0] as Record<string, unknown>;
    expect(body.attachments).toEqual([{ type: "document", attachment_id: "att_doc" }]);
  });

  it("rejects an unsupported document type client-side with an honest error", async () => {
    stubFetch(MODELS_ROUTE);
    render(ChatView);
    await fireEvent.click(screen.getByLabelText("Add attachment"));
    const fileInput = screen.getByLabelText("Upload document") as HTMLInputElement;
    const file = new File(["binary"], "archive.zip", { type: "application/zip" });
    await fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() =>
      expect(
        screen.getByText(/only plain-text, markdown, csv, pdf, or word/i),
      ).toBeInTheDocument(),
    );
    expect(screen.queryByText("archive.zip")).not.toBeInTheDocument();
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

  it("shows a route-level loading state while persisted history is fetched", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<never>(() => {})));
    render(ChatView, { props: { sessionId: "sess_hist" } });
    const statuses = await screen.findAllByRole("status");
    expect(statuses.some((el) => /loading conversation/i.test(el.textContent ?? ""))).toBe(true);
  });

  it("hydrates persisted turns and keeps their session when the route id clears", async () => {
    stubFetch({
      ...MODELS_ROUTE,
      "GET /api/sessions/sess_hist": {
        session: {
          session_id: "sess_hist",
          title: "Prior chat",
          status: "open",
          created_at: "2026-07-10T00:00:00Z",
          updated_at: "2026-07-10T00:01:00Z",
          turn_count: 2,
        },
        turns: [
          {
            turn_id: "turn_1",
            session_id: "sess_hist",
            turn_type: "prompt",
            status: "completed",
            prompt_text: "what is 2+2",
            created_at: "2026-07-10T00:00:00Z",
            completed_at: "2026-07-10T00:00:10Z",
            summary: "It is 4.",
          },
          {
            turn_id: "turn_2",
            session_id: "sess_hist",
            turn_type: "prompt",
            status: "completed",
            prompt_text: "thanks",
            created_at: "2026-07-10T00:00:20Z",
            completed_at: "2026-07-10T00:00:30Z",
            summary: "You're welcome.",
          },
        ],
      },
    });
    streamPromptMock.mockImplementation(
      async (_body: unknown, onEvent: (ev: StreamEvent) => void) => {
        onEvent({
          kind: "final",
          text: "",
          event_type: "",
          payload: {},
          response: { ...finalResponse("Sure."), session_id: "sess_hist" },
        } as StreamEvent);
      },
    );

    const { rerender } = render(ChatView, { props: { sessionId: "sess_hist" } });

    // Both the prior prompt and the restored agent answer must render — the
    // transcript is hydrated, not a blank composer.
    await waitFor(() => expect(screen.getByText("what is 2+2")).toBeInTheDocument());
    expect(screen.getByText("It is 4.")).toBeInTheDocument();
    expect(screen.getByText("thanks")).toBeInTheDocument();
    expect(screen.getByText("You're welcome.")).toBeInTheDocument();

    await rerender({ sessionId: null });

    // Continuing the conversation must reuse the same session id — a new
    // session must not be created merely to view history.
    const box = screen.getByRole("textbox", { name: /prompt/i });
    await fireEvent.input(box, { target: { value: "again" } });
    await fireEvent.keyDown(box, { key: "Enter" });

    await waitFor(() => expect(streamPromptMock).toHaveBeenCalledOnce());
    const body = streamPromptMock.mock.calls[0][0] as Record<string, unknown>;
    expect(body.session_id).toBe("sess_hist");
  });

  it("shows an honest error when persisted history cannot be loaded", async () => {
    stubFetch(MODELS_ROUTE);
    render(ChatView, { props: { sessionId: "sess_missing" } });

    await waitFor(() =>
      expect(screen.getByText(/could not load history/i)).toBeInTheDocument(),
    );
  });

  it("opens context details without changing or compacting the chat", async () => {
    stubFetch({
      ...MODELS_ROUTE,
      "GET /api/models": {
        ...(MODELS_ROUTE["GET /api/models"] as Record<string, unknown>),
        chat_profiles: [
          {
            profile_id: "configured-model",
            provider: "anthropic",
            model: "claude",
            default_state: "enabled",
            local_only: false,
            requires_network: true,
            endpoint_kind: "remote_hosted",
            requires_egress_policy: true,
            requires_budget_policy: false,
            runtime_gate: "hosted_model_runtime",
            off_machine: true,
            selected: true,
            prompt_cache_ttl: null,
            context_window_tokens: 1_000_000,
            configured: true,
          },
        ],
      },
    });
    render(ChatView);
    await fireEvent.click(screen.getByRole("button", { name: "Context window" }));
    expect(screen.getByText("0 / 1.0M (0%)")).toBeInTheDocument();
    expect(screen.queryByText(/context compacted/i)).not.toBeInTheDocument();
  });

  it("shows safe expandable thinking while Raiker prepares a response", async () => {
    stubFetch(MODELS_ROUTE);
    let finishStream: (() => void) | undefined;
    streamPromptMock.mockImplementation(
      async (_body: unknown, onEvent: (ev: StreamEvent) => void) => {
        onEvent({
          kind: "lifecycle",
          text: "internal intent payload",
          event_type: "intent_classified",
          payload: {},
          response: null,
        } as StreamEvent);
        await new Promise<void>((resolve) => {
          finishStream = resolve;
        });
      },
    );

    render(ChatView);
    const box = screen.getByRole("textbox", { name: /prompt/i });
    await fireEvent.input(box, { target: { value: "help me plan this" } });
    await fireEvent.keyDown(box, { key: "Enter" });

    expect(await screen.findByText("Raiker is thinking…")).toBeInTheDocument();
    const details = screen.getByLabelText("Raiker's thinking") as HTMLDetailsElement;
    expect(details.open).toBe(false);
    await fireEvent.click(screen.getByText("See what Raiker is thinking"));
    expect(details.open).toBe(true);
    expect(screen.getByText("Understanding what you need.")).toBeInTheDocument();
    expect(screen.queryByText("internal intent payload")).not.toBeInTheDocument();

    finishStream?.();
  });

  it("uses conversation bubbles, typing status, and a reaction without runtime metadata", async () => {
    stubFetch(MODELS_ROUTE);
    let finishStream: (() => void) | undefined;
    streamPromptMock.mockImplementation(
      async (_body: unknown, onEvent: (ev: StreamEvent) => void) => {
        onEvent({
          kind: "text_delta",
          text: "You're welcome — happy to help!",
          event_type: "",
          payload: {},
          response: null,
        } as StreamEvent);
        await new Promise<void>((resolve) => {
          finishStream = resolve;
        });
        onEvent({
          kind: "final",
          text: "",
          event_type: "",
          payload: {},
          response: finalResponse("You're welcome — happy to help!"),
        } as StreamEvent);
      },
    );

    render(ChatView);
    const box = screen.getByRole("textbox", { name: /prompt/i });
    await fireEvent.input(box, { target: { value: "thanks" } });
    await fireEvent.keyDown(box, { key: "Enter" });

    expect(await screen.findByText("Raiker is typing…")).toBeInTheDocument();
    finishStream?.();

    expect(await screen.findByLabelText("Raiker reacted with Heart")).toHaveTextContent("❤️");
    expect(document.querySelector(".message-group-user .message-bubble-user")).not.toBeNull();
    expect(document.querySelector(".message-group-raiker .message-bubble-raiker")).not.toBeNull();
    expect(screen.queryByText(/governing this turn|cache hit|completed/i)).not.toBeInTheDocument();
  });
});
