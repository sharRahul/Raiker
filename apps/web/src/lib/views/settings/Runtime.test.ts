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
        },
      }),
    );
  });
});
