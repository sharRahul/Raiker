import { fireEvent, render, screen } from "@testing-library/svelte";
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
});
