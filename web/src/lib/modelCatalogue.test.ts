import { describe, expect, it } from "vitest";
import type { ModelProfile } from "./apiTypes";
import {
  catalogueChoices,
  MAX_SEARCH_RESULTS,
  searchCatalogue,
  searchSummary,
} from "./modelCatalogue";

function profile(partial: Partial<ModelProfile> = {}): ModelProfile {
  return {
    profile_id: "anthropic-hosted",
    provider: "anthropic",
    model: "claude-sonnet-4-5",
    default_state: "enabled_runtime",
    local_only: false,
    requires_network: true,
    endpoint_kind: "remote_hosted",
    requires_egress_policy: true,
    requires_budget_policy: true,
    runtime_gate: "hosted_model_runtime",
    off_machine: true,
    selected: false,
    connection_configured: true,
    configured: true,
    ready: true,
    ...partial,
  } as ModelProfile;
}

describe("what a picker can reach (GLOBAL-MODEL-06)", () => {
  it("offers a model the owner never curated", () => {
    // The whole point: "keep available" decided whether a model existed in any
    // composer at all. A provider serving four hundred offered the two dozen
    // that were ticked, and the rest may as well not have been published.
    const choices = catalogueChoices([profile()], {
      "anthropic-hosted": ["claude-sonnet-4-5", "claude-opus-4-1", "claude-haiku-4-5"],
    });

    expect(choices.map((choice) => choice.model)).toEqual([
      "claude-sonnet-4-5",
      "claude-opus-4-1",
      "claude-haiku-4-5",
    ]);
    // … and says which of them the owner actually works with, because that is
    // an ordering rather than a gate.
    expect(choices.filter((choice) => choice.pinned).map((choice) => choice.model)).toEqual([
      "claude-sonnet-4-5",
    ]);
  });

  it("keeps a curated model whose provider has never listed successfully", () => {
    // A provider that has never answered a listing still has the models the
    // owner selected before. Dropping those is the disappearance the catalogue
    // store exists to prevent.
    const choices = catalogueChoices([profile({ model: "claude-opus-4-1" })], {});

    expect(choices).toHaveLength(1);
    expect(choices[0]).toMatchObject({ model: "claude-opus-4-1", pinned: true });
  });

  it("never lists one model twice because two sources named it", () => {
    const choices = catalogueChoices([profile({ model: "claude-opus-4-1" })], {
      "anthropic-hosted": ["claude-opus-4-1", "claude-sonnet-4-5"],
    });

    expect(choices.map((choice) => choice.model)).toEqual([
      "claude-opus-4-1",
      "claude-sonnet-4-5",
    ]);
  });

  it("keeps the same model name apart when two providers both serve it", () => {
    // `gpt-4o` from a direct OpenAI connection and from a router are different
    // choices: different credentials, different price, different policy.
    const choices = catalogueChoices(
      [profile({ profile_id: "openai-hosted", provider: "openai", model: "gpt-4o" })],
      { "openrouter-hosted": ["gpt-4o"] },
    );

    expect(choices).toHaveLength(2);
    expect(choices.map((choice) => choice.profile_id)).toEqual([
      "openai-hosted",
      "openrouter-hosted",
    ]);
  });
});

describe("finding a model in a catalogue nobody can scroll", () => {
  const many = Array.from({ length: 412 }, (_, index) => `router/model-${index}`);
  const choices = catalogueChoices([profile({ model: "claude-opus-4-1" })], {
    "anthropic-hosted": ["claude-opus-4-1", "claude-sonnet-4-5"],
    "openrouter-hosted": many,
  });

  it("shows nothing until the owner asks for something", () => {
    // An empty query is not a request for four hundred rows.
    expect(searchCatalogue(choices, "")).toEqual([]);
    expect(searchCatalogue(choices, "   ")).toEqual([]);
    expect(searchSummary(choices, "")).toBe("");
  });

  it("finds a model by the name the owner reads, not only its identifier", () => {
    const found = searchCatalogue(choices, "opus");
    expect(found.map((choice) => choice.model)).toContain("claude-opus-4-1");
  });

  it("puts what the owner works with above what they have never used", () => {
    const found = searchCatalogue(choices, "claude");
    expect(found[0].pinned).toBe(true);
  });

  it("caps a huge result set and says that it did", () => {
    const found = searchCatalogue(choices, "router/model");
    expect(found).toHaveLength(MAX_SEARCH_RESULTS);
    // A truncated list that does not say so reads as a small catalogue.
    expect(searchSummary(choices, "router/model")).toBe(
      `Showing ${MAX_SEARCH_RESULTS} of 412 matches. Narrow the search to see more.`,
    );
  });

  it("says plainly when nothing matches", () => {
    expect(searchCatalogue(choices, "gemma")).toEqual([]);
    expect(searchSummary(choices, "gemma")).toBe("No model matches “gemma”.");
  });

  it("counts a small result set exactly rather than rounding to the cap", () => {
    expect(searchSummary(choices, "claude-opus")).toBe("1 model matches “claude-opus”.");
  });
});
