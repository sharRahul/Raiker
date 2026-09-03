// BUG-238 — what actually stops a send.
//
// A readiness observation expires so no turn runs on a claim older than the
// owner's window. It was also deciding whether the model was *configured*: once
// the window passed, the composer disabled Send and offered "Set up model" —
// for a model the owner had already set up, after every restart and after any
// five idle minutes.
//
// The server now re-takes a stale observation before admitting the turn, so the
// browser has nothing to block on. Every other not-ready state is a real answer
// about the model and still blocks, because those are the ones an owner can fix.
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ModelReadinessView } from "./apiTypes";
import { blocksSending, isRevalidating, revalidateSelectedModel } from "./modelReadiness.svelte";
import { resetModels, selectedModelReadiness } from "./models.svelte";
import { setToken } from "./api";
import { stubFetch } from "./test-helpers";

function readiness(overrides: Partial<ModelReadinessView> = {}): ModelReadinessView {
  return {
    owner_principal_id: "principal_owner",
    profile_id: "ollama-local-openai-compatible",
    model: "gemma4:31b-cloud",
    endpoint_fingerprint: "fingerprint",
    state: "ready",
    checked_at: "2026-08-23T10:00:00Z",
    expires_at: "2026-08-23T10:05:00Z",
    summary: "The exact model is reachable.",
    reason_code: "model_ready",
    remediation: "",
    evidence: {},
    ready: true,
    ...overrides,
  };
}

const STALE = readiness({
  state: "stale",
  ready: false,
  summary: "The last model check has expired.",
  reason_code: "readiness_expired",
});

describe("model readiness gating", () => {
  it("does not block a send on an observation that merely aged out", () => {
    expect(isRevalidating(STALE)).toBe(true);
    expect(blocksSending(STALE)).toBe(false);
  });

  it("blocks a send when the model is genuinely unavailable", () => {
    for (const state of [
      "runtime_stopped",
      "authentication_failed",
      "quota_exhausted",
      "model_missing",
      "policy_blocked",
      "unreachable",
    ] as const) {
      const view = readiness({ state, ready: false, reason_code: state });
      expect(blocksSending(view), state).toBe(true);
      expect(isRevalidating(view), state).toBe(false);
    }
  });

  it("does not block a send on a connected provider nobody has checked yet", () => {
    // The server takes that first check before it admits the turn, so demanding
    // it by hand asked the owner to press Test on a provider they had just
    // connected and a model they had just selected.
    const unmeasured = readiness({
      state: "not_configured",
      ready: false,
      reason_code: "model_not_checked",
      evidence: { connection_configured: true },
    });
    expect(blocksSending(unmeasured)).toBe(false);
  });

  it("still blocks a send on a provider the owner has not connected", () => {
    // Raiker never reaches a provider on its own initiative, so an unchecked
    // model there is still the owner's to set up.
    const unconnected = readiness({
      state: "not_configured",
      ready: false,
      reason_code: "model_not_checked",
      evidence: { connection_configured: false },
    });
    expect(blocksSending(unconnected)).toBe(true);
  });

  it("blocks a send when no model is named at all", () => {
    const nothing = readiness({
      state: "not_configured",
      ready: false,
      profile_id: "",
      model: "",
      reason_code: "model_not_configured",
    });
    expect(blocksSending(nothing)).toBe(true);
  });

  it("never blocks a ready model", () => {
    expect(blocksSending(readiness())).toBe(false);
    expect(isRevalidating(readiness())).toBe(false);
  });

  it("treats an absent readiness as nothing to block on", () => {
    // A surface that has not resolved a profile yet must not disable its own
    // composer on the strength of not knowing.
    expect(blocksSending(null)).toBe(false);
    expect(isRevalidating(null)).toBe(false);
  });
});

describe("background revalidation", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetModels();
    setToken(null);
  });

  it("asks for nothing before the owner has a session", async () => {
    // The loop starts at mount, which is the lock screen. Reaching /api/models
    // there earns a 401 and a console error on every single load.
    const fetchMock = stubFetch({ "GET /api/models": { profiles: [] } });
    await revalidateSelectedModel();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  // BUG-238 — the server re-checks a stale model when it admits a turn, so the
  // stored observation can become `ready` without the browser asking. The tick
  // used to return early when no check was due, leaving the composer saying
  // "Re-checking this model" long after the turn had finished.
  it("publishes what it read even when no check is due", async () => {
    const profile = {
      profile_id: "openai-hosted",
      provider: "openai",
      model: "gpt-4",
      configured: true,
      selected: true,
      ready: true,
      readiness_state: "ready",
      readiness_checked_at: new Date().toISOString(),
      readiness_expires_at: new Date(Date.now() + 300_000).toISOString(),
    };
    stubFetch({
      "GET /api/models": {
        profiles: [profile],
        chat_profiles: [profile],
        current_profile_id: "openai-hosted",
      },
    });

    setToken("test-token");
    expect(selectedModelReadiness()).toBeNull();
    await revalidateSelectedModel();

    expect(selectedModelReadiness()?.readiness_state).toBe("ready");
  });
});
