/**
 * Settings → Connections → GitHub (ADD-27 GH-19).
 *
 * The six states are shown apart, never as one "Connected" light; sign-in shows
 * the code to enter and cancels cleanly; methods are offered only as found on
 * this machine; a delegation names what it allows and can be revoked; merging is
 * never offered as delegable.
 */
import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import GitHubConnection from "./GitHubConnection.svelte";
import { stubFetch } from "../../test-helpers";

const RISKS = [
  { operation: "read", label: "Read a repository (local)", risk: "low", default: "allowed", delegable: true, capability: null },
  { operation: "push", label: "Push a branch", risk: "high", default: "ask", delegable: true, capability: "git_push_execution" },
  { operation: "pull_request", label: "Open or update a pull request", risk: "high", default: "ask", delegable: true, capability: "connector_github_runtime" },
  { operation: "merge", label: "Merge a pull request", risk: "critical", default: "ask_every_time", delegable: false, capability: null },
];

const CREDENTIAL = {
  credential_id: "gcred_1", method: "app_user", label: "GitHub sign-in", account_login: "octo",
  account_id: "101", status: "active", selected: true, usable: true,
  expires_at: null, validated_at: "2026-10-12T10:00:00Z", last_error: null,
};

function connection(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    states: {
      connected_account: false, application_installed: false, repository_authorised: false,
      credential_available: false, capability_enabled: false, operation_approved: false,
    },
    selected: null, credentials: [], device_sign_in: true, browser_sign_in: false,
    apps: [], installations: [], repositories: [], delegations: [], risks: RISKS,
    checked_at: "2026-10-12T10:00:00Z",
    ...overrides,
  };
}

const GIT_STATUS = {
  credential_configured: false, credential_source: "none", credential_method: null, credential_id: null,
  account_login: null, grant: null, last_used: null, scopes: ["once", "session"],
  grant_seconds: { once: 300, session: 3600 }, hosts: ["github.com"], operations: ["Push"], checked_at: "x",
};

afterEach(() => vi.useRealTimers());

