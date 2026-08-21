import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../api";
import CredentialDeltaReview from "./CredentialDeltaReview.svelte";

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it("shows only safe delta metadata and discards through an owner decision", async () => {
  vi.spyOn(api, "credentialDeltas").mockResolvedValue({ deltas: [{
    run_id: "cmd_1", environment_profile_id: "container_a", state: "quarantined",
    manifest: { files: [{ path: "result.txt", kind: "file", size: 10 }] },
    delta_digest: "a".repeat(64), scan_digest: "b".repeat(64),
    scan_rule_version: "raiker-redaction-v1", cleanup_status: "pending",
    created_at: "2026-08-21T00:00:00Z", recipient_boundary: "disposable_container_tcb",
  }] });
  const discard = vi.spyOn(api, "discardCredentialDelta").mockResolvedValue({ ok: true, receipt: {} });
  vi.stubGlobal("confirm", () => true);
  vi.stubGlobal("crypto", { randomUUID: () => "decision_1" });
  render(CredentialDeltaReview, { runId: "cmd_1", profileId: "container_a" });

  expect(await screen.findByText("result.txt")).toBeInTheDocument();
  expect(screen.getByText(/Matched bytes, credential values/)).toBeInTheDocument();
  await fireEvent.click(screen.getByRole("button", { name: "Discard quarantined changes" }));
  await waitFor(() => expect(discard).toHaveBeenCalledWith("cmd_1", "decision_1"));
  expect(screen.queryByText("result.txt")).not.toBeInTheDocument();
});
