// MODEL-01/MODEL-02 — the client half of the one authoritative model decision.
//
// Two claims, and the second was found the hard way. The first is that `design`
// is a surface like the others: it was missing from the backend allowlist while
// the product model was Chat | Build | Design, so an owner who put Chat on a
// small local model had their image prompts follow it there.
//
// The second is that a decision is *checked* before any surface renders from
// it. The mocked end-to-end fixture answers an unrouted path with `{}` and HTTP
// 200; the composer's model picker read `decision.selected.profile_id` off that
// and took the page down. The fixture is artificial, the failure it produced is
// not — a truncated body, a proxy's error page served as JSON, or a running
// host older than the build all arrive exactly that way.
import { afterEach, describe, expect, it, vi } from "vitest";
import { stubFetch } from "./test-helpers";
import {
  WORK_SURFACES,
  isModelDecision,
  modelDecision,
  modelDecisions,
  surfaceModel,
} from "./surfaceModel.svelte";

afterEach(() => vi.unstubAllGlobals());

const DECISION = {
  scope: { surface: "chat", project_id: null },
  selected: { profile_id: "anthropic-hosted", model: "claude-sonnet-4-5", source: "surface_default" },
  effective: { profile_id: "anthropic-hosted", model: "claude-sonnet-4-5", reason: "selected" },
  ready: true,
  running: null,
  problem: null,
  revision: "abc1234567890def",
};

describe("the Work surfaces", () => {
  it("names all three Work modes", () => {
    // MODEL-02. The union in this module mirrors `raiker.models.decision.SURFACES`
    // exactly; a surface added on one side and not the other is the same defect.
    expect([...WORK_SURFACES]).toEqual(["chat", "build", "design"]);
  });
});

describe("a decision is checked before it is trusted", () => {
  it("accepts one that carries the contract", () => {
    expect(isModelDecision(DECISION)).toBe(true);
  });

  it.each([
    ["an empty object, which is what a 200 with no body looks like", {}],
    ["null", null],
    ["a string", "not a decision"],
    ["a body missing `effective`", { ...DECISION, effective: undefined }],
    ["a body missing `selected`", { ...DECISION, selected: undefined }],
    ["a `selected` with no model", { ...DECISION, selected: { profile_id: "p" } }],
    ["a body whose `ready` is not a boolean", { ...DECISION, ready: "yes" }],
  ])("rejects %s", (_why, body) => {
    expect(isModelDecision(body)).toBe(false);
  });
});

describe("reading one surface's decision", () => {
  it("returns the decision the host answered with", async () => {
    stubFetch({ "GET /api/model-decision": DECISION });
    const answer = await modelDecision("design");
    expect(answer?.selected.model).toBe("claude-sonnet-4-5");
  });

  it("asks about the surface it was given", async () => {
    const mock = stubFetch({ "GET /api/model-decision": DECISION });
    await modelDecision("design");
    expect(String(mock.mock.calls[0][0])).toContain("surface=design");
  });

  it("treats a malformed answer as no answer", async () => {
    // Not a degraded decision — no decision. The surfaces render correctly
    // without one, minus the line that explains a fallback, and that is
    // strictly better than a composer that will not draw.
    stubFetch({ "GET /api/model-decision": {} });
    expect(await modelDecision("chat")).toBeNull();
  });

  it("treats a failed read as no answer", async () => {
    stubFetch({});
    expect(await modelDecision("chat")).toBeNull();
  });
});

describe("reading every surface at once", () => {
  it("keeps the surfaces that carry the contract", async () => {
    stubFetch({
      "GET /api/model-decisions": {
        surfaces: { chat: DECISION, build: { ...DECISION, scope: { surface: "build", project_id: null } } },
      },
    });
    const answer = await modelDecisions();
    expect(Object.keys(answer ?? {}).sort()).toEqual(["build", "chat"]);
  });

  it("drops a surface whose entry is malformed rather than failing the rest", async () => {
    // One bad row must not cost the page every other row: the Models Overview
    // draws five surfaces and four correct ones are still worth showing.
    stubFetch({
      "GET /api/model-decisions": { surfaces: { chat: DECISION, build: {} } },
    });
    expect(Object.keys((await modelDecisions()) ?? {})).toEqual(["chat"]);
  });

  it("answers null when nothing in the body is a decision", async () => {
    stubFetch({ "GET /api/model-decisions": { surfaces: {} } });
    expect(await modelDecisions()).toBeNull();
  });

  it("answers null when the body has no surfaces at all", async () => {
    stubFetch({ "GET /api/model-decisions": {} });
    expect(await modelDecisions()).toBeNull();
  });
});

describe("a surface's remembered model", () => {
  it("is null when the surface has no opinion", async () => {
    stubFetch({ "GET /api/surface-models": { surfaces: {} } });
    expect(await surfaceModel("design")).toBeNull();
  });

  it("reads the pair the surface stored", async () => {
    stubFetch({
      "GET /api/surface-models": {
        surfaces: { design: { profile_id: "openai-hosted", model: "gpt-image-1" } },
      },
    });
    expect(await surfaceModel("design")).toEqual({
      profileId: "openai-hosted",
      model: "gpt-image-1",
    });
  });

  it("does not hand one surface another's default", async () => {
    stubFetch({
      "GET /api/surface-models": {
        surfaces: { chat: { profile_id: "openai-hosted", model: "gpt-5" } },
      },
    });
    expect(await surfaceModel("design")).toBeNull();
  });
});
