// Behaviour coverage for the Build workspace. The claims worth guarding are the
// ones a user acts on: the composer mode must change what the runtime enforces
// (not just the label), a connected repository must actually ride the turn, a
// chat must reach the project it was filed under, and background work must be
// reachable and dismissible.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AgentResponse, CodeReposView, ProjectsList, StreamEvent } from "../apiTypes";
import { makeGate, stubFetch, stubFetchPending } from "../test-helpers";

const streamPromptMock = vi.hoisted(() => vi.fn());
vi.mock("../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api")>();
  return { ...actual, streamPrompt: streamPromptMock };
});

import BuildView from "./BuildView.svelte";

afterEach(() => {
  vi.unstubAllGlobals();
  streamPromptMock.mockReset();
});

const MODELS = {
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
};

const WRITE_CAPABILITIES = [
  "file_write_execution",
  "patch_apply_execution",
  "shell_execution",
  "process_execution",
];

function gates(decisionMode: string) {
  return WRITE_CAPABILITIES.map((capability) => makeGate({ capability, decision_mode: decisionMode }));
}

function reposView(partial: Partial<CodeReposView> = {}): CodeReposView {
  return {
    repos: [],
    selected_repo_id: null,
    github_gate_state: "enabled_runtime",
    github_decision_mode: "ask",
    github_token_configured: false,
    note: "References only.",
    ...partial,
  };
}

const LOCAL_REPO = {
  repo_id: "repo_local",
  kind: "local" as const,
  label: "my-app",
  selected: true,
  created_at: "2026-07-20T00:00:00Z",
  local_subpath: "projects/my-app",
  local_exists: true,
  github_owner: null,
  github_repo: null,
  branch: null,
};

const GITHUB_REPO = {
  repo_id: "repo_gh",
  kind: "github" as const,
  label: "octo/app",
  selected: true,
  created_at: "2026-07-20T00:00:00Z",
  local_subpath: null,
  local_exists: false,
  github_owner: "octo",
  github_repo: "app",
  branch: "main",
};

function baseRoutes(overrides: Record<string, unknown> = {}) {
  return {
    "GET /api/models": MODELS,
    "GET /api/capability-gates": gates("ask"),
    "GET /api/code/repos": reposView(),
    "GET /api/tasks": [],
    ...overrides,
  };
}

function finalResponse(message: string): AgentResponse {
  return {
    request_id: "req_1",
    session_id: "sess_build",
    turn_id: "turn_1",
    status: "completed",
    message,
    events_path: null,
    checkpoint_path: null,
    approval: null,
    last_event_id: "evt_1",
  } as AgentResponse;
}

/** Resolve a stream immediately with one text delta and a final response. */
function respondWith(message: string) {
  streamPromptMock.mockImplementation(async (_body: unknown, onEvent: (ev: StreamEvent) => void) => {
    onEvent({ kind: "text_delta", text: message, event_type: "", payload: {}, response: null } as StreamEvent);
    onEvent({ kind: "final", text: "", event_type: "", payload: {}, response: finalResponse(message) } as StreamEvent);
  });
}

