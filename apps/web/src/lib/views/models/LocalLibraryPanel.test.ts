import { render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { stubFetch } from "../../test-helpers";
import LocalLibraryPanel from "./LocalLibraryPanel.svelte";

afterEach(() => vi.unstubAllGlobals());

describe("LocalLibraryPanel", () => {
  // MODEL-06 — the library answers "what is on disk"; the runtime slot rows
  // answer "what is serving". Deploy was the one control that crossed the two,
  // so a card here could put a model into a slot without ever showing which
  // slot it took or what it displaced. Serving is chosen where the slots are,
  // and `deployLocalModel` is still called from there.
  it("shows owner-approved roots and what is on disk, without deploying", async () => {
    stubFetch({
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
    });
    render(LocalLibraryPanel);
    expect(await screen.findByText("Gemma 4")).toBeTruthy();
    expect(screen.getByText("D:\\Models")).toBeTruthy();
    // A complete file states that it *could* serve. It does not offer to.
    expect(screen.getByText("Ready to serve")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Deploy" })).toBeNull();
  });

  it("states that no unapproved filesystem scan occurs", async () => {
    stubFetch({ "GET /api/model-library": { roots: [], models: [] } });
    render(LocalLibraryPanel);
    expect(
      await screen.findByText(/will not search the rest of your computer/i),
    ).toBeTruthy();
  });
});
