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
});
