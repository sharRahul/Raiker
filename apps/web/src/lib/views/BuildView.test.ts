// Behaviour coverage for the Build workspace. The claims worth guarding are the
// ones a user acts on: the composer mode must change what the runtime enforces
// for this conversation's turns — and, since BUG-70, must change *nothing*
// standing — a connected repository must actually ride the turn, a chat must
// reach the project it was filed under, and background work must be reachable
// and dismissible.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AgentResponse, CodeReposView, ProjectsList, StreamEvent } from "../apiTypes";
import { makeGate, stubFetch } from "../test-helpers";
import { resetModels } from "../models.svelte";

const streamPromptMock = vi.hoisted(() => vi.fn());
vi.mock("../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api")>();
  return { ...actual, streamPrompt: streamPromptMock };
});

import BuildView from "./BuildView.svelte";

class FakeRecognition {
  static instance: FakeRecognition;
  continuous = false;
  interimResults = false;
  lang = "";
  onresult: ((event: unknown) => void) | null = null;
  onerror: ((event: unknown) => void) | null = null;
  onend: (() => void) | null = null;
  constructor() { FakeRecognition.instance = this; }
  start() {}
  stop() { this.onend?.(); }
  abort() { this.onend?.(); }
  final(text: string) {
    this.onresult?.({ resultIndex: 0, results: [Object.assign([{ transcript: text }], { isFinal: true })] });
  }
}

afterEach(() => {
  vi.unstubAllGlobals();
  streamPromptMock.mockReset();
  resetModels();
});

const DEFAULT_READY_PROFILE = {
  profile_id: "test-ready", provider: "ollama", model: "test-model",
  selected: true, configured: true, ready: true, readiness_state: "ready",
};

