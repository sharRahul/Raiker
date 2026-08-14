import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../api";
import type { CommandRunView } from "../apiTypes";
import CommandOutputPane from "./CommandOutputPane.svelte";

afterEach(() => vi.restoreAllMocks());

const run: CommandRunView = {
  run_id: "cmd_1",
  session_id: "sess_1",
  turn_id: "turn_1",
  action_id: "act_1",
  authority_kind: "approval",
  authority_id: "approval_1",
  state: "succeeded",
  profile_id: "local_native",
  backend: "local_strict",
  safe_display: "git status --short",
  started_at: "2026-08-14T10:00:00Z",
  completed_at: "2026-08-14T10:00:01Z",
  exit_code: 0,
  termination_reason: "succeeded",
  stdout_bytes: 6,
  stderr_bytes: 0,
  truncated: false,
  redaction_count: 0,
  receipt_digest: "abc123def456",
  created_at: "2026-08-14T10:00:00Z",
  updated_at: "2026-08-14T10:00:01Z",
};

it("shows the authoritative environment, redacted output, and immutable receipt", async () => {
  vi.spyOn(api, "executionEnvironments").mockResolvedValue({
    selected_profile_id: "local_native",
    environments: [{
      profile_id: "local_native", kind: "local", name: "Local strict", enabled: true,
      configured: true, available: true, status: "ready", selected: true,
      credential_configured: false, budget: null, cost: null,
    }],
  });
  vi.spyOn(api, "commandRuns").mockResolvedValue({ runs: [run] });
  vi.spyOn(api, "commandOutput").mockResolvedValue({
    chunks: [{
      run_id: "cmd_1", sequence: 1, stream: "stdout", text: "clean\n", byte_count: 6,
      emitted_at: "2026-08-14T10:00:01Z", start_byte_offset: 0, end_byte_offset: 6,
    }],
    next_after: 1,
  });
  vi.spyOn(api, "commandReceipt").mockResolvedValue({
    receipt: {
      run_id: "cmd_1", state: "succeeded", exit_code: 0,
      termination_reason: "succeeded", completed_at: "2026-08-14T10:00:01Z",
      evidence: { backend: "local_strict" }, digest: "abc123def456",
    },
  });

  render(CommandOutputPane, { sessionId: "sess_1" });
  await fireEvent.click(screen.getByRole("button", { name: /Governed terminal/i }));

  expect(await screen.findByText("Selected environment is authoritative")).toBeInTheDocument();
  expect(await screen.findByText("clean")).toBeInTheDocument();
  expect(await screen.findByText(/Immutable receipt/)).toBeInTheDocument();
  expect(screen.getByText("local_strict")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Run" })).not.toBeInTheDocument();
  expect(screen.getByText(/Commands start through the governed agent path/i)).toBeInTheDocument();
});

it("refreshes when reopened after an approval ran while Build was hidden", async () => {
  vi.spyOn(api, "executionEnvironments").mockResolvedValue({
    selected_profile_id: "local_native",
    environments: [],
  });
  const runs = vi
    .spyOn(api, "commandRuns")
    .mockResolvedValueOnce({ runs: [] })
    .mockResolvedValue({ runs: [run] });
  vi.spyOn(api, "commandOutput").mockResolvedValue({ chunks: [], next_after: 0 });
  vi.spyOn(api, "commandReceipt").mockResolvedValue({
    receipt: {
      run_id: "cmd_1", state: "succeeded", exit_code: 0,
      termination_reason: "succeeded", completed_at: "2026-08-14T10:00:01Z",
      evidence: { backend: "local_strict" }, digest: "abc123def456",
    },
  });

  render(CommandOutputPane, { sessionId: "sess_1" });
  await waitFor(() => expect(runs).toHaveBeenCalledTimes(1));
  await fireEvent.click(screen.getByRole("button", { name: /Governed terminal/i }));

  await waitFor(() => expect(runs).toHaveBeenCalledTimes(2));
  expect(await screen.findByText("git status --short")).toBeInTheDocument();
});

it("refreshes an already-open terminal when Build becomes visible again", async () => {
  vi.spyOn(api, "executionEnvironments").mockResolvedValue({
    selected_profile_id: "local_native",
    environments: [],
  });
  const runs = vi
    .spyOn(api, "commandRuns")
    .mockResolvedValueOnce({ runs: [] })
    .mockResolvedValue({ runs: [run] });
  vi.spyOn(api, "commandOutput").mockResolvedValue({ chunks: [], next_after: 0 });
  vi.spyOn(api, "commandReceipt").mockResolvedValue({
    receipt: {
      run_id: "cmd_1", state: "succeeded", exit_code: 0,
      termination_reason: "succeeded", completed_at: "2026-08-14T10:00:01Z",
      evidence: { backend: "local_strict" }, digest: "abc123def456",
    },
  });

  const view = render(CommandOutputPane, { sessionId: "sess_1", visible: true });
  await waitFor(() => expect(runs).toHaveBeenCalledTimes(1));
  await fireEvent.click(screen.getByRole("button", { name: /Governed terminal/i }));
  await view.rerender({ sessionId: "sess_1", visible: false });
  await view.rerender({ sessionId: "sess_1", visible: true });

  await waitFor(() => expect(runs).toHaveBeenCalledTimes(3));
  expect(await screen.findByText("git status --short")).toBeInTheDocument();
});

it("selects the new session's run instead of retaining a stale run id", async () => {
  const secondRun: CommandRunView = {
    ...run,
    run_id: "cmd_2",
    session_id: "sess_2",
    safe_display: "git --version",
  };
  vi.spyOn(api, "executionEnvironments").mockResolvedValue({
    selected_profile_id: "local_native",
    environments: [],
  });
  vi.spyOn(api, "commandRuns").mockImplementation(async (sessionId) => ({
    runs: sessionId === "sess_2" ? [secondRun] : [run],
  }));
  vi.spyOn(api, "commandOutput").mockResolvedValue({ chunks: [], next_after: 0 });
  vi.spyOn(api, "commandReceipt").mockImplementation(async (runId) => ({
    receipt: {
      run_id: runId, state: "succeeded", exit_code: 0,
      termination_reason: "succeeded", completed_at: "2026-08-14T10:00:01Z",
      evidence: { backend: "local_strict" }, digest: "abc123def456",
    },
  }));

  const view = render(CommandOutputPane, { sessionId: "sess_1", visible: true });
  await fireEvent.click(screen.getByRole("button", { name: /Governed terminal/i }));
  expect(await screen.findByText("git status --short")).toBeInTheDocument();

  await view.rerender({ sessionId: "sess_2", visible: true });
  expect(await screen.findByText("git --version")).toBeInTheDocument();
});
