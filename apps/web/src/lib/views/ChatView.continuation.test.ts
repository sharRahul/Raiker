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
});

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
    "GET /api/models": { profiles: [], chat_profiles: [] },
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
  it("shows a parked turn as Waiting for approval", async () => {
    stubFetch(baseRoutes());
    render(ChatView, {});
    await parkATurn();
    expect(screen.getByText("Raiker wants to write notes.md")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Review approval" })).toBeInTheDocument();
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

  it("offers Continue now when the live channel cannot be relied on", async () => {
    // No resumable route: the poll fails, so automatic continuation cannot be
    // promised and the manual path has to appear.
    stubFetch({
      "GET /api/models": { profiles: [], chat_profiles: [] },
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
