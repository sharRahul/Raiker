// The Workbench is the default screen and the start of the common journey. Its
// composer must carry its own scope (session, project, model) and must hand the
// prompt to the one governed send path rather than calling the API itself.
import { render, screen, waitFor } from "@testing-library/svelte";
import { fireEvent } from "@testing-library/dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import WorkbenchView from "./WorkbenchView.svelte";
import { stubFetch, stubFetchPending } from "../test-helpers";
import { resetModels } from "../models.svelte";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  resetModels();
});

const SESSION = {
  session_id: "sess_1",
  title: "Draft the quarterly note",
  status: "active",
  created_at: "2026-07-20T00:00:00Z",
  updated_at: "2026-07-24T00:00:00Z",
  turn_count: 3,
  pinned: false,
  tags: [],
};

const LOCAL_PROFILE = {
  profile_id: "local-default",
  provider: "ollama",
  model: "qwen2.5",
  default_state: "enabled",
  local_only: true,
  requires_network: false,
  endpoint_kind: "loopback",
  requires_egress_policy: false,
  requires_budget_policy: false,
  runtime_gate: null,
  off_machine: false,
  selected: true,
  configured: true,
};

function routes(overrides: Record<string, unknown> = {}) {
  return {
    "GET /api/sessions": [SESSION],
    "GET /api/tasks": [],
    "GET /api/approvals": [],
    "GET /api/projects": {
      projects: [
        {
          project_id: "proj_1",
          name: "Quarterly note",
          root_subpath: "projects/quarterly-note",
          created_at: "2026-07-01T00:00:00Z",
          session_count: 1,
          selected: true,
          parent_id: null,
          path: "/",
          is_archived: false,
          archived_at: null,
        },
      ],
      active_project_id: "proj_1",
    },
    "GET /api/models": { profiles: [LOCAL_PROFILE] },
    ...overrides,
  };
}

