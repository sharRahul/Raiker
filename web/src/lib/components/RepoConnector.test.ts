// The connector's job is to be honest about what connecting a repository does
// and does not do: it must translate the server's fail-closed refusals into
// something a person can act on, and never imply that connecting granted access.
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CodeMapStatus, CodeReposView } from "../apiTypes";
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

// B9 — the code map's state, as the panel reads it back from /api/code/map.
function codeMap(partial: Partial<CodeMapStatus> = {}): CodeMapStatus {
  return {
    capability: "code_map_indexing",
    gate_state: "enabled_runtime",
    decision_mode: "ask",
    enabled: true,
    repository: "projects/my-app",
    repo_id: "repo_1",
    status: "indexed",
    reason_code: "",
    file_count: 412,
    symbol_count: 3120,
    edge_count: 900,
    languages: { python: 300, typescript: 112 },
    skipped: {},
    limits_hit: [],
    built_at: "2026-08-08T09:00:00Z",
    updated_at: "2026-08-08T09:30:00Z",
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
    const fetchMock = stubFetch({
      "POST /api/code/repos": { ok: true, repo_id: "repo_1" },
      "PUT /api/code/repos/selection": { ok: true, selected_repo_id: "repo_1" },
    });
    const onchanged = mount();

    await fireEvent.input(screen.getByLabelText(/folder inside this workspace/i), {
      target: { value: "projects/my-app" },
    });
    await fireEvent.click(screen.getByRole("button", { name: /connect repository/i }));

    await waitFor(() => expect(onchanged).toHaveBeenCalled());
    const connect = fetchMock.mock.calls.find(([u]) => String(u).endsWith("/api/code/repos"));
    expect(JSON.parse(String(connect?.[1]?.body))).toEqual({
      kind: "local",
      path: "projects/my-app",
    });
  });

  // Connecting the first repository is the owner saying which one this is. Build
  // sitting on "No repository" afterwards reads as the connect having failed.
  it("makes the first connected repository the active one", async () => {
    const fetchMock = stubFetch({
      "POST /api/code/repos": { ok: true, repo_id: "repo_1" },
      "PUT /api/code/repos/selection": { ok: true, selected_repo_id: "repo_1" },
    });
    mount();

    await fireEvent.input(screen.getByLabelText(/folder inside this workspace/i), {
      target: { value: "projects/my-app" },
    });
    await fireEvent.click(screen.getByRole("button", { name: /connect repository/i }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([u]) => String(u).includes("/api/code/repos/selection")),
      ).toBe(true),
    );
  });

  // ...and never a second one. An active repository is a choice, and adding
  // another must not silently move the work onto it.
  it("leaves an already-active repository alone when a second is connected", async () => {
    const fetchMock = stubFetch({
      "POST /api/code/repos": { ok: true, repo_id: "repo_2" },
      "PUT /api/code/repos/selection": { ok: true, selected_repo_id: "repo_2" },
    });
    const onchanged = mount({
      repos: [
        {
          repo_id: "repo_1",
          kind: "local",
          label: "my-app",
          selected: true,
          created_at: "2026-08-08T09:00:00Z",
          local_subpath: "projects/my-app",
          local_exists: true,
          github_owner: null,
          github_repo: null,
          branch: null,
        },
      ],
      selected_repo_id: "repo_1",
    });

    await fireEvent.input(screen.getByLabelText(/folder inside this workspace/i), {
      target: { value: "projects/other" },
    });
    await fireEvent.click(screen.getByRole("button", { name: /connect repository/i }));

    await waitFor(() => expect(onchanged).toHaveBeenCalled());
    expect(
      fetchMock.mock.calls.some(([u]) => String(u).includes("/api/code/repos/selection")),
    ).toBe(false);
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

  it("states what the code map holds and offers a rebuild", async () => {
    stubFetch({ "GET /api/code/map": codeMap() });
    mount();

    expect(await screen.findByText(/412 files, 3,120 declarations/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /rebuild index/i })).toBeEnabled();
  });

  it("offers to build the index when the repository has never been scanned", async () => {
    stubFetch({ "GET /api/code/map": codeMap({ status: "not_indexed", file_count: 0, symbol_count: 0 }) });
    mount();

    expect(await screen.findByRole("button", { name: /build index/i })).toBeEnabled();
    expect(screen.getByText(/not indexed yet/i)).toBeInTheDocument();
  });

  it("says the owner turned indexing off, and does not offer to run it anyway", async () => {
    // The gate is the owner's. A control that pretends to work while the
    // runtime would refuse is the failure this codebase keeps closing.
    stubFetch({ "GET /api/code/map": codeMap({ enabled: false, gate_state: "disabled" }) });
    mount();

    expect(await screen.findByText(/indexing is off/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /build index|rebuild index/i })).toBeDisabled();
  });

  it("names the bound a partial scan stopped at instead of reporting it as complete", async () => {
    stubFetch({
      "GET /api/code/map": codeMap({ status: "partial", limits_hit: ["max_files"] }),
    });
    mount();

    expect(await screen.findByText(/partial — the scan stopped at max files/i)).toBeInTheDocument();
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
