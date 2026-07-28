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
  return {
    "GET /api/models": { profiles: [], chat_profiles: [] },
    "GET /api/tasks": [],
    "PUT /api/sessions/session-chat/project": { ok: true, session_id: "session-chat", project_id: "project-1" },
  };
}

describe("ChatView composer parity", () => {
  it("renders the inline work panel and approval pill beside the project picker", async () => {
    stubFetch(routes());
    render(ChatView, { projects });

    expect(await screen.findByRole("complementary", { name: "Background work" })).toBeInTheDocument();
    expect(screen.getByLabelText("Project for this chat")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /approval mode/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Context window" })).toBeInTheDocument();
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
