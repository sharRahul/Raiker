import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AgentResponse, StreamEvent } from "../apiTypes";
import { stubFetch } from "../test-helpers";
import { resetModels } from "../models.svelte";

const streamPromptMock = vi.hoisted(() => vi.fn());
vi.mock("../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api")>();
  return { ...actual, streamPrompt: streamPromptMock };
});

import ChatView from "./ChatView.svelte";

afterEach(() => {
  vi.unstubAllGlobals();
  streamPromptMock.mockReset();
  resetModels();
});

const projects = {
  active_project_id: null,
  projects: [
    {
      project_id: "project-1",
      name: "Composer project",
      root_subpath: "projects/composer",
      created_at: "2026-07-28T10:00:00Z",
      session_count: 0,
      selected: false,
      parent_id: null,
      path: "Composer project",
      is_archived: false,
      archived_at: null,
    },
  ],
};

function routes() {
  const ready = { profile_id: "test-ready", provider: "ollama", model: "test-model", selected: true, configured: true, ready: true, readiness_state: "ready" };
  return {
    "GET /api/models": { profiles: [ready], chat_profiles: [ready] },
    "GET /api/tasks": [],
    "PUT /api/sessions/session-chat/project": { ok: true, session_id: "session-chat", project_id: "project-1" },
  };
}

const REASONING_PROFILE = {
  profile_id: "anthropic-claude",
  provider: "anthropic",
  model: "claude-sonnet",
  selected: true,
  configured: true,
  ready: true,
  readiness_state: "ready",
  supports_reasoning: true,
  supports_reasoning_effort: true,
  reasoning_effort_values: ["low", "high"],
};

const NON_REASONING_PROFILE = {
  profile_id: "ollama-gemma",
  provider: "ollama",
  model: "gemma4:31b-cloud",
  selected: true,
  configured: true,
  ready: true,
  readiness_state: "ready",
  supports_reasoning: false,
  supports_reasoning_effort: false,
  reasoning_effort_values: [],
};

describe("ChatView composer parity", () => {
  it("renders its background-work rail beside the chat column, not below the composer", async () => {
    stubFetch(routes());
    render(ChatView, { projects });

    // The rail is collapsed by default; opening it places the panel beside the
    // chat column rather than below the composer.
    await fireEvent.click(await screen.findByRole("button", { name: "Background work" }));
    const rail = await screen.findByRole("complementary", { name: "Background work" });
    expect(rail.closest(".rail-slot")).toBeInTheDocument();
    expect(rail.closest(".chat")).toBeNull();
    expect(rail.closest(".chat-layout")).toHaveClass("with-rail");
    expect(screen.getByLabelText("Project for this chat")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /approval mode/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Context window" })).toBeInTheDocument();
  });

  it("uses the persisted selected model and exposes only its supported thinking efforts", async () => {
    stubFetch({
      ...routes(),
      "GET /api/models": { profiles: [REASONING_PROFILE], chat_profiles: [REASONING_PROFILE] },
    });
    render(ChatView, { projects });

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Model for this turn: Claude Sonnet" })).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "Model for this turn: Claude Sonnet" })).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Model for this turn: Claude Sonnet" }));
    expect(screen.getByRole("menu", { name: "Models" })).toBeInTheDocument();
    // Trigger, provider header, and model row all identify Anthropic.
    expect(screen.getAllByRole("img", { name: "Anthropic logo" })).toHaveLength(3);
    expect(screen.getByRole("menuitemradio", { name: /Claude Sonnet/ })).toBeInTheDocument();
    const effort = screen.getByLabelText("Thinking effort");
    expect(within(effort).getAllByRole("option").map((option) => option.textContent)).toEqual([
      "Thinking: default",
      "low",
      "high",
    ]);
  });

  it("shows Not selected and blocks the prompt when no model is active", async () => {
    stubFetch({
      ...routes(),
      "GET /api/models": { profiles: [], chat_profiles: [] },
    });
    streamPromptMock.mockImplementation(async (_body: unknown, onEvent: (event: StreamEvent) => void) => {
      onEvent({ kind: "final", text: "", event_type: "", payload: {}, response: null });
    });
    render(ChatView, { projects });

    await waitFor(() => expect(screen.getByRole("button", { name: "Model for this turn: Not selected" })).toBeInTheDocument());
    expect(screen.queryByLabelText("Thinking effort")).not.toBeInTheDocument();
    await fireEvent.input(screen.getByLabelText("Prompt"), { target: { value: "Hello" } });
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    expect(screen.getByText("No model is set up.")).toBeInTheDocument();
    expect(streamPromptMock).not.toHaveBeenCalled();
  });

  it("sends an effort only for the active exact supported profile", async () => {
    stubFetch({
      ...routes(),
      "GET /api/models": { profiles: [REASONING_PROFILE, NON_REASONING_PROFILE], chat_profiles: [REASONING_PROFILE, NON_REASONING_PROFILE] },
    });
    streamPromptMock.mockImplementation(async (_body: unknown, onEvent: (event: StreamEvent) => void) => {
      onEvent({ kind: "final", text: "", event_type: "", payload: {}, response: null });
    });
    render(ChatView, { projects });

    await waitFor(() => expect(screen.getByLabelText("Thinking effort")).toBeInTheDocument());
    await fireEvent.change(screen.getByLabelText("Thinking effort"), { target: { value: "high" } });
    await fireEvent.input(screen.getByLabelText("Prompt"), { target: { value: "Reason" } });
    await fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(streamPromptMock).toHaveBeenCalled());
    expect(streamPromptMock.mock.calls[0][0]).toMatchObject({ reasoning_effort: "high" });
  });

  it("files the selected project after the first response creates the session", async () => {
    const fetchMock = stubFetch(routes());
    streamPromptMock.mockImplementation(async (_body: unknown, onEvent: (event: StreamEvent) => void) => {
      onEvent({
        kind: "final",
        text: "",
        event_type: "",
        payload: {},
        response: {
          request_id: "request-1",
          session_id: "session-chat",
          turn_id: "turn-1",
          status: "completed",
          message: "Done",
          events_path: null,
          checkpoint_path: null,
          approval: null,
          last_event_id: null,
        } satisfies AgentResponse,
      });
    });
    render(ChatView, { projects });

    await fireEvent.change(await screen.findByLabelText("Project for this chat"), {
      target: { value: "project-1" },
    });
    await fireEvent.input(screen.getByLabelText("Prompt"), { target: { value: "Start" } });
    await fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/api/sessions/session-chat/project"))).toBe(true),
    );
  });
});