describe("Build composer modes", () => {
  it("applies the mode to every write capability, not just the label", async () => {
    // The point of the control: choosing Plan sets the runtime's decision modes
    // to deny, so a write proposed anyway is blocked by the runtime.
    const fetchMock = stubFetch({
      ...baseRoutes(),
      "POST /api/capability-modes/file_write_execution/deny": { ok: true },
      "POST /api/capability-modes/patch_apply_execution/deny": { ok: true },
      "POST /api/capability-modes/shell_execution/deny": { ok: true },
      "POST /api/capability-modes/process_execution/deny": { ok: true },
    });
    render(BuildView);

    await fireEvent.click(await screen.findByRole("button", { name: "Plan" }));

    await waitFor(() => {
      const denied = fetchMock.mock.calls
        .map(([url]) => String(url))
        .filter((url) => url.includes("/api/capability-modes/") && url.endsWith("/deny"));
      expect(denied).toHaveLength(WRITE_CAPABILITIES.length);
    });
    expect(await screen.findByRole("button", { name: "Plan" })).toHaveAttribute("aria-pressed", "true");
  });

  it("reverts the shown mode when the runtime refuses the change", async () => {
    // Showing "Auto" over a posture the server rejected would be a lie about
    // what the agent may do next.
    stubFetch(baseRoutes());
    render(BuildView);
    await screen.findByRole("button", { name: "Edit" });

    await fireEvent.click(screen.getByRole("button", { name: "Auto" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/did not accept that mode|gate-manager/i);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Edit" })).toHaveAttribute("aria-pressed", "true");
    });
  });

  it("adopts the posture already set on the runtime", async () => {
    stubFetch(baseRoutes({ "GET /api/capability-gates": gates("deny") }));
    render(BuildView);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Plan" })).toHaveAttribute("aria-pressed", "true");
    });
  });

  it("says the posture is set individually rather than claiming a mode", async () => {
    const mixed = gates("ask");
    mixed[0] = makeGate({ capability: WRITE_CAPABILITIES[0], decision_mode: "deny" });
    stubFetch(baseRoutes({ "GET /api/capability-gates": mixed }));
    render(BuildView);

    expect(await screen.findByText(/set individually right now/i)).toBeInTheDocument();
  });

  it("says the posture could not be read rather than implying the mode is in effect", async () => {
    // A failed read is not the same as a mixed posture, and neither is the same
    // as "Edit is active" — the composer must not claim the last one.
    stubFetch(baseRoutes({ "GET /api/capability-gates": undefined }));
    render(BuildView);

    expect(await screen.findByText(/could not read the current write permissions/i)).toBeInTheDocument();
  });

  it("stays quiet about the posture while the first read is in flight", async () => {
    // Flashing "permissions are set individually" at everyone on load would
    // describe a state that is merely unknown yet.
    stubFetchPending();
    render(BuildView);

    expect(screen.queryByText(/set individually right now/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/could not read the current write permissions/i)).not.toBeInTheDocument();
  });

  it("sends the turn with the planning option the mode carries", async () => {
    stubFetch({
      ...baseRoutes(),
      "POST /api/capability-modes/file_write_execution/deny": { ok: true },
      "POST /api/capability-modes/patch_apply_execution/deny": { ok: true },
      "POST /api/capability-modes/shell_execution/deny": { ok: true },
      "POST /api/capability-modes/process_execution/deny": { ok: true },
    });
    respondWith("Here is the plan.");
    render(BuildView);

    await fireEvent.click(await screen.findByRole("button", { name: "Plan" }));
    await fireEvent.input(screen.getByLabelText("Describe the change"), {
      target: { value: "Add a settings page" },
    });
    await fireEvent.click(screen.getByRole("button", { name: /^send$/i }));

    await waitFor(() => expect(streamPromptMock).toHaveBeenCalled());
    expect(streamPromptMock.mock.calls[0][0]).toMatchObject({ planning_mode: "always" });
  });
});

describe("Build repository context", () => {
  it("attaches a local repository's path so the turn is bounded to it", async () => {
    stubFetch(baseRoutes({ "GET /api/code/repos": reposView({ repos: [LOCAL_REPO], selected_repo_id: "repo_local" }) }));
    respondWith("Done.");
    render(BuildView);

    await screen.findByRole("button", { name: /my-app/ });
    await fireEvent.input(screen.getByLabelText("Describe the change"), { target: { value: "Rename the header" } });
    await fireEvent.click(screen.getByRole("button", { name: /^send$/i }));

    await waitFor(() => expect(streamPromptMock).toHaveBeenCalled());
    expect(streamPromptMock.mock.calls[0][0].attachments).toEqual([
      { type: "path", path: "projects/my-app" },
    ]);
  });

  it("states a GitHub coordinate in the prompt the user can see", async () => {
    // The preamble is prepended in the browser rather than injected server-side
    // precisely so the transcript shows what was actually sent.
    stubFetch(baseRoutes({ "GET /api/code/repos": reposView({ repos: [GITHUB_REPO], selected_repo_id: "repo_gh" }) }));
    respondWith("Done.");
    render(BuildView);

    await screen.findByRole("button", { name: /octo\/app/ });
    await fireEvent.input(screen.getByLabelText("Describe the change"), { target: { value: "Summarise the README" } });
    await fireEvent.click(screen.getByRole("button", { name: /^send$/i }));

    await waitFor(() => expect(streamPromptMock).toHaveBeenCalled());
    expect(streamPromptMock.mock.calls[0][0].text).toBe(
      "Repository: octo/app (branch main).\n\nSummarise the README",
    );
    expect(streamPromptMock.mock.calls[0][0].attachments).toBeUndefined();
    expect(await screen.findByText(/Repository: octo\/app \(branch main\)/)).toBeInTheDocument();
  });

  it("warns when a connected local folder is no longer in the workspace", async () => {
    stubFetch(
      baseRoutes({
        "GET /api/code/repos": reposView({
          repos: [{ ...LOCAL_REPO, local_exists: false }],
          selected_repo_id: "repo_local",
        }),
      }),
    );
    render(BuildView);

    expect(await screen.findByText(/no longer in the workspace/i)).toBeInTheDocument();
  });

  it("says GitHub reads stay closed when the connector gate is off", async () => {
    stubFetch(
      baseRoutes({
        "GET /api/code/repos": reposView({
          repos: [GITHUB_REPO],
          selected_repo_id: "repo_gh",
          github_gate_state: "disabled",
        }),
      }),
    );
    render(BuildView);

    await fireEvent.click(await screen.findByRole("button", { name: /octo\/app/ }));
    const panel = await screen.findByRole("region", { name: "Repositories" });
    expect(within(panel).getByText(/reads are closed/i)).toBeInTheDocument();
  });
});

