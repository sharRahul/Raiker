import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ModelReadinessView } from "../apiTypes";
import { openModelSetup, resetModelSetup } from "../modelReadiness.svelte";
import ModelSetupDialog from "./ModelSetupDialog.svelte";

const missing: ModelReadinessView = {
  owner_principal_id: "principal_owner",
  profile_id: "ollama-local-openai-compatible",
  model: "gemma4:31b-cloud",
  endpoint_fingerprint: "fingerprint",
  state: "not_configured",
  checked_at: null,
  expires_at: null,
  summary: "No readiness check exists for this exact model.",
  reason_code: "model_not_checked",
  remediation: "Set up or check this model before sending.",
  evidence: { provider: "ollama" },
  ready: false,
};

afterEach(() => {
  resetModelSetup();
  window.location.hash = "";
});

describe("ModelSetupDialog", () => {
  it("states that no model is set up and links to Models without losing draft context", async () => {
    render(ModelSetupDialog, { readiness: missing, draftPreserved: true });

    expect(screen.getByRole("dialog", { name: "Set up a model to continue" })).toBeInTheDocument();
    expect(screen.getByText("Your draft is preserved.")).toBeInTheDocument();
    expect(screen.getByText("model_not_checked")).not.toBeVisible();
    await fireEvent.click(screen.getByRole("button", { name: "Open Models" }));
    expect(window.location.hash).toBe("#/models");
  });

  it("announces retry progress and returns focus to the trigger", async () => {
    const retry = vi.fn(async () => undefined);
    const trigger = document.createElement("button");
    trigger.textContent = "Send";
    document.body.append(trigger);
    trigger.focus();
    render(ModelSetupDialog, { onRetry: retry });
    openModelSetup(null, { ...missing, state: "runtime_stopped" });

    await fireEvent.click(await screen.findByRole("button", { name: "Check again" }));
    expect(retry).toHaveBeenCalledOnce();
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Check complete"));
    await fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(trigger).toHaveFocus();
    trigger.remove();
  });
});