describe("Settings → GitHub", () => {
  it("shows the six states separately, never one Connected light", async () => {
    stubFetch({ "GET /api/github": connection(), "GET /api/git-credential": GIT_STATUS });
    render(GitHubConnection);
    const states = await screen.findByTestId("github-states");
    for (const label of ["GitHub account", "Raiker app", "Repositories", "Credential", "Capability", "Approval"]) {
      expect(within(states).getByText(label)).toBeInTheDocument();
    }
    expect(screen.queryByText(/^Connected$/)).toBeNull();
    expect(within(states).getByText("Each use asks")).toBeInTheDocument();
  });

  it("shows the device code to enter, and cancelling connects nothing", async () => {
    const fetch = stubFetch({
      "GET /api/github": connection(),
      "GET /api/git-credential": GIT_STATUS,
      "POST /api/github/sign-in": {
        attempt_id: "ghauth_1", method: "device", outcome: "pending", reason: null, user_code: "WDJB-MJHT",
        verification_uri: "https://github.com/login/device", authorize_url: null,
        expires_at: "2099-01-01T00:00:00Z", next_poll_at: "2099-01-01T00:00:00Z", credential_id: null,
      },
      "POST /api/github/sign-in/ghauth_1/cancel": {
        attempt_id: "ghauth_1", method: "device", outcome: "cancelled", reason: "cancelled_by_owner", user_code: null,
        verification_uri: null, authorize_url: null, expires_at: "2099-01-01T00:00:00Z", next_poll_at: null, credential_id: null,
      },
    });
    render(GitHubConnection);
    await fireEvent.click(await screen.findByRole("button", { name: "Connect GitHub" }));
    const box = await screen.findByTestId("github-device-code");
    expect(within(box).getByText("WDJB-MJHT")).toBeInTheDocument();
    expect(within(box).getByRole("link", { name: "Open GitHub" })).toHaveAttribute("href", "https://github.com/login/device");
    await fireEvent.click(within(box).getByRole("button", { name: "Cancel" }));
    expect(await screen.findByText("Sign-in was cancelled. Nothing was connected.")).toBeInTheDocument();
    const calls = fetch.mock.calls.map(([url]) => String(url));
    expect(calls.some((url) => url.endsWith("/cancel"))).toBe(true);
  });

  it("offers only the methods this machine has", async () => {
    stubFetch({
      "GET /api/github": connection({ device_sign_in: false }),
      "GET /api/git-credential": GIT_STATUS,
      "GET /api/github/discovery": {
        gh_accounts: [{ login: "octo", active: true }], credential_helpers: [], ssh_keys: [],
      },
    });
    render(GitHubConnection);
    expect(await screen.findByText(/GitHub sign-in isn't available in this build yet/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Connect GitHub" })).toBeNull();
    await fireEvent.click(screen.getByRole("button", { name: "Find credentials on this machine" }));
    const found = await screen.findByTestId("github-discovery");
    expect(within(found).getByRole("button", { name: "Use @octo (active)" })).toBeInTheDocument();
    expect(within(found).getByText("No Git credential manager is configured.")).toBeInTheDocument();
    expect(within(found).getByText(/No SSH key/)).toBeInTheDocument();
  });

  it("names the account in use and explains a failed check in words", async () => {
    stubFetch({
      "GET /api/github": connection({
        selected: CREDENTIAL,
        credentials: [CREDENTIAL, { ...CREDENTIAL, credential_id: "gcred_2", method: "gh_cli", selected: false, last_error: "git_account_mismatch" }],
      }),
      "GET /api/git-credential": GIT_STATUS,
    });
    render(GitHubConnection);
    const rows = await screen.findByTestId("github-credentials");
    expect(within(rows).getByText("In use")).toBeInTheDocument();
    expect(within(rows).getByText(/now belongs to a different GitHub account/)).toBeInTheDocument();
  });

  it("never offers merging as delegable, and lists and revokes a delegation", async () => {
    const delegation = {
      delegation_id: "deleg_1", repository: "github.com/octo/demo", repository_id: "900",
      operations: ["push"], branch_pattern: "raiker/*", expires_at: "2099-01-01T00:00:00Z",
      max_actions: 3, actions_used: 1, state: "active", parent_delegation_id: null, created_at: "2026-10-12T10:00:00Z",
    };
    const fetch = stubFetch({
      "GET /api/github": connection({ selected: CREDENTIAL, credentials: [CREDENTIAL], delegations: [delegation] }),
      "GET /api/git-credential": GIT_STATUS,
      "DELETE /api/github/delegations/deleg_1": connection({ selected: CREDENTIAL, credentials: [CREDENTIAL] }),
    });
    render(GitHubConnection);
    const list = await screen.findByTestId("github-delegations");
    expect(within(list).getByText(/push on raiker\/\*/)).toBeInTheDocument();
    expect(within(list).getByText(/1\/3 used/)).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Push a branch" })).toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: "Merge a pull request" })).toBeNull();
    expect(screen.queryByRole("checkbox", { name: /Read a repository/ })).toBeNull();
    await fireEvent.click(within(list).getByRole("button", { name: "Revoke" }));
    await waitFor(() => expect(screen.queryByTestId("github-delegations")).toBeNull());
    expect(fetch.mock.calls.some(([, init]) => (init as RequestInit | undefined)?.method === "DELETE")).toBe(true);
  });

  it("explains a refused delegation in words", async () => {
    stubFetch({
      "GET /api/github": connection({ selected: CREDENTIAL, credentials: [CREDENTIAL] }),
      "GET /api/git-credential": GIT_STATUS,
      "POST /api/github/delegations": { __status: 422, detail: { ok: false, reason_code: "delegation_branch_pattern_too_broad" } },
    });
    render(GitHubConnection);
    await fireEvent.input(await screen.findByLabelText("Repository"), { target: { value: "octo/demo" } });
    await fireEvent.click(screen.getByRole("button", { name: "Delegate" }));
    expect(await screen.findByText(/never reaches the default branch/)).toBeInTheDocument();
  });
  it("shows an issue-to-PR plan before scheduling it as a Build task (BUG-339)", async () => {
    const delegation = {
      delegation_id: "gdel_1", repository: "github.com/octo/demo", repository_id: null,
      operations: ["fetch", "branch", "commit", "push", "pull_request"], branch_pattern: "raiker/*",
      expires_at: "2099-01-01T00:00:00Z", max_actions: null, actions_used: 0, state: "active",
      parent_delegation_id: null, created_at: "2026-10-18T10:00:00Z",
    };
    const plan = {
      repository: "github.com/octo/demo", work_branch: "raiker/issue-7", delegation_id: "gdel_1",
      delegation_problems: [], blocked_needs_owner: false,
      steps: [
        { step: "read_issue", label: "Read the issue (as untrusted data)", operation: "read", decision: "runs" },
        { step: "push", label: "Push the work branch", operation: "push", decision: "runs_under_delegation" },
      ],
      never: ["delete_branch", "merge", "protected_branch", "workflows"],
      title: "Issue #7 → pull request (octo/demo)", description: "Work on issue #7…",
    };
    const fetch = stubFetch({
      "GET /api/github": connection({ delegations: [delegation] }),
      "GET /api/git-credential": GIT_STATUS,
      "POST /api/github/routines/issue-to-pr": plan,
      "GET /api/projects": { projects: [{ project_id: "proj_1", name: "demo", root_subpath: "demo", created_at: "x", session_count: 0 }], active_project_id: null },
      "POST /api/tasks": { task_id: "task_1" },
      "GET /api/code/repos": {
        repos: [{ repo_id: "repo_demo", label: "demo", selected: true }],
        selected_repo_id: "repo_demo",
        github_gate_state: "disabled", github_decision_mode: "ask", github_token_configured: false,
      },
    });
    render(GitHubConnection);
    const form = await screen.findByTestId("github-issue-routine");
    await fireEvent.change(within(form).getByLabelText("Delegation"), { target: { value: "gdel_1" } });
    await fireEvent.input(within(form).getByLabelText("Issue"), { target: { value: "7" } });
    await fireEvent.click(within(form).getByRole("button", { name: "Show the plan" }));

    const steps = await screen.findByTestId("github-issue-routine-plan");
    expect(within(steps).getByText("Runs under the delegation")).toBeInTheDocument();
    expect(screen.getByText(/Never: delete branch, merge/)).toBeInTheDocument();
    // BR-02 — the task is bound to the repository Build is pointed at now.
    expect(await screen.findByTestId("github-issue-routine-repository")).toHaveTextContent(
      "Runs in demo — the repository Build is pointed at now, and only there",
    );
    // Nothing is scheduled until the owner chooses a project and says so.
    expect(fetch.mock.calls.some(([url]) => String(url).endsWith("/api/tasks"))).toBe(false);
    const schedule = screen.getByRole("button", { name: "Schedule as a Build task" });
    expect(schedule).toBeDisabled();
    await fireEvent.change(await screen.findByLabelText(/^Project/), { target: { value: "proj_1" } });
    await fireEvent.click(schedule);
    await waitFor(() => {
      const created = fetch.mock.calls.find(([url, init]) => String(url).endsWith("/api/tasks") && (init as RequestInit)?.method === "POST");
      expect(created).toBeTruthy();
      const body = JSON.parse(String((created![1] as RequestInit).body));
      expect(body).toMatchObject({ title: plan.title, description: plan.description, surface: "build", project_id: "proj_1" });
    });
    const sent = fetch.mock.calls.find(([url]) => String(url).endsWith("/api/github/routines/issue-to-pr"));
    expect(JSON.parse(String((sent![1] as RequestInit).body))).toEqual({
      repository: "github.com/octo/demo", issue_number: 7, work_branch: "raiker/issue-7", delegation_id: "gdel_1",
    });
  });
});
