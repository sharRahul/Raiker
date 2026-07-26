// The connector's job is to be honest about what connecting a repository does
// and does not do: it must translate the server's fail-closed refusals into
// something a person can act on, and never imply that connecting granted access.
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CodeReposView } from "../apiTypes";
import { stubFetch } from "../test-helpers";
import RepoConnector from "./RepoConnector.svelte";

afterEach(() => vi.unstubAllGlobals());

function view(partial: Partial<CodeReposView> = {}): CodeReposView {
  return {
    repos: [],
    selected_repo_id: null,
    github_gate_state: "enabled_runtime",
    github_decision_mode: "ask",
    github_token_configured: true,
    note: "References only.",
    ...partial,
  };
}

function mount(partial: Partial<CodeReposView> = {}) {
  const onchanged = vi.fn();
  render(RepoConnector, { props: { view: view(partial), onchanged, onclose: () => {} } });
  return onchanged;
}

describe("RepoConnector", () => {
  it("connects a workspace folder", async () => {
    const fetchMock = stubFetch({ "POST /api/code/repos": { ok: true, repo_id: "repo_1" } });
    const onchanged = mount();

    await fireEvent.input(screen.getByLabelText(/folder inside this workspace/i), {
      target: { value: "projects/my-app" },
    });
    await fireEvent.click(screen.getByRole("button", { name: /connect repository/i }));

    await waitFor(() => expect(onchanged).toHaveBeenCalled());
    const body = JSON.parse(String(fetchMock.mock.calls.at(-1)?.[1]?.body));
    expect(body).toEqual({ kind: "local", path: "projects/my-app" });
  });

  it("explains a path the runtime refused instead of showing a status code", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 422,
        json: async () => ({ detail: { reason_code: "repo_outside_workspace" } }),
      })),
    );
    mount();

    await fireEvent.input(screen.getByLabelText(/folder inside this workspace/i), {
      target: { value: "../elsewhere" },
    });
    await fireEvent.click(screen.getByRole("button", { name: /connect repository/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/outside this Raiker workspace/i);
  });

  it("splits a pasted owner/repo or GitHub URL into both fields", async () => {
    stubFetch({ "POST /api/code/repos": { ok: true, repo_id: "repo_1" } });
    mount();

    await fireEvent.click(screen.getByRole("button", { name: /github/i }));
    const ownerField = screen.getByLabelText("Owner");
    await fireEvent.input(ownerField, { target: { value: "https://github.com/octo/app.git" } });

    await waitFor(() => expect((ownerField as HTMLInputElement).value).toBe("octo"));
    expect((screen.getByLabelText("Repository") as HTMLInputElement).value).toBe("app");
  });

  it("says GitHub reads stay closed when the gate is off, without blocking the connection", async () => {
    // Connecting is bookkeeping. Refusing to record the reference would be
    // wrong; implying it granted reads would be worse.
    mount({ github_gate_state: "disabled", github_decision_mode: "ask" });

    await fireEvent.click(screen.getByRole("button", { name: /github/i }));

    expect(screen.getByText(/connector is closed right now/i)).toBeInTheDocument();
    expect(screen.getByText(/fail\s*closed until you open the gate/i)).toBeInTheDocument();
  });

  it("warns that reads fail closed while no owner token is configured", async () => {
    mount({ github_token_configured: false });

    await fireEvent.click(screen.getByRole("button", { name: /github/i }));

    expect(screen.getByText(/no owner token is configured yet/i)).toBeInTheDocument();
  });

  it("marks a local folder that has gone missing from the workspace", async () => {
    mount({
      repos: [
        {
          repo_id: "repo_1",
          kind: "local",
          label: "my-app",
          selected: false,
          created_at: "2026-07-20T00:00:00Z",
          local_subpath: "projects/my-app",
          local_exists: false,
          github_owner: null,
          github_repo: null,
          branch: null,
        },
      ],
    });

    expect(screen.getByText(/folder is missing/i)).toBeInTheDocument();
  });
});
