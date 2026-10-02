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
