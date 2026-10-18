/**
 * The shape of first launch, held apart from the screen that draws it.
 *
 * Each of these corresponds to one finding in the first-launch review: the
 * onboarding was secure and honest, and it still behaved like a configuration
 * wizard — an Account stage after the account existed, a provider matrix as the
 * opening move, a backup path requested before first use, and a privacy control
 * that read like a second Permissions.
 */
import { describe, expect, it } from "vitest";
import type { ModelProfile } from "./apiTypes";
import {
  nextStage,
  PERMISSIONS_NOTE,
  previousStage,
  PRIVACY_STATEMENT,
  recommendedPath,
  SETUP_STAGES,
  stagesFor,
  visibleStage,
} from "./firstRun";

const profile = (over: Partial<ModelProfile>): ModelProfile =>
  ({
    profile_id: "p",
    provider: "ollama",
    model: "<model>",
    default_state: "enabled_runtime",
    local_only: true,
    requires_network: false,
    endpoint_kind: "loopback",
    requires_egress_policy: false,
    requires_budget_policy: false,
    runtime_gate: null,
    off_machine: false,
    selected: false,
    connection_configured: false,
    prompt_cache_ttl: null,
    ...over,
  }) as ModelProfile;

describe("the stages first launch shows", () => {
  it("opens on the product and never asks for an account twice", () => {
    expect([...SETUP_STAGES]).toEqual(["welcome", "system", "model", "privacy", "permissions", "verify", "finish"]);
    expect(SETUP_STAGES).not.toContain("account");
  });

  it("does not stand backup between an owner and their first turn", () => {
    expect(SETUP_STAGES).not.toContain("backup");
  });

  it("renders a row stored under a retired stage rather than a blank screen", () => {
    // An instance part-way through the previous wizard has one of these stored.
    expect(visibleStage("account")).toBe("welcome");
    expect(visibleStage("backup")).toBe("finish");
    expect(visibleStage(null)).toBe("welcome");
    expect(visibleStage("model")).toBe("model");
    expect(visibleStage("system")).toBe("system");
    expect(visibleStage("verify")).toBe("verify");
    expect(visibleStage("finish")).toBe("finish");
  });

  it("does not repeat the checks a desktop installer already ran (DIST-05)", () => {
    const desktop = stagesFor("desktop");
    expect([...desktop]).toEqual(["model", "privacy", "finish"]);
    // A source checkout or server install had no installer step: it keeps the
    // device and installation checks.
    const source = stagesFor("payload");
    expect([...source]).toEqual(["system", "model", "privacy", "verify", "finish"]);
    expect(stagesFor(null)).toEqual(source);
    // A row stored on a stage this rail skips opens on the stage after it.
    expect(visibleStage("system", desktop)).toBe("model");
    expect(visibleStage("verify", desktop)).toBe("finish");
    expect(nextStage(desktop, "model")).toBe("privacy");
    expect(nextStage(desktop, "privacy")).toBe("finish");
    expect(previousStage(desktop, "finish")).toBe("privacy");
    expect(nextStage(source, "privacy")).toBe("verify");
    expect(previousStage(source, "finish")).toBe("verify");
    expect(previousStage(desktop, "model")).toBe("model");
  });

  it("no longer shows Welcome or Permissions (Quiet UI)", () => {
    // Welcome introduced what the app shows a moment later; Permissions was a
    // read-only copy of the Permissions page. Rows stored on either open on
    // the next stage that is shown.
    for (const distribution of ["desktop", "payload"]) {
      const shown = stagesFor(distribution);
      expect(shown).not.toContain("welcome");
      expect(shown).not.toContain("permissions");
    }
    expect(visibleStage("welcome", stagesFor("desktop"))).toBe("model");
    expect(visibleStage("welcome", stagesFor("payload"))).toBe("system");
    expect(visibleStage("permissions", stagesFor("desktop"))).toBe("finish");
    expect(visibleStage(null, stagesFor("desktop"))).toBe("model");
  });
});

