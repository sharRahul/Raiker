/**
 * BUG-22 and BUG-24 in the Chat surface.
 *
 * Two behaviours that have to hold together: a conversation the owner can take
 * away as a file, and a parked turn that continues itself when the decision is
 * made somewhere else.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AgentResponse, StreamEvent } from "../apiTypes";
import { stubFetch } from "../test-helpers";
import { resetModels } from "../models.svelte";

const streamPromptMock = vi.hoisted(() => vi.fn());
const streamResumeMock = vi.hoisted(() => vi.fn());
vi.mock("../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api")>();
  return {
    ...actual,
    streamPrompt: streamPromptMock,
    streamResumeAfterApproval: streamResumeMock,
  };
});

import ChatView from "./ChatView.svelte";

afterEach(() => {
  vi.unstubAllGlobals();
  streamPromptMock.mockReset();
  streamResumeMock.mockReset();
  resetModels();
});

const READY_PROFILE = {
  profile_id: "test-ready",
  provider: "ollama",
  model: "test-model",
  selected: true,
  configured: true,
  ready: true,
  readiness_state: "ready",
};

const PARKED: AgentResponse = {
  request_id: "req_1",
  session_id: "sess_1",
  turn_id: "turn_1",
  status: "needs_approval",
  message: "",
  events_path: null,
  checkpoint_path: null,
  approval: {
    approval_id: "apv_1",
    tool_name: "write_file",
    risk_level: "medium",
    message: "Raiker wants to write notes.md",
    expected_effect: "Writes one file in your workspace.",
  } as AgentResponse["approval"],
  last_event_id: null,
};

const RESUMABLE = {
  approval_id: "apv_1",
  session_id: "sess_1",
  turn_id: "turn_1",
  tool_name: "write_file",
  outcome_status: "success",
  created_at: "2026-07-31T10:00:00Z",
};

function baseRoutes(extra: Record<string, unknown> = {}) {
  return {
    "GET /api/models": {
      profiles: [READY_PROFILE],
      chat_profiles: [READY_PROFILE],
    },
    "GET /api/settings": { settings: {}, status: { vault: "ok", mfa_enrolled: false, username: "owner" } },
    "GET /api/sessions/sess_1/attachments": { session_id: "sess_1", files: [] },
    "GET /api/approvals/resumable": { session_id: "sess_1", turns: [] },
    ...extra,
  };
}

/** Send one prompt that parks on an approval, leaving the turn waiting. */
async function parkATurn() {
  streamPromptMock.mockImplementation(
    async (_body: unknown, onEvent: (event: StreamEvent) => void) => {
      onEvent({ kind: "final", text: "", event_type: "", payload: {}, response: PARKED });
    },
  );
  await fireEvent.input(screen.getByLabelText("Prompt"), { target: { value: "Write notes" } });
  await fireEvent.click(screen.getByRole("button", { name: "Send" }));
  await screen.findByText("Waiting for approval");
}