describe("Build project filing", () => {
  const PROJECTS: ProjectsList = {
    projects: [
      {
        project_id: "proj_1",
        name: "Landing page",
        root_subpath: "projects/landing-page",
        created_at: "2026-07-01T00:00:00Z",
        session_count: 0,
        selected: false,
      },
    ],
    active_project_id: null,
  } as ProjectsList;

  it("files the chat as soon as the first turn creates a session", async () => {
    // Choosing a project before the chat exists must not silently do nothing.
    const fetchMock = stubFetch({
      ...baseRoutes(),
      "PUT /api/sessions/sess_build/project": { ok: true, session_id: "sess_build", project_id: "proj_1" },
      "GET /api/approvals": [],
    });
    respondWith("Done.");
    render(BuildView, { props: { projects: PROJECTS } });

    await fireEvent.change(await screen.findByLabelText("Project for this chat"), {
      target: { value: "proj_1" },
    });
    expect(await screen.findByText(/filed there as soon as it starts/i)).toBeInTheDocument();

    await fireEvent.input(screen.getByLabelText("Describe the change"), { target: { value: "Start" } });
    await fireEvent.click(screen.getByRole("button", { name: /^send$/i }));

    await waitFor(() => {
      const moved = fetchMock.mock.calls.some(([url]) =>
        String(url).includes("/api/sessions/sess_build/project"),
      );
      expect(moved).toBe(true);
    });
  });
});

describe("Build background work rail", () => {
  it("shows running background work and hides on the toggle", async () => {
    stubFetch(
      baseRoutes({
        "GET /api/tasks": [
          {
            task_id: "task_1",
            session_id: "sess_inbox",
            status: "running",
            title: "Keep improving the site",
            objective: "One improvement per cycle",
            current_step: "Reviewing contrast",
            progress_percent: 40,
            created_at: "2026-07-20T00:00:00Z",
            updated_at: "2026-07-20T00:05:00Z",
            completed_at: null,
            summary: null,
            recurrence: "continuous",
            project_id: null,
          },
        ],
      }),
    );
    render(BuildView);

    const rail = await screen.findByRole("complementary", { name: "Background work" });
    expect(await within(rail).findByText("Keep improving the site")).toBeInTheDocument();
    expect(within(rail).getByText(/Keeps going until stopped/)).toBeInTheDocument();

    await fireEvent.click(within(rail).getByRole("button", { name: "Hide background work" }));
    await waitFor(() => {
      expect(screen.queryByRole("complementary", { name: "Background work" })).not.toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /background work/i })).toHaveAttribute("aria-expanded", "false");
  });

  it("schedules a standing agent through the governed task surface", async () => {
    const fetchMock = stubFetch({
      ...baseRoutes(),
      "POST /api/tasks": { task_id: "task_new" },
    });
    render(BuildView);

    const rail = await screen.findByRole("complementary", { name: "Background work" });
    await fireEvent.click(within(rail).getByRole("tab", { name: "Agents" }));
    await fireEvent.click(within(rail).getByRole("button", { name: /surprise me by building a small app/i }));
    const schedule = within(rail).getByRole("button", { name: "Schedule agent" });
    await waitFor(() => expect(schedule).not.toBeDisabled());
    await fireEvent.click(schedule);

    await waitFor(() => {
      const created = fetchMock.mock.calls.find(
        ([url, init]) => String(url).endsWith("/api/tasks") && init?.method === "POST",
      );
      expect(created).toBeDefined();
      expect(JSON.parse(String(created?.[1]?.body))).toMatchObject({
        title: "Surprise me",
        recurrence: "continuous",
      });
    });
  });
});
