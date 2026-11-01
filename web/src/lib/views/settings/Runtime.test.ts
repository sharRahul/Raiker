import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "../../api";
import type { ExecutionEnvironmentsView } from "../../apiTypes";
import Runtime from "./Runtime.svelte";

const view: ExecutionEnvironmentsView = {
  selected_profile_id: "native_sandbox",
  environments: [
    {
      profile_id: "native_sandbox",
      kind: "native",
      name: "Local sandbox",
      enabled: true,
      configured: true,
      available: true,
      status: "ready",
      selected: true,
      credential_configured: true,
      budget: null,
      cost: null,
      selected_for_commands: true,
      assigned_tools: [],
      features: {},
      probe_checked_at: "2026-08-14T10:00:00Z",
      availability_reason: null,
      boundary: "appcontainer",
      probe_observations: {},
    },
    {
      profile_id: "container-review",
      kind: "retired",
      name: "Repository review",
      enabled: true,
      configured: false,
      available: false,
      status: "retired",
      selected: false,
      credential_configured: true,
      budget: null,
      cost: null,
      selected_for_commands: false,
      assigned_tools: [],
      features: {},
      probe_checked_at: "2026-08-14T10:00:00Z",
      availability_reason: "container_environment_retired",
      boundary: "none",
      probe_observations: {},
    },
  ],
};

afterEach(() => vi.restoreAllMocks());

function stubRuntime() {
  vi.spyOn(api, "runtimeMode").mockResolvedValue({
    mode_name: "raiker_runtime",
    status: "active",
    activated_at: "2026-08-08T18:00:00Z",
    activated_by: "principal_owner",
    reason: "Runtime enabled",
    allowed_modes: [],
  });
  vi.spyOn(api, "executionEnvironments").mockResolvedValue(view);
}

describe("Runtime environments", () => {
  it("shows a retired Docker profile as removed, never as a place work runs", async () => {
    stubRuntime();
    render(Runtime);

    const card = within((await screen.findByText("Repository review")).closest("article")!);
    expect(card.getByText("Docker/Podman · removed")).toBeInTheDocument();
    expect(card.getByText(/Raiker no longer uses Docker or Podman/)).toBeInTheDocument();
    expect(card.getByRole("button", { name: "Select" })).toBeDisabled();
  });

  it("no longer offers a container boundary to configure", async () => {
    stubRuntime();
    render(Runtime);

    await fireEvent.click(await screen.findByText("Add execution profile"));
    const options = [...(screen.getByLabelText("Environment type") as HTMLSelectElement).options];
    expect(options.map((option) => option.value)).toEqual(["ssh", "daytona"]);
  });

  it("requires an exact SSH host key pin and keeps remote capabilities honest", async () => {
    stubRuntime();
    const configure = vi
      .spyOn(api, "configureExecutionEnvironment")
      .mockResolvedValue({ ok: true, profile_id: "ssh-new" });
    render(Runtime);

    await fireEvent.click(await screen.findByText("Add execution profile"));
    await fireEvent.input(screen.getByLabelText("Display name"), { target: { value: "Build host" } });
    await fireEvent.input(screen.getByLabelText("Host"), { target: { value: "build.example.com" } });
    await fireEvent.input(screen.getByLabelText("Remote user"), { target: { value: "raiker" } });
    await fireEvent.input(screen.getByLabelText("Pinned host public key"), { target: { value: "ssh-ed25519 AAAATEST" } });
    await fireEvent.input(screen.getByLabelText("Host fingerprint"), { target: { value: `SHA256:${"a".repeat(43)}` } });
    await fireEvent.click(screen.getByRole("button", { name: "Save environment" }));

    await waitFor(() => expect(configure).toHaveBeenCalledWith({
      kind: "ssh",
      name: "Build host",
      enabled: true,
      config: {
        host: "build.example.com",
        user: "raiker",
        credential_env: "RAIKER_SSH_IDENTITY_FILE",
        host_public_key: "ssh-ed25519 AAAATEST",
        host_key_sha256: `SHA256:${"a".repeat(43)}`,
        max_runtime_seconds: 300,
      },
    }));
  });
});

