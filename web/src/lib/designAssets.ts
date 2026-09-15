/*
 * What Design's canvas is a canvas *of*.
 *
 * The review asks for Assets, Canvas and Inspector around an object, with a
 * version strip and a variation grid. Every one of those needs a relationship
 * between pictures, and until BUG-277 there was none: the governed endpoint took
 * a prompt and returned one picture, so a "version history" would have been a
 * list sorted by time and called a history.
 *
 * There is one now. A generation carries `source_generation_id` — what it was
 * made from — and `kind`: `create` made something from a prompt alone, `edit`
 * changed a named image, `variation` asked the same question again. This module
 * turns those two fields into the three things the canvas draws, and it is a
 * plain module rather than view code because each of them is a claim worth
 * testing on its own.
 *
 * The rule underneath all of it: a chain of single parents is a history. Nothing
 * here invents a relationship the runtime did not record — an asset whose parent
 * is missing is an origin, not a broken row, because a source can be forgotten
 * while the images made from it remain.
 */
import type { ImageGeneration } from "./apiTypes";

/** One asset on the canvas, with the two relationships the runtime recorded. */
export interface DesignAsset {
  generation: ImageGeneration;
  /** What this was made from, when the parent is still present. */
  parent: ImageGeneration | null;
  /** Everything made directly from this one, oldest first. */
  children: ImageGeneration[];
}

const idOf = (generation: ImageGeneration) => generation.generation_id;

/** Only a generation that produced a picture can be a subject or a version. */
export function isAsset(generation: ImageGeneration): boolean {
  return generation.status === "ok" && generation.has_image === true;
}

/**
 * The assets, newest first, each joined to its parent and its children.
 *
 * Refusals are deliberately excluded. They belong in the history of the asset
 * they were about — which is what `refusalsFor` is for — and not on a canvas
 * that is showing pictures, because a refusal has no picture to show.
 */
export function designAssets(generations: ImageGeneration[]): DesignAsset[] {
  const byId: Record<string, ImageGeneration> = {};
  for (const generation of generations) byId[idOf(generation)] = generation;

  const childrenOf: Record<string, ImageGeneration[]> = {};
  for (const generation of generations) {
    if (!isAsset(generation)) continue;
    const source = generation.source_generation_id;
    if (!source) continue;
    (childrenOf[source] ??= []).push(generation);
  }
  for (const list of Object.values(childrenOf)) {
    list.sort((left, right) => left.created_at.localeCompare(right.created_at));
  }

  return generations
    .filter(isAsset)
    .slice()
    .sort((left, right) => right.created_at.localeCompare(left.created_at))
    .map((generation) => ({
      generation,
      parent: generation.source_generation_id
        ? (byId[generation.source_generation_id] ?? null)
        : null,
      children: childrenOf[idOf(generation)] ?? [],
    }));
}

/**
 * The chain of versions an asset belongs to, oldest first.
 *
 * Walks up to the origin and back down the line the selected asset is actually
 * on — not every descendant of the origin. Two edits of the same picture are two
 * branches, and putting both in one strip would say the second came after the
 * first when neither came from the other.
 *
 * Cycle-guarded: `source_generation_id` is not a foreign key, so a store that
 * somehow held a loop would otherwise hang the page rather than draw a strip.
 */
export function versionChain(
  generations: ImageGeneration[],
  selectedId: string,
): ImageGeneration[] {
  const byId: Record<string, ImageGeneration> = {};
  for (const generation of generations) {
    if (isAsset(generation)) byId[idOf(generation)] = generation;
  }
  const selected = byId[selectedId];
  if (!selected) return [];

  const ancestry: ImageGeneration[] = [selected];
  const seen = new Set([selectedId]);
  let walker = selected;
  while (walker.source_generation_id) {
    const parent = byId[walker.source_generation_id];
    if (!parent || seen.has(idOf(parent))) break;
    seen.add(idOf(parent));
    ancestry.unshift(parent);
    walker = parent;
  }
  return ancestry;
}

/**
 * The siblings produced by the same request as *selectedId*.
 *
 * A variation request stores one row per picture, all sharing a source and a
 * timestamp, which is exactly what a 2-up or 4-up compare grid is for. An asset
 * with no siblings returns an empty list rather than a grid of one.
 */
export function variationSet(
  generations: ImageGeneration[],
  selectedId: string,
): ImageGeneration[] {
  const selected = generations.find((generation) => idOf(generation) === selectedId);
  if (!selected || !isAsset(selected) || selected.kind !== "variation") return [];
  const siblings = generations.filter(
    (generation) =>
      isAsset(generation) &&
      generation.kind === "variation" &&
      generation.created_at === selected.created_at &&
      (generation.source_generation_id ?? null) === (selected.source_generation_id ?? null),
  );
  return siblings.length > 1
    ? siblings.sort((left, right) => idOf(left).localeCompare(idOf(right)))
    : [];
}

/**
 * The refused attempts that named *selectedId* as their subject.
 *
 * An edit that was denied is still something the owner asked of this picture, so
 * the inspector can say so beside it. This is the reason the executor records
 * lineage on refusals as well as successes.
 */
export function refusalsFor(
  generations: ImageGeneration[],
  selectedId: string,
): ImageGeneration[] {
  return generations
    .filter(
      (generation) =>
        generation.status !== "ok" && generation.source_generation_id === selectedId,
    )
    .sort((left, right) => right.created_at.localeCompare(left.created_at));
}

/**
 * What pressing the primary button will do, in the word for that act.
 *
 * COMPOSER-15 asks every surface's primary action to name what the press
 * performs, and Design's now has three answers because it has three requests.
 * The word follows the *state*, never the other way round: it says Edit only
 * when an asset is selected, because only then is there a subject for an edit
 * to be about.
 */
export function designPrimaryAction(
  selectedId: string | null,
  variations: number,
): string {
  if (selectedId) return "Edit";
  return variations > 1 ? `Generate ${variations}` : "Generate";
}

/**
 * The most pictures one request may ask for.
 *
 * Mirrors `MAX_VARIATIONS` in `raiker/runtime/executors/tier2_image.py`, which
 * is the bound that actually enforces it — a count is an action argument, and an
 * action argument is a thing a model can propose. This constant exists so the
 * picker cannot offer a number the runtime will refuse; the runtime refusing it
 * is what makes the bound real.
 */
export const MAX_DESIGN_VARIATIONS = 4;

/** How the inspector names the act that produced an asset. */
export const KIND_LABEL: Record<string, string> = {
  create: "Generated",
  edit: "Edited from",
  variation: "One of a set",
};