describe("ChatView — cross-tab approval continuation (BUG-24)", () => {
  it("restores a pending approval card when a parked conversation is reloaded", async () => {
    stubFetch(baseRoutes({
      "GET /api/sessions/sess_1": {
        session: { session_id: "sess_1", title: "Notes" },
        turns: [{
          turn_id: "turn_1", session_id: "sess_1", turn_type: "prompt",
          status: "needs_approval", prompt_text: "Write notes", created_at: "2026-08-01T10:00:00Z",
          completed_at: null, summary: "",
        }],
        parked_approvals: [{
          approval_id: "apv_1", turn_id: "turn_1", tool_name: "write_file",
          created_at: "2026-08-01T10:00:00Z",
        }],
      },
    }));

    render(ChatView, { props: { sessionId: "sess_1" } });

    expect(await screen.findByText("Waiting for approval")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Review approval" })).toBeInTheDocument();
  });
  it("shows a parked turn as Waiting for approval", async () => {
    stubFetch(baseRoutes());
    render(ChatView, {});
    await parkATurn();
    expect(screen.getByText("Raiker wants to write notes.md")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Review approval" })).toBeInTheDocument();
  });

  // ADD-02 — a turn that proposed a batch asks for more than one decision. The
  // transcript carries the runtime's own statement of which one this is, so the
  // owner reads three approvals as one plan rather than as the agent proposing
  // the same thing three times.
  it("carries the batch position the runtime stated into the transcript", async () => {
    stubFetch(baseRoutes());
    streamPromptMock.mockImplementation(
      async (_body: unknown, onEvent: (event: StreamEvent) => void) => {
        onEvent({
          kind: "final", text: "", event_type: "", payload: {},
          response: {
            ...PARKED,
            approval: {
              ...PARKED.approval,
              message: "Approval required — decision 2 of 3 in this batch.",
              queue_position: 2,
              queue_total: 3,
              queued_calls: 1,
            },
          } as AgentResponse,
        });
      },
    );
    render(ChatView, {});
    await fireEvent.input(screen.getByLabelText("Prompt"), { target: { value: "Write three" } });
    await fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText(/decision 2 of 3 in this batch/i)).toBeInTheDocument();
  });

  it("flips to Approved — continuing… and streams the resumption, without a reload", async () => {
    stubFetch(baseRoutes({ "GET /api/approvals/resumable": { session_id: "sess_1", turns: [RESUMABLE] } }));
    let resolveStream: (() => void) | undefined;
    streamResumeMock.mockImplementation(async () => {
      await new Promise<void>((resolve) => (resolveStream = resolve));
    });
    render(ChatView, {});
    await parkATurn();

    // The resolution happened in another tab; the watcher's poll finds it.
    expect(await screen.findByText("Approved — continuing…")).toBeInTheDocument();
    await waitFor(() => expect(streamResumeMock).toHaveBeenCalledWith("apv_1", expect.any(Function)));
    resolveStream?.();
  });

  it("resumes the same turn exactly once even as the poll repeats", async () => {
    stubFetch(baseRoutes({ "GET /api/approvals/resumable": { session_id: "sess_1", turns: [RESUMABLE] } }));
    streamResumeMock.mockImplementation(async () => {});
    render(ChatView, {});
    await parkATurn();
    await waitFor(() => expect(streamResumeMock).toHaveBeenCalled());
    await new Promise((resolve) => setTimeout(resolve, 60));
    expect(streamResumeMock).toHaveBeenCalledTimes(1);
  });

  it("reports a turn another tab claimed first as continued, not as an error", async () => {
    stubFetch(baseRoutes({ "GET /api/approvals/resumable": { session_id: "sess_1", turns: [RESUMABLE] } }));
    const { ApiError } = await import("../api");
    streamResumeMock.mockRejectedValue(
      new ApiError(409, "suspended_turn_already_resumed", "conflict"),
    );
    render(ChatView, {});
    await parkATurn();
    expect(await screen.findByText("Continued in another tab")).toBeInTheDocument();
    expect(screen.queryByText(/could not continue/)).not.toBeInTheDocument();
  });

  // BUG-196 — every one of these used to render "The turn could not continue
  // (409)." directly beneath a turn that had completed, because the streaming
  // path discarded the reason code and the classifier knew one code.
  it("says nothing at all when the refusal lands on a turn that already finished", async () => {
    stubFetch(baseRoutes({ "GET /api/approvals/resumable": { session_id: "sess_1", turns: [RESUMABLE] } }));
    const { ApiError } = await import("../api");
    streamResumeMock.mockImplementation(
      async (_id: string, onEvent: (event: StreamEvent) => void) => {
        onEvent({
          kind: "final", text: "", event_type: "", payload: {},
          response: { ...PARKED, status: "completed", message: "Wrote notes.md.", approval: null },
        });
        // The poller's attempt loses the race *after* the answer has landed.
        throw new ApiError(409, "approval_not_resolved", "conflict");
      },
    );
    render(ChatView, {});
    await parkATurn();

    expect(await screen.findByText("Wrote notes.md.")).toBeInTheDocument();
    expect(screen.queryByText(/could not continue/)).not.toBeInTheDocument();
  });

  it("keeps waiting, without an error, when no decision has reached the runtime yet", async () => {
    stubFetch(baseRoutes({ "GET /api/approvals/resumable": { session_id: "sess_1", turns: [RESUMABLE] } }));
    const { ApiError } = await import("../api");
    streamResumeMock.mockRejectedValue(new ApiError(409, "approval_not_resolved", "conflict"));
    render(ChatView, {});
    await parkATurn();

    await waitFor(() => expect(streamResumeMock).toHaveBeenCalled());
    expect(screen.queryByText(/could not continue/)).not.toBeInTheDocument();
    expect(await screen.findByText("Waiting for approval")).toBeInTheDocument();
  });

  it("still says so when the parked state genuinely cannot be read", async () => {
    stubFetch(baseRoutes({ "GET /api/approvals/resumable": { session_id: "sess_1", turns: [RESUMABLE] } }));
    const { ApiError } = await import("../api");
    streamResumeMock.mockRejectedValue(
      new ApiError(409, "suspended_turn_unreadable", "conflict"),
    );
    render(ChatView, {});
    await parkATurn();

    expect(
      await screen.findByText("The turn could not continue (suspended_turn_unreadable)."),
    ).toBeInTheDocument();
  });

  it("offers Continue now when the live channel cannot be relied on", async () => {
    // No resumable route: the poll fails, so automatic continuation cannot be
    // promised and the manual path has to appear.
    stubFetch({
      "GET /api/models": {
        profiles: [READY_PROFILE],
        chat_profiles: [READY_PROFILE],
      },
      "GET /api/settings": { settings: {}, status: { vault: "ok", mfa_enrolled: false, username: "owner" } },
      "GET /api/sessions/sess_1/attachments": { session_id: "sess_1", files: [] },
    });
    render(ChatView, {});
    await parkATurn();
    expect(await screen.findByRole("button", { name: "Continue now" })).toBeInTheDocument();
    expect(screen.getByText(/cannot currently watch for a decision/)).toBeInTheDocument();
  });
});

describe("ChatView — conversation export (BUG-22)", () => {
  it("puts Export conversation and Print in the conversation menu", async () => {
    stubFetch(baseRoutes());
    render(ChatView, {});
    await fireEvent.click(await screen.findByRole("button", { name: "Conversation actions" }));
    expect(screen.getByRole("menuitem", { name: "Export conversation…" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Print / Save as PDF" })).toBeInTheDocument();
  });

  it("cannot export a conversation that has not started yet", async () => {
    stubFetch(baseRoutes());
    render(ChatView, {});
    await fireEvent.click(await screen.findByRole("button", { name: "Conversation actions" }));
    expect(screen.getByRole("menuitem", { name: "Export conversation…" })).toBeDisabled();
  });

  it("opens the export dialog once a conversation exists", async () => {
    stubFetch(
      baseRoutes({
        "GET /api/sessions/sess_1/export/manifest": {
          session_id: "sess_1",
          title: "Notes",
          created_at: null,
          message_count: 2,
          file_count: 0,
          files: [],
          redaction_policy: "Secret-shaped values are replaced with ***REDACTED***.",
          formats: ["html", "markdown", "pdf"],
          messages: [],
        },
      }),
    );
    render(ChatView, {});
    await parkATurn();
    await fireEvent.click(screen.getByRole("button", { name: "Conversation actions" }));
    await fireEvent.click(screen.getByRole("menuitem", { name: "Export conversation…" }));
    expect(await screen.findByRole("dialog", { name: "Export conversation" })).toBeInTheDocument();
    expect(await screen.findByText("What will be included")).toBeInTheDocument();
  });
});

// BUG-215 — a turn's own working was a stream fact and only a stream fact, so a
// re-opened conversation silently showed less than it had five minutes earlier.
describe("ChatView — retained reasoning (BUG-215)", () => {
  function reloadedTurn(extra: Record<string, unknown>) {
    return baseRoutes({
      "GET /api/sessions/sess_1": {
        session: { session_id: "sess_1", title: "Notes" },
        turns: [{
          turn_id: "turn_1", session_id: "sess_1", turn_type: "prompt",
          status: "completed", prompt_text: "Plan the migration",
          created_at: "2026-08-16T10:00:00Z", completed_at: "2026-08-16T10:00:05Z",
          summary: "Here is the plan.", ...extra,
        }],
      },
    });
  }

  it("shows the working a re-opened turn kept", async () => {
    stubFetch(reloadedTurn({ reasoning_chars: 31, reasoning: "Check the schema before writing." }));
    render(ChatView, { props: { sessionId: "sess_1" } });

    await screen.findByText("Here is the plan.");
    await fireEvent.click(screen.getByRole("button", { name: /Thinking/ }));
    expect(screen.getByText("Check the schema before writing.")).toBeInTheDocument();
  });

  it("says the working was not kept rather than showing nothing", async () => {
    stubFetch(reloadedTurn({ reasoning_chars: 420, reasoning: null }));
    render(ChatView, { props: { sessionId: "sess_1" } });

    await screen.findByText("Here is the plan.");
    expect(screen.getByText(/It was not kept/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Thinking/ })).not.toBeInTheDocument();
  });

  it("says nothing at all about a turn that never produced any working", async () => {
    stubFetch(reloadedTurn({ reasoning_chars: 0, reasoning: null }));
    render(ChatView, { props: { sessionId: "sess_1" } });

    await screen.findByText("Here is the plan.");
    expect(screen.queryByText(/It was not kept/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Thinking/ })).not.toBeInTheDocument();
  });
});
