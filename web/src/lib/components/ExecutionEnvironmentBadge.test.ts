import { render, screen } from "@testing-library/svelte";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../api";
import ExecutionEnvironmentBadge from "./ExecutionEnvironmentBadge.svelte";

afterEach(() => vi.restoreAllMocks());

it("names the selected environment and readiness", async () => {
  vi.spyOn(api, "executionEnvironments").mockResolvedValue({
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
      },
    ],
  });

  render(ExecutionEnvironmentBadge);

  const badge = await screen.findByText("Local sandbox · Ready");
  expect(badge).toBeInTheDocument();
  expect(badge).toHaveAttribute("href", "#/settings?tab=advanced&kind=runtime");
});

it("says a retired container selection is removed, not merely unready", async () => {
  vi.spyOn(api, "executionEnvironments").mockResolvedValue({
    selected_profile_id: "container_default",
    environments: [
      {
        profile_id: "container_default",
        kind: "retired",
        name: "Local container",
        enabled: true,
        configured: false,
        available: false,
        status: "retired",
        selected: true,
        credential_configured: true,
        budget: null,
        cost: null,
        selected_for_commands: true,
        assigned_tools: [],
        features: {},
        probe_checked_at: "2026-08-14T10:00:00Z",
        availability_reason: "container_environment_retired",
      },
    ],
  });

  render(ExecutionEnvironmentBadge);

  expect(await screen.findByText("Local container · Removed")).toBeInTheDocument();
});