// BUG-194 — the environment card states what each boundary really does between
// commands, and offers the reset only where there is something to reset. Both
// halves matter: an absent control is the honest projection of an unbuilt
// capability, where a disabled one implies it is a setting away.
describe("Runtime execution capabilities and reset (BUG-194)", () => {
  function stubCapabilities() {
    vi.spyOn(api, "runtimeMode").mockResolvedValue({
      mode_name: "raiker_runtime",
      status: "active",
      activated_at: "2026-08-17T00:00:00Z",
      activated_by: "principal_owner",
      reason: "Runtime enabled",
      allowed_modes: [],
    });
    vi.spyOn(api, "executionEnvironments").mockResolvedValue({
      ...view,
      environments: [
        {
          ...view.environments[0],
          features: { background: true, pty: true, restart_recovery: true, persistent_environment: false },
        },
        view.environments[1],
      ],
    });
  }

  it("lists only the capabilities a boundary really has", async () => {
    stubCapabilities();
    render(Runtime);

    expect(await screen.findByText("Survives a Raiker restart")).toBeInTheDocument();
    expect(screen.getByText("Runs work in the background")).toBeInTheDocument();
    expect(screen.queryByText("Keeps its state between commands")).not.toBeInTheDocument();
    const localCard = within(screen.getByText("Local sandbox").closest("article")!);
    expect(localCard.getByText("Foreground and background command execution")).toBeInTheDocument();
    expect(localCard.queryByText(/background execution.*unavailable/i)).not.toBeInTheDocument();
    // No boundary persists between commands, so nothing offers a reset.
    expect(screen.queryByRole("button", { name: "Reset environment" })).not.toBeInTheDocument();
  });

});

describe("Runtime runner integrity", () => {
  it("names package-relative runner integrity without calling it publisher verification", async () => {
    stubRuntime();
    vi.spyOn(api, "executionEnvironments").mockResolvedValue({
      ...view,
      environments: [{
        ...view.environments[0], kind: "native", name: "Native OS sandbox",
        runner_trust: "package_relative_integrity", probe_observations: {},
      }],
    });
    render(Runtime);
    expect(await screen.findByText("Package-relative integrity only")).toBeInTheDocument();
    expect(screen.queryByText("Publisher verified")).not.toBeInTheDocument();
  });
});

/**
 * REM-SET-RUNTIME — the page guides an execution target, and keeps the tuning
 * that is an interval or a port number below the thing it tunes.
 */