describe("WorkbenchView", () => {
  it("counts each actionable runtime configuration gap once", async () => {
    stubFetch(routes({
      "GET /api/diagnostics": {
        missing_config: ["No model profile is selected.", "No runtime mode is active."],
        production_ready_local_single_user_runtime: false,
      },
    }));
    render(WorkbenchView);

    const tile = (await screen.findByText("Runtime issues")).closest("article");
    await waitFor(() => expect(tile).toHaveTextContent("2"));
    expect(tile).not.toHaveTextContent("3");
  });

  it("shows a loading state for live status before it is known", async () => {
    stubFetchPending();
    render(WorkbenchView);
    expect(await screen.findByText(/loading status/i)).toBeInTheDocument();
  });

  it("says status is unavailable rather than reporting zeroes", async () => {
    stubFetch({});
    render(WorkbenchView);
    const alert = await screen.findByText(/workbench status is unavailable/i);
    expect(alert).toHaveTextContent(/workbench status is unavailable/i);
    expect(screen.getByText(/no work was started or changed/i)).toBeInTheDocument();
  });

  it("names the project scope and the model that will serve the turn", async () => {
    stubFetch(routes());
    render(WorkbenchView);

    await waitFor(() => expect(screen.getByText("Quarterly note")).toBeInTheDocument());
    expect(await screen.findByRole("button", { name: /model for this turn: qwen 2.5/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Build" })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Run work" })).not.toBeInTheDocument();
  });

  it("labels a hosted model as leaving the machine", async () => {
    stubFetch(
      routes({
        "GET /api/models": {
          profiles: [
            { ...LOCAL_PROFILE, profile_id: "hosted", provider: "anthropic", off_machine: true },
          ],
        },
      }),
    );
    render(WorkbenchView);
    await fireEvent.click(await screen.findByRole("button", { name: /model for this turn: qwen/i }));
    expect(screen.getByRole("group", { name: /anthropic models/i })).toBeInTheDocument();
  });

  it("says no model is selected instead of implying one is ready", async () => {
    stubFetch(routes({ "GET /api/models": { profiles: [] } }));
    render(WorkbenchView);
    await waitFor(() =>
      expect(screen.getByText(/a model is required before work can start/i)).toBeInTheDocument(),
    );
  });

  it("hands the prompt to the governed chat send path instead of posting it", async () => {
    vi.useFakeTimers();
    const fetchMock = stubFetch(routes());
    const composed = vi.fn();
    window.addEventListener("raiker:compose", composed);
    render(WorkbenchView);

    await vi.waitFor(() => expect(screen.getByLabelText(/what would you like raiker to do/i)).toBeInTheDocument());
    await fireEvent.click(screen.getByRole("tab", { name: "Chat" }));
    await fireEvent.input(screen.getByLabelText(/what would you like raiker to do/i), {
      target: { value: "Summarise the open approvals" },
    });
    await vi.waitFor(() => expect(screen.getByRole("button", { name: /start conversation/i })).toBeEnabled());
    await fireEvent.click(screen.getByRole("button", { name: /start conversation/i }));
    vi.runAllTimers();

    expect(composed).toHaveBeenCalledTimes(1);
    const detail = (composed.mock.calls[0][0] as CustomEvent).detail;
    expect(detail.text).toBe("Summarise the open approvals");
    expect(detail.sessionId).toBeNull();
    // The Workbench must not be a second send path.
    expect(
      fetchMock.mock.calls.some(([input]) => String(input).includes("/api/prompts")),
    ).toBe(false);
    window.removeEventListener("raiker:compose", composed);
  });

  it("continues the chosen conversation when one is selected", async () => {
    vi.useFakeTimers();
    stubFetch(routes());
    const composed = vi.fn();
    window.addEventListener("raiker:compose", composed);
    render(WorkbenchView);
    await fireEvent.click(await screen.findByRole("tab", { name: "Chat" }));

    // Wait for the saved conversation to become a real option — selecting a
    // value a <select> does not yet offer would silently leave it empty.
    await vi.waitFor(() =>
      expect(screen.getByRole("option", { name: SESSION.title })).toBeInTheDocument(),
    );
    await fireEvent.change(screen.getByLabelText(/conversation to continue/i), {
      target: { value: "sess_1" },
    });
    await fireEvent.input(screen.getByLabelText(/what would you like raiker to do/i), {
      target: { value: "Continue from here" },
    });
    await fireEvent.click(screen.getByRole("button", { name: /start conversation/i }));
    vi.runAllTimers();

    expect((composed.mock.calls[0][0] as CustomEvent).detail.sessionId).toBe("sess_1");
    window.removeEventListener("raiker:compose", composed);
  });

  it("hands Build its own exact provider and model choice", async () => {
    vi.useFakeTimers();
    stubFetch(routes({
      "GET /api/models": {
        profiles: [LOCAL_PROFILE],
        chat_profiles: [
          LOCAL_PROFILE,
          { ...LOCAL_PROFILE, profile_id: "anthropic", provider: "anthropic", model: "opus", selected: false },
        ],
      },
    }));
    const composed = vi.fn();
    window.addEventListener("raiker:build-compose", composed);
    render(WorkbenchView);

    await fireEvent.click(await screen.findByRole("button", { name: /model for this turn: qwen/i }));
    await fireEvent.click(screen.getByRole("menuitemradio", { name: /opus/i }));
    await fireEvent.input(screen.getByLabelText(/what would you like raiker to do/i), { target: { value: "Build the release" } });
    await fireEvent.click(screen.getByRole("button", { name: /start build/i }));
    vi.runAllTimers();

    expect((composed.mock.calls[0][0] as CustomEvent).detail).toMatchObject({
      profileId: "anthropic",
      model: "opus",
    });
    window.removeEventListener("raiker:build-compose", composed);
  });

  it("keeps Schedule on the global model resolved at run time", async () => {
    stubFetch(routes());
    render(WorkbenchView);
    await fireEvent.click(await screen.findByRole("tab", { name: "Schedule" }));
    expect(screen.getByText(/global at run time/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /model for this turn/i })).not.toBeInTheDocument();
  });

  it("keeps the start control disabled until something is written", async () => {
    stubFetch(routes());
    render(WorkbenchView);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /start build/i })).toBeDisabled(),
    );
  });
});
