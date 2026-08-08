import { render, screen } from "@testing-library/svelte";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../api";
import ExecutionEnvironmentBadge from "./ExecutionEnvironmentBadge.svelte";

afterEach(() => vi.restoreAllMocks());

it("names the selected container runtime and readiness", async () => {
  vi.spyOn(api, "executionEnvironments").mockResolvedValue({
    selected_profile_id: "container-review",
    environments: [
      {
        profile_id: "container-review",
        kind: "container",
        name: "Repository review",
        enabled: true,
        configured: true,
        available: true,
        status: "ready",
        selected: true,
        credential_configured: true,
        budget: null,
        cost: null,
        runtime: "podman",
        image: "raiker-tools:approved",
        repository_access: "read_only",
        writable_output: true,
        assigned_tool_count: 2,
        availability_reason: null,
      },
    ],
    container_options: { runtimes: ["docker", "podman"], images: [], supported_tools: [] },
  });

  render(ExecutionEnvironmentBadge);

  expect(await screen.findByText("Repository review · Podman · Ready")).toBeInTheDocument();
});
