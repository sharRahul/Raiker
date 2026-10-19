/**
 * BR-D02 — Build's header states where a turn would run, from the server's
 * target description, and nothing when there is no target to state.
 */
import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import BuildTargetChip from "./BuildTargetChip.svelte";
import { stubFetch } from "../test-helpers";

const ROUTE = "GET /api/code/repos/repo_1/target";

function target(overrides: Record<string, unknown>): Record<string, unknown> {
  return {
    repo_id: "repo_1",
    repo_kind: "local",
    label: "app",
    state: "ready",
    host: "this_computer",
    folder: "app",
    folder_exists: true,
    git: true,
    branch: "main",
    head: "abc1234",
    identity: "https://github.com/o/app.git",
    environment: "local_native",
    code_placement: "sandbox",
    code_placement_reason: "native_sandbox_available",
    fingerprint: "f".repeat(64),
    ...overrides,
  };
}

describe("BuildTargetChip", () => {
  it("states the branch, commit and where code runs", async () => {
    stubFetch({ [ROUTE]: target({}) });
    render(BuildTargetChip, { repoId: "repo_1" });
    const chip = await screen.findByTestId("build-target");
    expect(chip).toHaveTextContent("main · abc1234");
    expect(chip).toHaveTextContent("Sandbox");
    expect(chip.getAttribute("title")).toContain("Repository: https://github.com/o/app.git");
    expect(chip.getAttribute("title")).toContain("Target fingerprint: ffffffffffff");
  });

  it("says a GitHub coordinate has no checkout instead of inventing a branch", async () => {
    stubFetch({ [ROUTE]: target({ repo_kind: "github", state: "remote_only", git: false, branch: "", head: "" }) });
    render(BuildTargetChip, { repoId: "repo_1" });
    expect(await screen.findByTestId("build-target")).toHaveTextContent("GitHub · no checkout");
  });

  it("leaves a missing folder to the header's warning", async () => {
    stubFetch({ [ROUTE]: target({ state: "folder_missing", folder_exists: false }) });
    render(BuildTargetChip, { repoId: "repo_1" });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.queryByTestId("build-target")).toBeNull();
  });
});