describe("Runtime configuration reading order", () => {
  it("puts the execution target above the tuning, not below it", async () => {
    stubRuntime();
    render(Runtime, { principal: "owner", settings: {}, save: vi.fn() });

    const targets = await screen.findByText("Local, remote, and cloud environments");
    const advanced = screen.getByText("Advanced");
    expect(targets.compareDocumentPosition(advanced) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("folds the readiness window away and says where readiness is actually read", async () => {
    stubRuntime();
    render(Runtime, { principal: "owner", settings: {}, save: vi.fn() });

    const summary = await screen.findByText("Advanced");
    expect(summary.closest("details")?.open).toBe(false);
    expect(screen.getByLabelText(/Re-confirm a model check after/)).toHaveValue(5);
    expect(screen.getByRole("link", { name: "Models" })).toHaveAttribute("href", "#/models");
    expect(screen.getByRole("link", { name: "Diagnostics" })).toHaveAttribute("href", "#/observe");
  });

  it("still reports the owner's readiness window to the runtime", async () => {
    const save = vi.fn();
    stubRuntime();
    render(Runtime, { principal: "owner", settings: {}, save });

    const field = await screen.findByLabelText(/Re-confirm a model check after/);
    await fireEvent.change(field, { target: { value: "30" } });

    expect(save).toHaveBeenCalledWith({ "models.readiness_ttl_minutes": 30 });
  });

});

// DEC-11 step 6 — a configured target can be turned off, and off stops what runs there.
describe("Runtime turning a target off", () => {
  it("offers Turn off only on a target the owner configured, and says what stopped", async () => {
    stubRuntime();
    const toggle = vi
      .spyOn(api, "setExecutionEnvironmentEnabled")
      .mockResolvedValue({ ok: true, profile_id: "container-review", enabled: false, stopped_runs: 2 });
    vi.stubGlobal("confirm", () => true);
    render(Runtime);

    const card = within((await screen.findByText("Repository review")).closest("article")!);
    const localCard = within(screen.getByText("Local sandbox").closest("article")!);
    expect(localCard.queryByRole("button", { name: "Turn off" })).not.toBeInTheDocument();
    await fireEvent.click(card.getByRole("button", { name: "Turn off" }));

    await waitFor(() => expect(toggle).toHaveBeenCalledWith("container-review", false));
    expect(await screen.findByText(/Repository review is off\. 2 running commands were stopped\./)).toBeInTheDocument();
    vi.unstubAllGlobals();
  });

  it("says a target is off and offers to turn it back on", async () => {
    stubRuntime();
    vi.spyOn(api, "executionEnvironments").mockResolvedValue({
      ...view,
      environments: [
        view.environments[0],
        { ...view.environments[1], enabled: false, status: "off", availability_reason: null },
      ],
    });
    render(Runtime);

    const card = within((await screen.findByText("Repository review")).closest("article")!);
    expect(card.getByText(/Off — nothing runs here/)).toBeInTheDocument();
    expect(card.getByRole("button", { name: "Turn on" })).toBeInTheDocument();
  });
});

// Found by the 2026-10-11 live round: the runtime card printed a raw ISO time.
describe("Runtime last changed", () => {
  it("says when the runtime last changed as a local time, not an ISO string", async () => {
    stubRuntime();
    render(Runtime);
    await screen.findByText("Repository review");
    expect(screen.queryByText("2026-08-08T18:00:00Z")).toBeNull();
  });
});

// DEC-11 step 6 — removing a target nothing depends on, or naming where work goes.
describe("Runtime removing a target", () => {
  it("removes a target that is not the default with no replacement", async () => {
    stubRuntime();
    const remove = vi.spyOn(api, "removeExecutionEnvironment").mockResolvedValue({
      ok: true, profile_id: "container-review", removed: true, name: "Repository review",
      selected_profile_id: null,
    });
    const asked: string[] = [];
    vi.stubGlobal("confirm", (text: string) => { asked.push(text); return true; });
    render(Runtime);

    const card = within((await screen.findByText("Repository review")).closest("article")!);
    const localCard = within(screen.getByText("Local sandbox").closest("article")!);
    expect(localCard.queryByRole("button", { name: "Remove" })).not.toBeInTheDocument();
    await fireEvent.click(card.getByRole("button", { name: "Remove" }));

    await waitFor(() => expect(remove).toHaveBeenCalledWith("container-review", null));
    expect(asked[0]).toMatch(/commands that ran here stay in the record/);
    expect(await screen.findByText("Repository review was removed.")).toBeInTheDocument();
    vi.unstubAllGlobals();
  });

  it("names where work will run when the default is removed, and sends that choice", async () => {
    stubRuntime();
    vi.spyOn(api, "executionEnvironments").mockResolvedValue({
      ...view,
      selected_profile_id: "container-review",
      environments: [
        { ...view.environments[0], selected: false },
        { ...view.environments[1], selected: true },
      ],
    });
    const remove = vi.spyOn(api, "removeExecutionEnvironment").mockResolvedValue({
      ok: true, profile_id: "container-review", removed: true, name: "Repository review",
      selected_profile_id: "native_sandbox",
    });
    const asked: string[] = [];
    vi.stubGlobal("confirm", (text: string) => { asked.push(text); return true; });
    render(Runtime);

    const card = within((await screen.findByText("Repository review")).closest("article")!);
    await fireEvent.click(card.getByRole("button", { name: "Remove" }));

    await waitFor(() => expect(remove).toHaveBeenCalledWith("container-review", "native_sandbox"));
    expect(asked[0]).toMatch(/from now on it runs on Local sandbox/);
    vi.unstubAllGlobals();
  });

  it("says to turn it off first when commands still run there", async () => {
    stubRuntime();
    vi.spyOn(api, "removeExecutionEnvironment").mockRejectedValue(
      new ApiError(409, "execution_environment_in_use", "conflict"),
    );
    vi.stubGlobal("confirm", () => true);
    render(Runtime);

    const card = within((await screen.findByText("Repository review")).closest("article")!);
    await fireEvent.click(card.getByRole("button", { name: "Remove" }));

    expect(await screen.findByText(/still has commands running\. Turn it off first/)).toBeInTheDocument();
    vi.unstubAllGlobals();
  });
});

// Found in the 2026-10-11 live round: the browser compiles `pattern` with the
// `v` flag, where an unescaped "/" in a class is a syntax error — so the
// fingerprint check was silently never applied.
describe("Runtime field patterns", () => {
  it("every pattern on the page compiles the way the browser compiles it", async () => {
    stubRuntime();
    const { container } = render(Runtime);
    await screen.findByText("Repository review");
    const patterns = [...container.querySelectorAll("input[pattern]")].map((input) => input.getAttribute("pattern") ?? "");
    expect(patterns.length).toBeGreaterThan(0);
    for (const pattern of patterns) expect(() => new RegExp(`^(?:${pattern})$`, "v")).not.toThrow();
    const fingerprint = new RegExp(`^(?:${patterns.find((p) => p.startsWith("SHA256"))})$`, "v");
    expect(fingerprint.test("SHA256:/cZYD7wNWwk8It+s1GdraLEv7RbNRGVdZUf0IkT6MEM")).toBe(true);
    expect(fingerprint.test("SHA256:short")).toBe(false);
  });
});