const MODELS = {
  profiles: [DEFAULT_READY_PROFILE],
  chat_profiles: [DEFAULT_READY_PROFILE],
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

const REASONING_PROFILE = {
  profile_id: "openrouter-reasoning",
  provider: "openrouter",
  model: "reasoning-model",
  selected: true,
  configured: true,
  ready: true,
  readiness_state: "ready",
  supports_reasoning: true,
  supports_reasoning_effort: true,
  reasoning_effort_values: ["medium", "high"],
};

const ALT_REASONING_PROFILE = {
  ...REASONING_PROFILE,
  model: "opus-build-model",
  selected: false,
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

// The mode is one chip and one menu now (it was three side-by-side buttons), so
// choosing it is: open the chip, click the option. The trigger names the current
// posture, which is also how these tests assert what was chosen.
async function pickMode(label: string) {
  await fireEvent.click(
    await screen.findByRole("button", { name: /^How much Raiker may do this turn:/ }),
  );
  await fireEvent.click(await screen.findByRole("menuitemradio", { name: new RegExp(`^${label}`) }));
}

function modeTrigger() {
  return screen.getByRole("button", { name: /^How much Raiker may do this turn:/ });
}

describe("Build composer modes", () => {
  it("opens in Auto and sends no turn-scoped override for it", async () => {
    stubFetch(baseRoutes());
    respondWith("Done.");
    render(BuildView);

    expect(await screen.findByRole("button", {
      name: "How much Raiker may do this turn: Auto",
    })).toBeInTheDocument();

    await fireEvent.input(await screen.findByLabelText("Describe the change"), {
      target: { value: "Add a settings page" },
    });
    await fireEvent.click(screen.getByRole("button", { name: /^send$/i }));

    await waitFor(() => expect(streamPromptMock).toHaveBeenCalled());
    // Opening in Auto must widen nothing: no capability override and no planning
    // override, so the turn runs under exactly the owner's standing permissions.
    expect(streamPromptMock.mock.calls[0][0].capability_modes).toEqual({});
    expect(streamPromptMock.mock.calls[0][0].planning_mode).toBeUndefined();
  });

  it("is the Code-minimal composer: no Chat switch, no duplicate capacity chip", async () => {
    stubFetch(baseRoutes());
    render(BuildView);

    await screen.findByLabelText("Describe the change");
    expect(screen.queryByRole("group", { name: "Chat or Build" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Model context capacity")).not.toBeInTheDocument();
    // Build keeps the one badge that is about where the work runs.
    expect(screen.getByLabelText("Execution environment")).toBeInTheDocument();
  });


  it("keeps dictated text editable and sends it only after explicit Send", async () => {
    vi.stubGlobal("SpeechRecognition", FakeRecognition);
    stubFetch({ ...baseRoutes(), "GET /api/settings": { settings: { "general.speech_language": "en" }, status: { username: "Owner" } } });
    streamPromptMock.mockResolvedValue(undefined);
    render(BuildView);

    await fireEvent.click(await screen.findByRole("button", { name: "Dictate" }));
    FakeRecognition.instance.final("check the repository");
    await fireEvent.click(await screen.findByRole("button", { name: "Done dictating" }));
    expect(streamPromptMock).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Describe the change")).toHaveValue("check the repository");
    await fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(streamPromptMock.mock.calls[0][0]).toMatchObject({ input_mode: "dictated" });
  });

  it("does not retain dictated provenance after the owner cancels it", async () => {
    vi.stubGlobal("SpeechRecognition", FakeRecognition);
    stubFetch(baseRoutes());
    streamPromptMock.mockResolvedValue(undefined);
    render(BuildView);
    const prompt = await screen.findByLabelText("Describe the change");
    await fireEvent.input(prompt, { target: { value: "keep this" } });
    await fireEvent.click(screen.getByRole("button", { name: "Dictate" }));
    FakeRecognition.instance.final("discard this");
    await fireEvent.click(screen.getByRole("button", { name: "Cancel dictation" }));
    await fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(streamPromptMock.mock.calls[0][0]).toMatchObject({
      text: expect.stringContaining("keep this"),
      input_mode: "typed",
    });
  });

  it("offers manual read aloud beside Copy only after a Build answer completes", async () => {
    stubFetch(baseRoutes());
    respondWith("Build answer");
    render(BuildView);
    await fireEvent.input(await screen.findByLabelText("Describe the change"), { target: { value: "Plan it" } });
    await fireEvent.click(screen.getByRole("button", { name: /^send$/i }));

    expect(await screen.findByRole("button", { name: "Read aloud" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy response" })).toBeInTheDocument();
  });

  it("preserves the change and disables Send when the exact model is unready", async () => {
    const stopped = { ...REASONING_PROFILE, ready: false, readiness_state: "runtime_stopped", readiness_summary: "The local runtime is stopped.", readiness_reason_code: "local_runtime_unreachable", readiness_remediation: "Start it, then check again." };
    stubFetch(baseRoutes({ "GET /api/models": { ...MODELS, profiles: [stopped], chat_profiles: [stopped] } }));
    render(BuildView);
    const box = screen.getByLabelText("Describe the change");
    await fireEvent.input(box, { target: { value: "keep this change" } });
    await waitFor(() => expect(screen.getByRole("button", { name: /^send$/i })).toBeDisabled());
    expect(screen.getByText("The local runtime is stopped.")).toBeInTheDocument();
    expect(box).toHaveValue("keep this change");
  });
  it("changes no standing permission when a mode is picked", async () => {
    // BUG-70 — the whole defect. Pressing a chip used to POST four
    // `/api/capability-modes/<cap>/<mode>` changes: global, permanent, and
    // without the step-up the Permissions page demands for the same transition.
    // The mode is now this conversation's posture, so nothing standing is
    // written at all.
    const fetchMock = stubFetch(baseRoutes());
    render(BuildView);

    await pickMode("Plan");
    expect(modeTrigger()).toHaveAccessibleName("How much Raiker may do this turn: Plan");

    const written = fetchMock.mock.calls
      .map(([url]) => String(url))
      .filter((url) => url.includes("/api/capability-modes/"));
    expect(written).toEqual([]);
  });

  it("selects Auto without a dialog and without touching anything standing", async () => {
    // Auto was the sharpest case: it set four high-risk permissions to `auto`
    // with no confirmation. It now sends no override at all.
    const fetchMock = stubFetch(baseRoutes());
    render(BuildView);

    await pickMode("Auto");

    expect(modeTrigger()).toHaveAccessibleName("How much Raiker may do this turn: Auto");
    expect(
      fetchMock.mock.calls.map(([url]) => String(url)).filter((u) => u.includes("/api/capability-modes/")),
    ).toEqual([]);
  });

  it("tells the owner what Auto actually amounts to under their permissions", async () => {
    // With every write still at Ask, "low-risk changes run unprompted" would be
    // the same lie the old chip told — just in the other direction.
    stubFetch(baseRoutes({ "GET /api/capability-gates": gates("ask") }));
    render(BuildView);

    await pickMode("Auto");

    expect(await screen.findByText(/still be proposed/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /change in permissions/i })).toBeInTheDocument();
  });

  it("says it could not read the standing permissions rather than assuming them", async () => {
    stubFetch(baseRoutes({ "GET /api/capability-gates": undefined }));
    render(BuildView);

    await pickMode("Auto");

    expect(await screen.findByText(/could not read your standing permissions/i)).toBeInTheDocument();
  });

  it("states that the mode applies to this conversation only", async () => {
    stubFetch(baseRoutes());
    render(BuildView);

    await fireEvent.click(
      await screen.findByRole("button", { name: /^How much Raiker may do this turn:/ }),
    );

    const menu = screen.getByRole("menu", { name: "Mode" });
    expect(menu).toHaveTextContent(/applies to this conversation's turns only/i);
    expect(menu).toHaveTextContent(/raising a standing permission stays on the Permissions page/i);
  });

  it("sends the mode as a turn-scoped posture with the prompt", async () => {
    stubFetch(baseRoutes());
    respondWith("Here is the plan.");
    render(BuildView);

    await pickMode("Plan");
    await fireEvent.input(screen.getByLabelText("Describe the change"), {
      target: { value: "Add a settings page" },
    });
    await fireEvent.click(screen.getByRole("button", { name: /^send$/i }));

    await waitFor(() => expect(streamPromptMock).toHaveBeenCalled());
    expect(streamPromptMock.mock.calls[0][0]).toMatchObject({
      capability_modes: {
        file_write_execution: "deny",
        patch_apply_execution: "deny",
        shell_execution: "deny",
        process_execution: "deny",
      },
    });
  });

  it("sends no posture at all in Auto", async () => {
    stubFetch(baseRoutes());
    respondWith("Done.");
    render(BuildView);

    await pickMode("Auto");
    await fireEvent.input(screen.getByLabelText("Describe the change"), {
      target: { value: "Add a settings page" },
    });
    await fireEvent.click(screen.getByRole("button", { name: /^send$/i }));

    await waitFor(() => expect(streamPromptMock).toHaveBeenCalled());
    expect(streamPromptMock.mock.calls[0][0].capability_modes).toEqual({});
  });

  it("sends the turn with the planning option the mode carries", async () => {
    stubFetch(baseRoutes());
    respondWith("Here is the plan.");
    render(BuildView);

    await pickMode("Plan");
    await fireEvent.input(screen.getByLabelText("Describe the change"), {
      target: { value: "Add a settings page" },
    });
    await fireEvent.click(screen.getByRole("button", { name: /^send$/i }));

    await waitFor(() => expect(streamPromptMock).toHaveBeenCalled());
    expect(streamPromptMock.mock.calls[0][0]).toMatchObject({ planning_mode: "always" });
  });
});

describe("Build model picker", () => {
  it("shows the selected model and sends only an advertised thinking effort", async () => {
    stubFetch(baseRoutes({
      "GET /api/models": {
        ...MODELS,
        profiles: [REASONING_PROFILE],
        chat_profiles: [REASONING_PROFILE, ALT_REASONING_PROFILE],
      },
    }));
    respondWith("Done.");
    render(BuildView);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Model for this turn: Reasoning Model" })).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "Model for this turn: Reasoning Model" })).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Model for this turn: Reasoning Model" }));
    await fireEvent.click(screen.getByRole("menuitemradio", { name: /Opus Build Model/i }));
    // The thinking budget belongs to the model, so it is a section of the model
    // menu rather than a second dropdown beside it, and it offers only the
    // levels this exact model publishes.
    await fireEvent.click(screen.getByRole("button", { name: "Model for this turn: Opus Build Model" }));
    await fireEvent.click(screen.getByRole("button", { name: /^Effort/ }));
    const effortSection = screen.getByRole("group", { name: "Effort" });
    expect(
      within(effortSection)
        .getAllByRole("menuitemradio")
        .map((option) => option.textContent?.trim()),
    ).toEqual(["Medium", "High"]);
    await fireEvent.click(within(effortSection).getByRole("menuitemradio", { name: "High" }));
    expect(within(effortSection).getByRole("switch", { name: /Thinking/ })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await fireEvent.input(screen.getByLabelText("Describe the change"), { target: { value: "Use effort" } });
    await fireEvent.click(screen.getByRole("button", { name: /^send$/i }));

    await waitFor(() => expect(streamPromptMock).toHaveBeenCalled());
    expect(streamPromptMock.mock.calls[0][0]).toMatchObject({
      model_profile: "openrouter-reasoning",
      model: "opus-build-model",
      reasoning_effort: "high",
    });
  });

  it("calls an unavailable choice Not selected", async () => {
    stubFetch(baseRoutes({ "GET /api/models": { ...MODELS, profiles: [], chat_profiles: [] } }));
    render(BuildView);

    expect(await screen.findByRole("button", { name: "Model for this turn: Not selected" })).toBeInTheDocument();
    // No model means no published effort levels, so the Effort section is absent
    // rather than present and empty.
    await fireEvent.click(screen.getByRole("button", { name: "Model for this turn: Not selected" }));
    expect(screen.queryByRole("group", { name: "Effort" })).not.toBeInTheDocument();
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

  it("renders sent attachment cards outside the prompt bubble", async () => {
    stubFetch(baseRoutes());
    respondWith("Done.");
    render(BuildView);

    await fireEvent.click(screen.getByLabelText("Add attachment"));
    await fireEvent.input(screen.getByLabelText("Attachment path"), {
      target: { value: "docs/architecture/HANDOFF.md" },
    });
    await fireEvent.click(screen.getByText("Attach"));
    await fireEvent.input(screen.getByLabelText("Describe the change"), {
      target: { value: "Read the handoff" },
    });
    await fireEvent.click(screen.getByRole("button", { name: /^send$/i }));

    await waitFor(() => expect(streamPromptMock).toHaveBeenCalled());
    expect(screen.getByText("HANDOFF.md").closest(".from-you")).toBeNull();
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

    // The rail is collapsed by default; open it to view running work.
    await fireEvent.click(await screen.findByRole("button", { name: /background work/i }));
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

    // The rail is collapsed by default; open it to reach the agent form.
    await fireEvent.click(await screen.findByRole("button", { name: /background work/i }));
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

describe("Build transcript rendering", () => {
  // Build shows the same model prose as Chat, so the BUG-03 fix has to reach
  // it too — a plan full of code fences is exactly what this view produces.
  it("renders a markdown answer as real elements", async () => {
    stubFetch(baseRoutes());
    respondWith("## Plan\n\n1. Read the file\n2. Patch it\n\n```ts\nconst x = 1;\n```");
    render(BuildView);

    await fireEvent.input(await screen.findByLabelText("Describe the change"), {
      target: { value: "Plan the change" },
    });
    await fireEvent.click(screen.getByRole("button", { name: /^send$/i }));

    const answer = await waitFor(() => {
      const el = document.querySelector(".from-raiker .markdown");
      expect(el).not.toBeNull();
      return el as HTMLElement;
    });
    expect(answer.querySelectorAll("h2")).toHaveLength(1);
    expect(answer.querySelectorAll("ol > li")).toHaveLength(2);
    expect(answer.querySelector("pre code")?.textContent).toBe("const x = 1;");
    expect(answer.textContent).not.toContain("## Plan");
  });
});
