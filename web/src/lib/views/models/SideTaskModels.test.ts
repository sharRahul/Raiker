// Hermes Agent's auxiliary models: a model per side task, each with its own fallback.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { modelProfile, modelsView, stubFetch } from "../../test-helpers";
import SideTaskModels from "./SideTaskModels.svelte";

afterEach(() => vi.unstubAllGlobals());

const gemma = modelProfile({ profile_id: "ollama-local-openai-compatible", provider: "ollama", model: "gemma4:31b-cloud" });

describe("side-task models", () => {
  it("says what each task falls back to and adds a model to a chain", async () => {
    const mock = stubFetch({
      "PUT /api/model-side-tasks": {
        ok: true,
        task: "vision",
        chain: [{ profile_id: gemma.profile_id, model: gemma.model }],
      },
    });
    const onreload = vi.fn(async () => {});
    render(SideTaskModels, {
      props: { models: modelsView({ profiles: [gemma], chat_profiles: [gemma] }), onreload },
    });
    const summarise = screen.getByRole("group", { name: "Summarising models" });
    expect(summarise).toHaveTextContent("Uses the turn's own model.");
    const vision = screen.getByRole("group", { name: "Vision models" });
    expect(vision).toHaveTextContent(/images go unseen/);

    await fireEvent.change(within(vision).getByRole("combobox"), {
      target: { value: JSON.stringify([gemma.profile_id, gemma.model]) },
    });
    await fireEvent.click(within(vision).getByRole("button", { name: "Add" }));
    await waitFor(() => {
      const put = mock.mock.calls.find((c) => String(c[0]).includes("/api/model-side-tasks"));
      expect(put).toBeTruthy();
      expect(JSON.parse(put![1]!.body as string)).toEqual({
        task: "vision",
        chain: [{ profile_id: gemma.profile_id, model: gemma.model }],
      });
    });
    expect(onreload).toHaveBeenCalled();
  });

  it("explains a model that cannot see", async () => {
    stubFetch({
      "PUT /api/model-side-tasks": { __status: 400, detail: { reason_code: "side_task_model_lacks_vision" } },
    });
    render(SideTaskModels, {
      props: { models: modelsView({ profiles: [gemma], chat_profiles: [gemma] }), onreload: async () => {} },
    });
    const vision = screen.getByRole("group", { name: "Vision models" });
    await fireEvent.change(within(vision).getByRole("combobox"), {
      target: { value: JSON.stringify([gemma.profile_id, gemma.model]) },
    });
    await fireEvent.click(within(vision).getByRole("button", { name: "Add" }));
    expect(await within(vision).findByRole("status")).toHaveTextContent("does not accept images");
  });
});
