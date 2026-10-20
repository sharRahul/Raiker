// PA-D02 — Settings is the only place a profile is made, changed or activated.
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import ExecutionProfiles from "./ExecutionProfiles.svelte";
import { stubFetch } from "../../test-helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const TEMPLATES = [
  { template: "private_local", name: "Private local", summary: "Only models on this machine.", allow_local: true, allow_hosted: false, memory_to_hosted: false },
  { template: "balanced", name: "Balanced", summary: "Local and hosted.", allow_local: true, allow_hosted: true, memory_to_hosted: false },
];
const PROFILE = {
  profile_id: "xprof_1", version: 2, name: "Private local", template: "private_local", allow_local: true, allow_hosted: false,
  allowed_providers: [], memory_to_hosted: false, max_step_runs: 10, max_cost_usd: null, created_at: "",
};

describe("ExecutionProfiles", () => {
  it("says goals cannot be accepted before a profile exists, and creates one from a template", async () => {
    const fetch = stubFetch({
      "GET /api/execution-profiles": { profiles: [], templates: TEMPLATES, active_profile_id: null, project_bindings: [] },
      "GET /api/projects": { projects: [], active_project_id: null },
      "POST /api/execution-profiles": { ok: true, profile: PROFILE, goals_paused: 0 },
    });
    render(ExecutionProfiles);
    expect(await screen.findByText(/Goals can be drafted, but not accepted/)).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Create Private local" }));
    await waitFor(() => expect(screen.getByText("Created Private local.")).toBeInTheDocument());
    const post = fetch.mock.calls.find(([, init]) => (init as RequestInit | undefined)?.method === "POST");
    expect(JSON.parse(String((post?.[1] as RequestInit).body))).toEqual({ template: "private_local" });
  });

  it("marks the active profile, states its boundary and says a change pauses running goals", async () => {
    stubFetch({
      "GET /api/execution-profiles": { profiles: [PROFILE], templates: TEMPLATES, active_profile_id: "xprof_1", project_bindings: [] },
      "GET /api/projects": { projects: [], active_project_id: null },
      "PUT /api/execution-profiles/xprof_1": { ok: true, profile: { ...PROFILE, version: 3 }, goals_paused: 1 },
    });
    render(ExecutionProfiles);
    expect(await screen.findByText("Active")).toBeInTheDocument();
    expect(screen.getByText(/Only models on this machine; nothing leaves this machine/)).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    await fireEvent.click(screen.getByRole("button", { name: "Save as version 3" }));
    await waitFor(() => expect(screen.getByText(/1 running goal was paused/)).toBeInTheDocument());
  });
});
