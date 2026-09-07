import { fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import type { ModelReadinessView } from "../apiTypes";
import { resetModelSetup, setupDialog } from "../modelReadiness.svelte";
import ModelReadinessStrip from "./ModelReadinessStrip.svelte";

const stopped: ModelReadinessView = {
  owner_principal_id: "principal_owner",
  profile_id: "ollama-local-openai-compatible",
  model: "gemma4:31b-cloud",
  endpoint_fingerprint: "fingerprint",
  state: "runtime_stopped",
  checked_at: "2026-08-09T10:00:00Z",
  expires_at: "2026-08-09T10:05:00Z",
  summary: "Ollama is not reachable.",
  reason_code: "local_runtime_unreachable",
  remediation: "Start Ollama, then check again.",
  evidence: { provider: "ollama" },
  ready: false,
};

afterEach(() => resetModelSetup());

describe("ModelReadinessStrip", () => {
  it("explains the disabled action, preserves the draft, and delegates setup", async () => {
    const initialHash = window.location.hash;
    render(ModelReadinessStrip, { readiness: stopped, draftPreserved: true });

    expect(screen.getByText("Ollama is not reachable.")).toBeInTheDocument();
    expect(screen.getByText("Your draft is preserved.")).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Set up model" }));

    expect(setupDialog.open).toBe(true);
    expect(setupDialog.readiness?.reason_code).toBe("local_runtime_unreachable");
    expect(window.location.hash).toBe(initialHash);
  });

  it("renders nothing once the exact model is ready", () => {
    render(ModelReadinessStrip, {
      readiness: { ...stopped, state: "ready", ready: true },
    });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  // BUG-238 — an observation that aged out is not an unset-up model. The server
  // re-checks it before admitting the turn, so asking the owner to "set up" a
  // model they already set up was work invented by a timer.
  it("says it is re-checking a stale model rather than asking for setup", () => {
    render(ModelReadinessStrip, {
      readiness: {
        ...stopped,
        state: "stale",
        summary: "The last model check has expired.",
        reason_code: "readiness_expired",
        remediation: "Check this model again before sending.",
      },
      draftPreserved: true,
    });

    expect(screen.getByText(/checking this model/i)).toBeInTheDocument();
    expect(screen.getByText(/you can still send/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Set up model" })).not.toBeInTheDocument();
  });

  it("still asks for setup when the model is genuinely unavailable", () => {
    render(ModelReadinessStrip, { readiness: stopped });
    expect(screen.getByRole("button", { name: "Set up model" })).toBeInTheDocument();
    expect(screen.queryByText(/re-checking this model/i)).not.toBeInTheDocument();
  });
});
