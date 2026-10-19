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
  return {
    turn_id: "turn_1",
    project_id: "proj_1",
    writes: 1,
    checks: [],
    reason: "",
    readback: [],
    unapplied_writes: 0,
    pending_writes: 0,
    target_drift: [],
    target: null,
    ...overrides,
  };
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

  it("says a check ran outside the repository folder, and where", async () => {
    stubFetch({
      [ROUTE]: outcome({
        outcome: "completed_unverified",
        checks: [{ command: "pytest -q", result: "wrong_directory", exit_code: 0, run_id: "cmd_1", cwd: "." }],
        target: { repo_kind: "local", label: "app", folder: "app", branch: "main", head: "abc1234", fingerprint: "f" },
      }),
    });
    render(BuildOutcome, { sessionId: "sess_1", turnId: "turn_1" });
    expect(await screen.findByText(/ran outside the repository folder \(in the workspace root\)/)).toBeInTheDocument();
    expect(screen.getByText(/on main from abc1234/)).toBeInTheDocument();
  });

  it("names a written file that is no longer on disk, and a target that moved", async () => {
    stubFetch({
      [ROUTE]: outcome({
        outcome: "completed_unverified",
        readback: [
          { path: "app/notes.txt", state: "missing" },
          { path: "app/ok.txt", state: "matches" },
        ],
        target_drift: ["branch"],
        target: { repo_kind: "local", label: "app", folder: "app", branch: "main", head: "", fingerprint: "f" },
      }),
    });
    render(BuildOutcome, { sessionId: "sess_1", turnId: "turn_1" });
    expect(await screen.findByText("app/notes.txt")).toBeInTheDocument();
    expect(screen.getByText(/no longer on disk/)).toBeInTheDocument();
    expect(screen.queryByText("app/ok.txt")).toBeNull();
    expect(screen.getByTestId("build-target-drift")).toHaveTextContent(
      "The branch this turn started on has changed since (it began on main).",
    );
  });

  it("names a high-severity finding on the stored review of the current patch", async () => {
    stubFetch({
      [ROUTE]: outcome({
        outcome: "completed_unverified",
        reason: "Every check passed, but the review of the current patch has a high-severity finding.",
        checks: [{ command: "pytest -q", result: "passed", exit_code: 0, run_id: "cmd_1", cwd: "app" }],
        review: { fingerprint: "f", high: 1, findings: 2 },
      }),
    });
    render(BuildOutcome, { sessionId: "sess_1", turnId: "turn_1" });
    expect(await screen.findByTestId("build-outcome-review")).toHaveTextContent(
      "The review of the current patch has 1 high-severity finding — see Changes.",
    );
  });

  it("says a stopped turn stopped, and a partial change that some of it did not apply", async () => {
    stubFetch({
      [ROUTE]: outcome({
        outcome: "partially_completed",
        reason: "Some changes this turn proposed were applied, and others failed or were refused.",
        unapplied_writes: 2,
      }),
    });
    render(BuildOutcome, { sessionId: "sess_1", turnId: "turn_1" });
    expect(await screen.findByText("Partly applied")).toBeInTheDocument();
    expect(screen.getByText("2 proposed changes did not apply.")).toBeInTheDocument();
  });

  it("names a turn waiting on a write as waiting on you, without asking for checks", async () => {
    stubFetch({
      [ROUTE]: outcome({
        outcome: "blocked",
        writes: 0,
        pending_writes: 1,
        reason: "A change this turn proposed is waiting for your approval; nothing has changed yet.",
      }),
    });
    render(BuildOutcome, { sessionId: "sess_1", turnId: "turn_1" });
    expect(await screen.findByText("Waiting on you")).toBeInTheDocument();
    expect(screen.queryByText(/Add checks to this project's context/)).toBeNull();
  });
});
