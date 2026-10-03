// BUG-311 — the overview and setup's Ready step gave two answers about Design.
//
// Design researches on the chat model and draws on an image model. Its model
// decision is the research half, so "ready" there said nothing about drawing,
// and the overview printed **Ready** beside a model that returns no images
// while setup, reading `image_models`, said Design still needed a provider.
import { render, screen, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { modelProfile, modelsView, stubFetch } from "../../test-helpers";
import ModelsOverview from "./ModelsOverview.svelte";

afterEach(() => vi.unstubAllGlobals());

const decision = (surface: string) => ({
  scope: { surface, project_id: null },
  selected: { profile_id: "ollama-local-openai-compatible", model: "gpt-oss:20b-cloud", source: "global_default" },
  effective: { profile_id: "ollama-local-openai-compatible", model: "gpt-oss:20b-cloud", reason: "selected" },
  ready: true,
  running: null,
  problem: null,
  revision: "abc1234567890def",
});

const chatModel = modelProfile({
  profile_id: "ollama-local-openai-compatible",
  provider: "ollama",
  model: "gpt-oss:20b-cloud",
  configured: true,
  readiness_state: "ready",
  ready: true,
});

async function designRow(profiles = [chatModel]) {
  stubFetch({
    "GET /api/model-decisions": {
      surfaces: { chat: decision("chat"), build: decision("build"), design: decision("design") },
    },
  });
  const onopen = vi.fn();
  render(ModelsOverview, { models: modelsView({ profiles }), onopen });
  const label = await screen.findByText("Design");
  return { row: label.closest("li") as HTMLElement, onopen };
}

describe("BUG-311 — Design is ready to draw only when a model returns images", () => {
  it("says research only, and offers the fix, when nothing connected returns images", async () => {
    const { row, onopen } = await designRow();

    expect(within(row).getByText("Research only")).toBeInTheDocument();
    expect(within(row).queryByText("Ready")).not.toBeInTheDocument();
    expect(within(row).getByText(/no connected model returns images/i)).toBeInTheDocument();
    within(row).getByRole("button", { name: "Connect an image provider" }).click();
    expect(onopen).toHaveBeenCalledWith("add");
  });

  it("stays plainly ready when a reachable model draws", async () => {
    const images = modelProfile({
      profile_id: "openai-hosted",
      provider: "openai",
      model: "gpt-4o",
      off_machine: true,
      connection_configured: true,
      image_models: ["gpt-image-1"],
    });
    const { row } = await designRow([chatModel, images]);

    expect(within(row).getByText("Ready")).toBeInTheDocument();
    expect(within(row).queryByText("Research only")).not.toBeInTheDocument();
  });

  it("leaves Chat and Build alone: they never draw", async () => {
    await designRow();
    const chat = (await screen.findByText("Chat")).closest("li") as HTMLElement;
    expect(within(chat).getByText("Ready")).toBeInTheDocument();
  });
});

// UX-MODEL-02 — "connected", "discovered", "selected" and "runs" were four facts
// in four places. The decision now carries them as four ordered steps and one
// next action, and the overview draws them while one is not done.
describe("UX-MODEL-02 — a four-step readiness line with one next action", () => {
  const steps = (states: string[]) =>
    ["connect", "discover", "choose", "run"].map((id, index) => ({
      id,
      label: ["Provider connected", "Model found", "Model chosen", "Runs"][index],
      state: states[index],
    }));

  async function renderWith(chat: Record<string, unknown>, extra: Record<string, unknown> = {}) {
    const fetchMock = stubFetch({
      "GET /api/model-decisions": {
        surfaces: { chat, build: decision("build"), design: decision("design") },
      },
      ...extra,
    });
    const onopen = vi.fn();
    render(ModelsOverview, { models: modelsView({ profiles: [chatModel] }), onopen });
    const label = await screen.findByText("Chat", { selector: ".surface-name" });
    return { row: label.closest("li") as HTMLElement, onopen, fetchMock };
  }

  it("names the blocked step and offers only its action", async () => {
    const { row, onopen } = await renderWith({
      ...decision("chat"),
      ready: false,
      problem: {
        reason_code: "provider_authentication_failed",
        summary: "Anthropic rejected the saved credential.",
        remediation: "Update the provider credential and check again.",
      },
      steps: steps(["blocked", "waiting", "waiting", "waiting"]),
      next_action: { label: "Update the credential", target: "add" },
    });

    const line = within(row).getByRole("list", { name: "Chat readiness" });
    const items = within(line).getAllByRole("listitem");
    expect(items.map((item) => item.dataset.state)).toEqual([
      "blocked", "waiting", "waiting", "waiting",
    ]);
    expect(within(items[0]).getByText(/needs you/)).toBeInTheDocument();
    // One primary action in the row, and the attention list uses the same word.
    const buttons = screen.getAllByRole("button", { name: "Update the credential" });
    expect(buttons).toHaveLength(2);
    within(row).getByRole("button", { name: "Update the credential" }).click();
    expect(onopen).toHaveBeenCalledWith("add");
  });

  it("draws nothing extra on a ready row", async () => {
    const { row } = await renderWith({
      ...decision("chat"),
      steps: steps(["done", "done", "done", "done"]),
      next_action: null,
    });
    expect(within(row).getByText("Ready")).toBeInTheDocument();
    expect(within(row).queryByTestId("model-readiness-steps")).not.toBeInTheDocument();
  });

  it("runs the exact-pair check in place for an unchecked model and re-reads", async () => {
    const { row, fetchMock } = await renderWith(
      {
        ...decision("chat"),
        ready: false,
        problem: {
          reason_code: "model_not_checked",
          summary: "No readiness check exists for this exact model.",
          remediation: "Set up or check this model before sending.",
        },
        steps: steps(["done", "unchecked", "done", "unchecked"]),
        next_action: { label: "Check it now", target: "check" },
      },
      { "POST /api/model-readiness/check": { state: "ready", ready: true } },
    );
    within(row).getByRole("button", { name: "Check it now" }).click();
    await vi.waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url, init]) =>
          String(url).includes("/api/model-readiness") && (init as RequestInit | undefined)?.method === "POST",
        ),
      ).toBe(true),
    );
    await vi.waitFor(() =>
      expect(
        fetchMock.mock.calls.filter(([url]) => String(url).includes("/api/model-decisions")).length,
      ).toBeGreaterThan(1),
    );
  });

  it("is absent on a host that sends no steps", async () => {
    const { row } = await renderWith({ ...decision("chat"), ready: false, problem: null });
    expect(within(row).queryByTestId("model-readiness-steps")).not.toBeInTheDocument();
  });
});
