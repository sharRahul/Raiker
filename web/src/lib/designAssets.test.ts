/*
 * What Design's canvas can honestly draw.
 *
 * the Design canvas asks for a version strip, a variation grid and an inspector that says
 * where an asset came from. Each of those is a claim about a *relationship*
 * between pictures, and the only relationships that exist are the two the
 * runtime records: `source_generation_id` and `kind`. These tests hold the line
 * between deriving from those and inventing on top of them — a list sorted by
 * time is not a history, and the moment it is drawn as one the canvas is lying
 * about which picture came from which.
 */
import { describe, expect, it } from "vitest";
import type { ImageGeneration } from "./apiTypes";
import {
  designAssets,
  designPrimaryAction,
  isAsset,
  refusalsFor,
  variationSet,
  versionChain,
} from "./designAssets";

function gen(over: Partial<ImageGeneration> & { generation_id: string }): ImageGeneration {
  return {
    profile_id: "openai-hosted",
    provider: "openai",
    model: "gpt-image-1",
    prompt: "a leaf",
    size: "1024x1024",
    status: "ok",
    reason_code: null,
    has_image: true,
    media_type: "image/png",
    byte_size: 100,
    created_at: "2026-09-12T10:00:00Z",
    kind: "create",
    source_generation_id: null,
    ...over,
  };
}

describe("what counts as an asset", () => {
  it("is a generation that produced a picture", () => {
    expect(isAsset(gen({ generation_id: "a" }))).toBe(true);
  });

  it("is not a refusal, which has no picture to show", () => {
    expect(
      isAsset(gen({ generation_id: "a", status: "refused", has_image: false })),
    ).toBe(false);
  });

  it("is not a row that claims success with nothing stored", () => {
    expect(isAsset(gen({ generation_id: "a", has_image: false }))).toBe(false);
  });
});

describe("the asset rail", () => {
  it("is newest first, and joins each asset to its parent and children", () => {
    const assets = designAssets([
      gen({ generation_id: "origin", created_at: "2026-09-12T10:00:00Z" }),
      gen({
        generation_id: "edit",
        created_at: "2026-09-12T11:00:00Z",
        kind: "edit",
        source_generation_id: "origin",
      }),
    ]);

    expect(assets.map((a) => a.generation.generation_id)).toEqual(["edit", "origin"]);
    expect(assets[0].parent?.generation_id).toBe("origin");
    expect(assets[1].children.map((c) => c.generation_id)).toEqual(["edit"]);
  });

  it("keeps refusals off a canvas that is showing pictures", () => {
    const assets = designAssets([
      gen({ generation_id: "ok" }),
      gen({ generation_id: "no", status: "refused", has_image: false }),
    ]);

    expect(assets.map((a) => a.generation.generation_id)).toEqual(["ok"]);
  });

  it("treats an asset whose parent is gone as an origin, not a broken row", () => {
    // A source can be forgotten while the images made from it remain.
    const assets = designAssets([
      gen({ generation_id: "orphan", kind: "edit", source_generation_id: "long_gone" }),
    ]);

    expect(assets).toHaveLength(1);
    expect(assets[0].parent).toBeNull();
  });
});

