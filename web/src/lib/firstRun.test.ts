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
  PERMISSIONS_NOTE,
  PRIVACY_CHOICES,
  recommendedPath,
  SETUP_STAGES,
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
    expect([...SETUP_STAGES]).toEqual(["welcome", "model", "privacy", "finish"]);
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
  });
});

describe("what the model stage recommends", () => {
  it("prefers a runtime already running on this machine", () => {
    const recommended = recommendedPath([
      profile({
        profile_id: "anthropic-hosted",
        provider: "anthropic",
        local_only: false,
        connection_configured: true,
      }),
      profile({ profile_id: "ollama-local", provider_detected: true }),
    ]);

    expect(recommended?.profileId).toBe("ollama-local");
    expect(recommended?.label).toContain("already running here");
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
  it("asks about where content travels, not about authority", () => {
    expect(PRIVACY_CHOICES.map((choice) => choice.label)).toEqual([
      "Local only",
      "Local, and the providers I connect",
    ]);
    for (const choice of PRIVACY_CHOICES) {
      expect(choice.detail.toLowerCase()).not.toContain("permission");
    }
  });

  it("keeps the wire values, so a stored privacy mode still means what it did", () => {
    expect(PRIVACY_CHOICES.map((choice) => choice.mode)).toEqual([
      "local_first",
      "balanced",
    ]);
  });

  it("states the posture in one sentence rather than listing the gates", () => {
    expect(PERMISSIONS_NOTE).toMatch(/ask you/i);
    expect(PERMISSIONS_NOTE.length).toBeLessThan(200);
  });
});