describe("what the model stage recommends", () => {
  it("prefers a runtime installed on this machine", () => {
    const recommended = recommendedPath([
      profile({
        profile_id: "anthropic-hosted",
        provider: "anthropic",
        local_only: false,
        connection_configured: true,
      }),
      profile({ profile_id: "ollama-local", provider_detected: true, configured: true }),
    ]);

    expect(recommended?.profileId).toBe("ollama-local");
    // Detection is a PATH lookup, so the claim is "installed", not "running".
    expect(recommended?.label).toContain("installed here");
  });

  /**
   * BUG-340 — a running Ollama listed a cloud model, and setup said its models
   * never leave this device. The device claim is earned from the service's own
   * per-model answer.
   */
  it("names the cloud destination when the runtime serves a cloud model", () => {
    const recommended = recommendedPath([
      profile({
        profile_id: "ollama-local",
        provider_detected: true,
        provider_running: true,
        configured: true,
        model_locations: { "llama3:latest": "device", "gpt-oss:20b-cloud": "ollama.com" },
      }),
    ]);
    expect(recommended?.label).toBe("Ollama is running here");
    expect(recommended?.detail).not.toContain("never leave this device");
    expect(recommended?.detail).toContain("ollama.com");
  });

  it("claims the device only when every served model runs on it", () => {
    const allLocal = recommendedPath([
      profile({
        profile_id: "ollama-local",
        provider_detected: true,
        configured: true,
        model_locations: { "llama3:latest": "device" },
      }),
    ]);
    expect(allLocal?.detail).toContain("never leave this device");
    const undescribed = recommendedPath([
      profile({ profile_id: "ollama-local", provider_detected: true, configured: true }),
    ]);
    expect(undescribed?.detail).not.toContain("never leave this device");
  });

  it("does not recommend an installed runtime that names no model", () => {
    // A managed llama.cpp slot before anything is deployed into it.
    const bare = profile({
      profile_id: "raiker-local-llama-cpp",
      provider: "llama.cpp",
      provider_detected: true,
      configured: false,
    });
    expect(recommendedPath([bare])).toBeNull();

    const ollama = profile({ profile_id: "ollama-local", provider_detected: true, configured: true });
    expect(recommendedPath([bare, ollama])?.profileId).toBe("ollama-local");
  });

  /**
   * REM-MODEL-01 — the recommendation passes through the one reachability
   * answer, so "the cheapest path to a working model" cannot name a backend
   * whose last check said it does not work.
   */
  it("does not recommend a connected provider whose key was rejected", () => {
    const recommended = recommendedPath([
      profile({
        profile_id: "anthropic-hosted",
        provider: "anthropic",
        local_only: false,
        off_machine: true,
        connection_configured: true,
        readiness_state: "authentication_failed",
      }),
    ]);

    expect(recommended).toBeNull();
  });

  it("does not recommend a running runtime that has no model to serve", () => {
    const recommended = recommendedPath([
      profile({
        profile_id: "ollama-local",
        provider_detected: true,
        readiness_state: "model_missing",
      }),
    ]);

    expect(recommended).toBeNull();
  });

  it("falls back to a provider the owner has already connected", () => {
    const recommended = recommendedPath([
      profile({
        profile_id: "anthropic-hosted",
        provider: "anthropic",
        local_only: false,
        connection_configured: true,
      }),
    ]);

    expect(recommended?.profileId).toBe("anthropic-hosted");
    expect(recommended?.label).toContain("connected");
  });

  it("recommends nothing when there is nothing to recommend", () => {
    // A screen that guesses on the owner's behalf here would be recommending a
    // provider they have no account with.
    expect(recommendedPath([profile({ profile_id: "ollama-local" })])).toBeNull();
    expect(recommendedPath([])).toBeNull();
  });
});

describe("what first launch says about privacy and permissions", () => {
  it("states where content travels, not an authority", () => {
    expect(PRIVACY_STATEMENT.detail.toLowerCase()).not.toContain("permission");
    // BUG-345 — nothing enforced *Local only*, so it is not offered.
    expect(PRIVACY_STATEMENT.detail).not.toMatch(/Local only/);
    expect(PRIVACY_STATEMENT.detail).toMatch(/choose a model that runs here/);
  });

  it("records the one wire value the runtime behaves as", () => {
    expect(PRIVACY_STATEMENT.mode).toBe("balanced");
  });

  it("states the posture in one sentence rather than listing the gates", () => {
    expect(PERMISSIONS_NOTE).toMatch(/ask you/i);
    expect(PERMISSIONS_NOTE.length).toBeLessThan(200);
  });
});

describe("BUG-332 — a stored key is not a working connection", () => {
  const anthropic = profile({
    profile_id: "anthropic-hosted",
    provider: "anthropic",
    local_only: false,
    off_machine: true,
    connection_configured: true,
  });

  it("asks for the workspace ID when the provider said it needs one", () => {
    const recommended = recommendedPath([anthropic], {
      "anthropic-hosted": "provider_workspace_required",
    });
    expect(recommended?.action).toBe("workspace");
    expect(recommended?.label).toBe("Anthropic needs its workspace ID");
  });

  it("reads the stored check too, before anything is listed on this screen", () => {
    const checked = { ...anthropic, readiness_reason_code: "provider_workspace_required" } as ModelProfile;
    expect(recommendedPath([checked])?.action).toBe("workspace");
  });

  it("prefers another provider that does work", () => {
    const openrouter = profile({
      profile_id: "openrouter-policy-gated",
      provider: "openrouter",
      local_only: false,
      off_machine: true,
      connection_configured: true,
    });
    const recommended = recommendedPath([anthropic, openrouter], {
      "anthropic-hosted": "provider_workspace_required",
    });
    expect(recommended?.profileId).toBe("openrouter-policy-gated");
    expect(recommended?.action).toBe("choose");
  });

  it("says connected once the workspace is named and the models list", () => {
    expect(recommendedPath([anthropic], { "anthropic-hosted": null })?.label).toBe(
      "Anthropic is connected",
    );
  });
});

