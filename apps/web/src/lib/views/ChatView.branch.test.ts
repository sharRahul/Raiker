// GAP-CHAT C14, the part that was left open: branch from here.
//
// Edit and Retry continue this conversation. Branching opens a *second* one from
// a chosen point, and the property that makes it safe is what these tests hold:
// the conversation you branched from keeps every turn it had, and the branch says
// where it grew from.
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
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
  window.location.hash = "";
});

const READY = {
  profile_id: "test-ready",
  provider: "ollama",
  model: "test-model",
  selected: true,
  configured: true,
  ready: true,
  readiness_state: "ready",
};

const RESPONSE: AgentResponse = {
  request_id: "request-1",
  session_id: "session-chat",
  turn_id: "turn-1",
  status: "completed",
  message: "Two options, and I took the first.",
  events_path: null,
  checkpoint_path: null,
  approval: null,
  last_event_id: null,
};

function routes(overrides: Record<string, unknown> = {}) {
  return {
    "GET /api/models": { profiles: [READY], chat_profiles: [READY] },
    "GET /api/tasks": [],
    ...overrides,
  };
}

/** Send one prompt so the transcript has a completed turn to branch from. */
async function sendOneTurn() {
  streamPromptMock.mockImplementation(
    async (_body: unknown, onEvent: (event: StreamEvent) => void) => {
      onEvent({
        kind: "final",
        text: "Two options, and I took the first.",
        event_type: "",
        payload: {},
        response: RESPONSE,
      });
    },
  );
  await fireEvent.input(screen.getByLabelText("Prompt"), {
    target: { value: "Which option should we take?" },
  });
  await fireEvent.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() =>
    expect(screen.getByRole("button", { name: /branch a second conversation/i })).toBeInTheDocument(),
  );
}

describe("branch from here", () => {
  it("branches from the checkpoint of that exact turn and opens the branch", async () => {
    const fetchMock = stubFetch(
      routes({
        "GET /api/checkpoints": [
          {
            checkpoint_id: "ckpt_other",
            session_id: "session-chat",
            turn_id: "turn-0",
            task_id: null,
            checkpoint_type: "turn",
            created_at: "2026-08-16T10:00:00Z",
            summary: "an earlier turn",
            last_event_id: null,
            can_restore_state: true,
            can_restore_files: false,
          },
          {
            checkpoint_id: "ckpt_here",
            session_id: "session-chat",
            turn_id: "turn-1",
            task_id: null,
            checkpoint_type: "turn",
            created_at: "2026-08-16T10:01:00Z",
            summary: "chose the first option",
            last_event_id: null,
            can_restore_state: true,
            can_restore_files: false,
          },
        ],
        "POST /api/checkpoints/ckpt_here/branch": {
          status: "forked",
          checkpoint_id: "ckpt_here",
          source_session_id: "session-chat",
          session_id: "sess_branch_1",
          title: "fork of chose the first option",
          summary: "chose the first option",
          memory_candidate_count: 0,
          seed_manifest_path: "checkpoints/forks/sess_branch_1.json",
        },
      }),
    );
    render(ChatView, { projects: null });
    await sendOneTurn();

    await fireEvent.click(screen.getByRole("button", { name: /branch a second conversation/i }));

    // The branch is taken from this turn's own checkpoint, not the latest one.
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([url, init]) =>
            String(url).endsWith("/api/checkpoints/ckpt_here/branch") && init?.method === "POST",
        ),
      ).toBe(true),
    );
    expect(
      fetchMock.mock.calls.some(([url]) =>
        String(url).includes("/api/checkpoints/ckpt_other/branch"),
      ),
    ).toBe(false);
    // And the owner lands in it.
    await waitFor(() => expect(window.location.hash).toBe("#/new-chat?session=sess_branch_1"));
  });

  it("says there is no point to branch from rather than inventing one", async () => {
    stubFetch(routes({ "GET /api/checkpoints": [] }));
    render(ChatView, { projects: null });
    await sendOneTurn();

    await fireEvent.click(screen.getByRole("button", { name: /branch a second conversation/i }));

    expect(
      await screen.findByText(/No checkpoint was written for that turn/),
    ).toBeInTheDocument();
    expect(window.location.hash).toBe("");
  });

  it("names the conversation a branch grew from, and links back to it unchanged", async () => {
    stubFetch(
      routes({
        "GET /api/sessions/sess_branch_1": {
          session_id: "sess_branch_1",
          title: "fork of chose the first option",
          status: "active",
          created_at: "2026-08-16T10:02:00Z",
          updated_at: "2026-08-16T10:02:00Z",
          turns: [],
          parked_approvals: [],
        },
        "GET /api/sessions/sess_branch_1/branch-origin": {
          session_id: "sess_branch_1",
          source_session_id: "session-chat",
          source_title: "Which option should we take?",
          forked_from_checkpoint_id: "ckpt_here",
          summary: "chose the first option",
          created_at: "2026-08-16T10:02:00Z",
        },
      }),
    );
    render(ChatView, { projects: null, sessionId: "sess_branch_1" });

    const banner = await screen.findByText(/Branched from/);
    expect(banner).toHaveTextContent("chose the first option");
    expect(banner).toHaveTextContent("kept every turn it had");
    expect(
      screen.getByRole("link", { name: "Which option should we take?" }),
    ).toHaveAttribute("href", "#/new-chat?session=session-chat");
  });

  it("shows no lineage band on a conversation that is not a branch", async () => {
    stubFetch(
      routes({
        "GET /api/sessions/session-root": {
          session_id: "session-root",
          title: "A root conversation",
          status: "active",
          created_at: "2026-08-16T10:02:00Z",
          updated_at: "2026-08-16T10:02:00Z",
          turns: [],
          parked_approvals: [],
        },
        "GET /api/sessions/session-root/branch-origin": {
          session_id: "session-root",
          source_session_id: null,
          source_title: null,
          forked_from_checkpoint_id: null,
          summary: "",
          created_at: "",
        },
      }),
    );
    render(ChatView, { projects: null, sessionId: "session-root" });

    await waitFor(() => expect(screen.getByLabelText("Prompt")).toBeInTheDocument());
    expect(screen.queryByText(/Branched from/)).not.toBeInTheDocument();
  });
});