describe("the version strip", () => {
  const chain = [
    gen({ generation_id: "v1", created_at: "2026-09-12T10:00:00Z" }),
    gen({
      generation_id: "v2",
      created_at: "2026-09-12T11:00:00Z",
      kind: "edit",
      source_generation_id: "v1",
    }),
    gen({
      generation_id: "v3",
      created_at: "2026-09-12T12:00:00Z",
      kind: "edit",
      source_generation_id: "v2",
    }),
  ];

  it("walks to the origin, oldest first", () => {
    expect(versionChain(chain, "v3").map((g) => g.generation_id)).toEqual([
      "v1",
      "v2",
      "v3",
    ]);
  });

  it("stops at the selected version rather than running past it", () => {
    // Selecting v2 is looking at v2. v3 came after it and is not one of its
    // versions; it is a thing made *from* it.
    expect(versionChain(chain, "v2").map((g) => g.generation_id)).toEqual(["v1", "v2"]);
  });

  it("shows only the line the selection is on, when a picture was edited twice", () => {
    // Two edits of v1 are two branches. A strip holding both would say the
    // second came after the first, when neither came from the other.
    const branched = [
      chain[0],
      gen({ generation_id: "left", kind: "edit", source_generation_id: "v1" }),
      gen({ generation_id: "right", kind: "edit", source_generation_id: "v1" }),
    ];

    expect(versionChain(branched, "right").map((g) => g.generation_id)).toEqual([
      "v1",
      "right",
    ]);
  });

  it("is empty for a selection that is not an asset", () => {
    expect(versionChain(chain, "nothing")).toEqual([]);
    expect(
      versionChain([gen({ generation_id: "no", status: "refused", has_image: false })], "no"),
    ).toEqual([]);
  });

  it("does not hang on a store that somehow holds a loop", () => {
    // `source_generation_id` is not a foreign key, so this is defended rather
    // than assumed away.
    const looped = [
      gen({ generation_id: "a", kind: "edit", source_generation_id: "b" }),
      gen({ generation_id: "b", kind: "edit", source_generation_id: "a" }),
    ];

    expect(versionChain(looped, "a").map((g) => g.generation_id)).toEqual(["b", "a"]);
  });
});

describe("the variation grid", () => {
  const set = [
    gen({
      generation_id: "s1",
      kind: "variation",
      created_at: "2026-09-12T11:00:00Z",
      source_generation_id: null,
    }),
    gen({
      generation_id: "s2",
      kind: "variation",
      created_at: "2026-09-12T11:00:00Z",
      source_generation_id: null,
    }),
  ];

  it("is the siblings produced by the same request", () => {
    expect(variationSet(set, "s1").map((g) => g.generation_id)).toEqual(["s1", "s2"]);
  });

  it("is empty for an ordinary generation, so a grid of one is never drawn", () => {
    expect(variationSet([gen({ generation_id: "only" })], "only")).toEqual([]);
  });

  it("does not gather two separate requests that happen to share a subject", () => {
    const later = gen({
      generation_id: "s3",
      kind: "variation",
      created_at: "2026-09-12T12:00:00Z",
    });

    expect(variationSet([...set, later], "s3")).toEqual([]);
  });
});

describe("the refusals an asset collected", () => {
  it("are shown against the picture they were about", () => {
    // The reason the executor records lineage on refusals as well as successes.
    const rows = [
      gen({ generation_id: "asset" }),
      gen({
        generation_id: "denied",
        status: "refused",
        has_image: false,
        kind: "edit",
        source_generation_id: "asset",
        reason_code: "image_refused_by_provider",
      }),
    ];

    expect(refusalsFor(rows, "asset").map((g) => g.reason_code)).toEqual([
      "image_refused_by_provider",
    ]);
  });

  it("do not include refusals that named no subject", () => {
    const rows = [
      gen({ generation_id: "asset" }),
      gen({ generation_id: "denied", status: "refused", has_image: false }),
    ];

    expect(refusalsFor(rows, "asset")).toEqual([]);
  });
});

describe("the word on the primary button", () => {
  it("says Edit only when there is a subject for an edit to be about", () => {
    expect(designPrimaryAction("img_1", 1)).toBe("Edit");
    expect(designPrimaryAction(null, 1)).toBe("Generate");
  });

  it("names the count when more than one picture is being asked for", () => {
    expect(designPrimaryAction(null, 4)).toBe("Generate 4");
  });

  it("still says Edit when a selection and a count are both set", () => {
    // The subject is what changes the act; the count changes how many.
    expect(designPrimaryAction("img_1", 4)).toBe("Edit");
  });
});
