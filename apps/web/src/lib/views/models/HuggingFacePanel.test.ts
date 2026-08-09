import { fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { stubFetch } from "../../test-helpers";
import HuggingFacePanel from "./HuggingFacePanel.svelte";

afterEach(() => vi.unstubAllGlobals());

describe("HuggingFacePanel", () => {
  it("searches and labels ready GGUF separately from conversion sources", async () => {
    stubFetch({
      "GET /api/hugging-face/search": {
        items: [
          { repo_id: "org/model-GGUF", downloads: 42, likes: 3, gated: false },
        ],
      },
      "GET /api/hugging-face/org/model-GGUF/variants": {
        items: [
          {
            repo_id: "org/model-GGUF",
            revision: "a".repeat(40),
            files: ["model-Q4_K_M.gguf"],
            format: "gguf",
            quantization: "Q4_K_M",
            total_bytes: 100,
            cached_bytes: 0,
            gated: false,
            license_id: "apache-2.0",
            complete: true,
          },
          {
            repo_id: "org/model-GGUF",
            revision: "a".repeat(40),
            files: ["config.json", "model.safetensors"],
            format: "safetensors",
            quantization: null,
            total_bytes: 200,
            cached_bytes: 0,
            gated: false,
            license_id: "apache-2.0",
            complete: true,
          },
        ],
      },
      "GET /api/model-library": { roots: [{ path: "D:\\Models" }], models: [] },
    });
    render(HuggingFacePanel);
    await fireEvent.input(screen.getByLabelText("Search Hugging Face models"), {
      target: { value: "gemma" },
    });
    await fireEvent.click(
      screen.getByRole("button", { name: "Search models" }),
    );
    await fireEvent.click(await screen.findByText("org/model-GGUF"));
    expect(await screen.findByText("Q4_K_M")).toBeTruthy();
    expect(screen.getByText("Ready to deploy")).toBeTruthy();
    expect(screen.getByText("Requires isolated conversion")).toBeTruthy();
  });
});
