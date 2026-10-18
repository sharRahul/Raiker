/**
 * BR-D01 — a finished Build turn says what its own records support, and nothing
 * when it changed no files.
 */
import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import BuildOutcome from "./BuildOutcome.svelte";
import { stubFetch } from "../test-helpers";

const ROUTE = "GET /api/sessions/sess_1/turns/turn_1/outcome";

function outcome(overrides: Record<string, unknown>): Record<string, unknown> {
  return { turn_id: "turn_1", project_id: "proj_1", writes: 1, checks: [], reason: "", ...overrides };
}

describe("BuildOutcome", () => {
  it("names a verified change and each check that passed", async () => {
    stubFetch({
      [ROUTE]: outcome({
        outcome: "completed_verified",
        reason: "Every check you declared ran after the last change and passed.",
        checks: [{ command: "pytest -q", result: "passed", exit_code: 0, run_id: "cmd_1" }],
      }),
    });
    render(BuildOutcome, { sessionId: "sess_1", turnId: "turn_1" });
    expect(await screen.findByText("Verified")).toBeInTheDocument();
    expect(screen.getByText("pytest -q")).toBeInTheDocument();
    expect(screen.getByTestId("build-outcome")).toHaveAttribute("data-outcome", "completed_verified");
  });

  it("says a failed check failed, with its exit code", async () => {
    stubFetch({
      [ROUTE]: outcome({
        outcome: "failed",
        reason: "A check you declared ran after the last change and failed.",
        checks: [{ command: "pytest -q", result: "failed", exit_code: 1, run_id: "cmd_1" }],
      }),
    });
    render(BuildOutcome, { sessionId: "sess_1", turnId: "turn_1" });
    expect(await screen.findByText("Checks failed")).toBeInTheDocument();
    expect(screen.getByText(/failed \(exit 1\)/)).toBeInTheDocument();
  });

  it("asks for checks when none are declared, rather than implying success", async () => {
    stubFetch({ [ROUTE]: outcome({ outcome: "completed_unverified", reason: "No checks are declared." }) });
    render(BuildOutcome, { sessionId: "sess_1", turnId: "turn_1" });
    expect(await screen.findByText("Not verified")).toBeInTheDocument();
    expect(screen.getByText(/Add checks to this project's context/)).toBeInTheDocument();
  });

  it("shows nothing for a turn that changed no files", async () => {
    const fetch = stubFetch({ [ROUTE]: outcome({ outcome: "no_change", writes: 0 }) });
    render(BuildOutcome, { sessionId: "sess_1", turnId: "turn_1" });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(fetch).toHaveBeenCalled();
    expect(screen.queryByTestId("build-outcome")).toBeNull();
  });
});
