// The Workbench is the default screen and the start of the common journey. Its
// composer must carry its own scope (session, project, model) and must hand the
// prompt to the one governed send path rather than calling the API itself.
import { render, screen, waitFor } from "@testing-library/svelte";
import { fireEvent } from "@testing-library/dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import WorkbenchView from "./WorkbenchView.svelte";
import { stubFetch, stubFetchPending } from "../test-helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
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
  it("shows a loading state for live status before it is known", async () => {
    stubFetchPending();
    render(WorkbenchView);
    expect(await screen.findByText(/loading status/i)).toBeInTheDocument();
  });

  it("says status is unavailable rather than reporting zeroes", async () => {
    stubFetch({});
    render(WorkbenchView);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/workbench status is unavailable/i);
    expect(alert).toHaveTextContent(/no work was started or changed/i);
  });

  it("names the project scope and the model that will serve the turn", async () => {
    stubFetch(routes());
    render(WorkbenchView);

    await waitFor(() => expect(screen.getByText("Quarterly note")).toBeInTheDocument());
    expect(await screen.findByText("local-default · qwen2.5")).toBeInTheDocument();
    expect(screen.getByText(/runs locally — the turn stays on this machine/i)).toBeInTheDocument();
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
    await waitFor(() =>
      expect(screen.getByText(/the turn leaves your device/i)).toBeInTheDocument(),
    );
  });

  it("says no model is selected instead of implying one is ready", async () => {
    stubFetch(routes({ "GET /api/models": { profiles: [] } }));
    render(WorkbenchView);
    await waitFor(() =>
      expect(screen.getByText(/no model is selected yet/i)).toBeInTheDocument(),
    );
  });

  it("hands the prompt to the governed chat send path instead of posting it", async () => {
    vi.useFakeTimers();
    const fetchMock = stubFetch(routes());
    const composed = vi.fn();
    window.addEventListener("raiker:compose", composed);
    render(WorkbenchView);

    await vi.waitFor(() => expect(screen.getByLabelText(/what would you like to do/i)).toBeInTheDocument());
    await fireEvent.input(screen.getByLabelText(/what would you like to do/i), {
      target: { value: "Summarise the open approvals" },
    });
    await fireEvent.click(screen.getByRole("button", { name: /start work/i }));
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

    // Wait for the saved conversation to become a real option — selecting a
    // value a <select> does not yet offer would silently leave it empty.
    await vi.waitFor(() =>
      expect(screen.getByRole("option", { name: SESSION.title })).toBeInTheDocument(),
    );
    await fireEvent.change(screen.getByLabelText(/conversation to continue/i), {
      target: { value: "sess_1" },
    });
    await fireEvent.input(screen.getByLabelText(/what would you like to do/i), {
      target: { value: "Continue from here" },
    });
    await fireEvent.click(screen.getByRole("button", { name: /start work/i }));
    vi.runAllTimers();

    expect((composed.mock.calls[0][0] as CustomEvent).detail.sessionId).toBe("sess_1");
    window.removeEventListener("raiker:compose", composed);
  });

  it("keeps the start control disabled until something is written", async () => {
    stubFetch(routes());
    render(WorkbenchView);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /start work/i })).toBeDisabled(),
    );
  });
});
