// B18 — rewind to before this turn, from the transcript.
//
// The governed restore has had an executor, a capability, a classification and
// a route since Workstream B, and BUG-230 gave it a caller. What it did not
// have was a way in from the place the work happens: to undo the turn that
// broke something the owner had to leave the conversation for the Checkpoints
// route, recognise the right snapshot by id, and come back. That is the same
// defect this codebase keeps finding — a capability built and never routed —
// and it is worse here than elsewhere, because "undo that turn" is the control
// that makes leaving an agent running reasonable at all.
//
// Three properties are held here, and each is a thing that must stay true no
// matter how the surface is redrawn:
//
//  * the rewind is taken from **this turn's own checkpoint**, not the latest;
//  * opening it **restores nothing** — it reads a metadata-only plan, and the
//    workspace changes only after an approval a human resolves;
//  * a turn with no checkpoint **says so** rather than offering a control that
//    would fail, or silently doing nothing.
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
  message: "Renamed the column and updated the two callers.",
  events_path: null,
  checkpoint_path: null,
  approval: null,
  last_event_id: null,
};

function checkpoint(id: string, turnId: string) {
  return {
    checkpoint_id: id,
    session_id: "session-chat",
    turn_id: turnId,
    task_id: null,
    checkpoint_type: "turn",
    created_at: "2026-08-29T10:00:00Z",
    summary: "before the rename",
    last_event_id: null,
    can_restore_state: true,
    can_restore_files: true,
  };
}

const PLAN = {
  status: "ok",
  checkpoint_id: "ckpt_here",
  session_id: "session-chat",
  checkpoint_created_at: "2026-08-29T10:00:00Z",
  can_execute: true,
  requires_approval: true,
  files: [
    {
      workspace_path: "db/schema.sql",
      op: "restore_content",
      pre_image_sha256: "aaa",
      pre_image_size: 120,
      current_sha256: "bbb",
      current_size: 132,
      changed: true,
      changed_by_other_principal: false,
    },
  ],
  restore_content_count: 1,
  delete_count: 0,
  skip_count: 0,
  changed_count: 1,
  touches_other_principal: false,
};

function routes(overrides: Record<string, unknown> = {}) {
  return {
    "GET /api/models": { profiles: [READY], chat_profiles: [READY] },
    "GET /api/tasks": [],
    ...overrides,
  };
}

async function sendOneTurn() {
  streamPromptMock.mockImplementation(
    async (_body: unknown, onEvent: (event: StreamEvent) => void) => {
      onEvent({
        kind: "final",
        text: RESPONSE.message,
        event_type: "",
        payload: {},
        response: RESPONSE,
      });
    },
  );
  await fireEvent.input(screen.getByLabelText("Prompt"), {
    target: { value: "Rename the column." },
  });
  await fireEvent.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "More actions for this message" }),
    ).toBeInTheDocument(),
  );
}

async function openRewind() {
  await fireEvent.click(screen.getByRole("button", { name: "More actions for this message" }));
  await fireEvent.click(screen.getByRole("menuitem", { name: /^Rewind to before this/ }));
}

describe("rewind from a turn", () => {
  it("previews this turn's own checkpoint and restores nothing", async () => {
    const fetchMock = stubFetch(
      routes({
        "GET /api/checkpoints": [
          checkpoint("ckpt_other", "turn-0"),
          checkpoint("ckpt_here", "turn-1"),
        ],
        "GET /api/checkpoints/ckpt_here/restore-plan": PLAN,
      }),
    );
    render(ChatView, { projects: null });
    await sendOneTurn();
    await openRewind();

    // The plan read is for this turn's checkpoint, not the newest one.
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) =>
          String(url).includes("/api/checkpoints/ckpt_here/restore-plan"),
        ),
      ).toBe(true),
    );
    expect(
      fetchMock.mock.calls.some(([url]) =>
        String(url).includes("/api/checkpoints/ckpt_other/restore-plan"),
      ),
    ).toBe(false);

    expect(await screen.findByText("db/schema.sql")).toBeInTheDocument();
    expect(
      screen.getByText(/computed from stored metadata and changed nothing/i),
    ).toBeInTheDocument();
    // Nothing was restored by opening it, and the ask is still withheld.
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url).includes("/restore") &&
          !String(url).includes("restore-plan") &&
          (init as RequestInit | undefined)?.method === "POST",
      ),
    ).toBe(false);
    expect(screen.getByRole("button", { name: /request this rewind/i })).toBeDisabled();
  });

  it("raises a governed approval and says nothing has changed yet", async () => {
    const fetchMock = stubFetch(
      routes({
        "GET /api/checkpoints": [checkpoint("ckpt_here", "turn-1")],
        "GET /api/checkpoints/ckpt_here/restore-plan": PLAN,
        "POST /api/checkpoints/ckpt_here/restore": {
          status: "approval_required",
          approval_id: "appr_rewind_1",
          action_id: "act_1",
          checkpoint_id: "ckpt_here",
          critical: false,
          executes_action: false,
          restore_content_count: 1,
          delete_count: 0,
          skip_count: 0,
        },
      }),
    );
    render(ChatView, { projects: null });
    await sendOneTurn();
    await openRewind();

    await screen.findByText("db/schema.sql");
    await fireEvent.click(screen.getByLabelText(/i have read what this would change/i));
    await fireEvent.click(screen.getByRole("button", { name: /request this rewind/i }));

    expect(await screen.findByText(/nothing has changed yet/i)).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url).endsWith("/api/checkpoints/ckpt_here/restore") &&
          (init as RequestInit | undefined)?.method === "POST",
      ),
    ).toBe(true);
  });

  it("says there is nothing to rewind to rather than offering a control that would fail", async () => {
    stubFetch(routes({ "GET /api/checkpoints": [] }));
    render(ChatView, { projects: null });
    await sendOneTurn();
    await openRewind();

    expect(
      await screen.findByText(/no checkpoint was written for that turn/i),
    ).toBeInTheDocument();
  });
});
