import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { stubFetch } from "../../test-helpers";
import LocalLibraryPanel from "./LocalLibraryPanel.svelte";

afterEach(() => vi.unstubAllGlobals());

describe("LocalLibraryPanel", () => {
  it("shows owner-approved roots and deployable GGUF inventory", async () => {
    const mock = stubFetch({
      "GET /api/model-library": {
        roots: [{ path: "D:\\Models" }],
        models: [
          {
            owner_principal_id: "owner",
            root_path: "D:\\Models",
            model_id: "models/gemma",
            name: "Gemma 4",
            architecture: "gemma",
            quantization: "Q4_K_M",
            primary_path: "D:\\Models\\gemma.gguf",
            shard_count: 1,
            expected_shards: 1,
            complete: true,
            size_bytes: 4294967296,
            indexed_at: "now",
          },
        ],
      },
      "POST /api/model-library/models%2Fgemma/deploy": {
        operation_id: "mop_1",
        state: "queued",
      },
    });
    render(LocalLibraryPanel);
    expect(await screen.findByText("Gemma 4")).toBeTruthy();
    expect(screen.getByText("D:\\Models")).toBeTruthy();
    await fireEvent.click(screen.getByRole("button", { name: "Deploy" }));
    await waitFor(() =>
      expect(mock).toHaveBeenCalledWith(
        "/api/model-library/models%2Fgemma/deploy",
        expect.anything(),
      ),
    );
  });

  it("states that no unapproved filesystem scan occurs", async () => {
    stubFetch({ "GET /api/model-library": { roots: [], models: [] } });
    render(LocalLibraryPanel);
    expect(
      await screen.findByText(/will not search the rest of your computer/i),
    ).toBeTruthy();
  });
});
