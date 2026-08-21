import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../api";
import type { ExecutionEnvironmentsView } from "../../apiTypes";
import Runtime from "./Runtime.svelte";

const view: ExecutionEnvironmentsView = {
  selected_profile_id: "local_native",
  environments: [
    {
      profile_id: "local_native",
      kind: "local",
      name: "Local workspace",
      enabled: true,
      configured: true,
      available: true,
      status: "ready",
      selected: true,
      credential_configured: true,
      budget: null,
      cost: null,
    },
    {
      profile_id: "container-review",
      kind: "container",
      name: "Repository review",
      enabled: true,
      configured: true,
      available: false,
      status: "unavailable",
      selected: false,
      credential_configured: true,
      budget: null,
      cost: null,
      runtime: "podman",
      image: "raiker-tools:approved",
      repository_access: "read_only",
      writable_output: true,
      assigned_tool_count: 2,
      availability_reason: "container_runtime_unavailable:podman",
    },
  ],
  container_options: {
    runtimes: ["docker", "podman"],
    images: ["raiker-tools:approved"],
    supported_tools: ["glob", "grep", "list_directory", "read_file", "stat_path"],
  },
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

describe("Runtime container profiles", () => {
  it("shows the runtime boundary and exact unavailable remediation", async () => {
    stubRuntime();
    render(Runtime);

    expect(await screen.findByText("Repository review")).toBeInTheDocument();
    expect(screen.getByText("Podman · raiker-tools:approved")).toBeInTheDocument();
    expect(screen.getByText("Read-only repository → writable output")).toBeInTheDocument();
    expect(screen.getByText("2 tools")).toBeInTheDocument();
    expect(screen.getByText("Podman is not available on this host.")).toBeInTheDocument();
  });

  it("submits only allowlisted container choices", async () => {
    stubRuntime();
    const configure = vi
      .spyOn(api, "configureExecutionEnvironment")
      .mockResolvedValue({ ok: true, profile_id: "container-new" });
    render(Runtime);

    await fireEvent.click(await screen.findByText("Add execution profile"));
    await fireEvent.change(screen.getByLabelText("Environment type"), {
      target: { value: "container" },
    });
    await fireEvent.input(screen.getByLabelText("Display name"), {
      target: { value: "Safe reads" },
    });
    await fireEvent.change(screen.getByLabelText("Container runtime"), {
      target: { value: "podman" },
    });
    await fireEvent.click(screen.getByLabelText("grep"));
    await fireEvent.click(screen.getByRole("button", { name: "Save environment" }));

    await waitFor(() =>
      expect(configure).toHaveBeenCalledWith({
        kind: "container",
        name: "Safe reads",
        enabled: true,
        config: {
          runtime: "podman",
          image: "raiker-tools:approved",
          tools: ["grep"],
          repository_access: "read_only",
          writable_output: true,
          egress_domains: [],
          egress_ports: [],
        },
      }),
    );
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
        {
          ...view.environments[1],
          available: true,
          status: "ready",
          availability_reason: null,
          features: { persistent_environment: true, process_tree_stop: true },
        },
      ],
    });
  }

  it("lists only the capabilities a boundary really has", async () => {
    stubCapabilities();
    render(Runtime);

    expect(await screen.findByText("Survives a Raiker restart")).toBeInTheDocument();
    expect(screen.getByText("Runs work in the background")).toBeInTheDocument();
    expect(screen.getByText("Keeps its state between commands")).toBeInTheDocument();
    // The local boundary does not persist, so it gets no reset control at all.
    expect(screen.getAllByRole("button", { name: "Reset environment" })).toHaveLength(1);
  });

  it("resets the persistent boundary, and clears the cache only when asked", async () => {
    stubCapabilities();
    const reset = vi
      .spyOn(api, "resetExecutionEnvironment")
      .mockResolvedValue({ ok: true, profile_id: "container-review", session_id: "settings", recreated: false });
    vi.stubGlobal("confirm", () => true);
    render(Runtime);

    await fireEvent.click(await screen.findByRole("button", { name: "Reset environment" }));
    await waitFor(() =>
      expect(reset).toHaveBeenCalledWith("container-review", "settings", false),
    );

    await fireEvent.click(screen.getByRole("button", { name: "Reset and clear cache" }));
    await waitFor(() =>
      expect(reset).toHaveBeenCalledWith("container-review", "settings", true),
    );
    vi.unstubAllGlobals();
  });
});

describe("Runtime filtered egress honesty", () => {
  it("shows normalized policy but never presents configuration as enforcement", async () => {
    stubRuntime();
    vi.spyOn(api, "executionEnvironments").mockResolvedValue({
      ...view,
      environments: [
        view.environments[0],
        {
          ...view.environments[1],
          config: {
            egress_domains: ["api.example.com", "*.packages.example"],
            egress_ports: [443],
            egress_enforcement: "not_proven",
          },
          features: { filtered_network: false },
        },
      ],
    });
    render(Runtime);

    expect(await screen.findByRole("status", { name: "Filtered network status" })).toHaveTextContent(
      "Filtered network · not proven",
    );
    expect(screen.getByText(/api\.example\.com, \*\.packages\.example/)).toBeInTheDocument();
    expect(screen.queryByText("Filters command network access")).not.toBeInTheDocument();
  });
});
