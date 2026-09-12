/*
 * GLOBAL-MODEL-06 — what a picker can reach, as opposed to what it offers at
 * rest.
 *
 * "Keep available" decided whether a model appeared in any composer at all, so
 * curation was a prerequisite for visibility: a provider serving four hundred
 * models offered whichever two dozen the owner had ticked, and the rest may as
 * well not have existed. The plan supersedes that —
 *
 *   > All discovered compatible models are available by default.
 *   > Remove `Keep available` as a prerequisite for composer visibility.
 *
 * — while keeping curation as the convenience it always should have been:
 * pinned and recent models are the quick list, and *search must still be able
 * to find the full provider catalogue*.
 *
 * Both halves matter. A flat list of four hundred names is not availability
 * either; BUG-260 already recorded that scrolling one "is not choosing, it is
 * hunting". So the quick list stays short and the catalogue is a keystroke
 * away, which is what this module derives.
 */

import type { ModelProfile } from "./apiTypes";
import { modelName } from "./modelPresentation";

/** One model a picker can offer, whether or not the owner curated it. */
export interface CatalogueChoice {
  profile_id: string;
  provider: string;
  model: string;
  /**
   * True when this model is already in the owner's quick list. The quick list
   * is an ordering, never a gate: a model absent from it is still selectable,
   * it simply is not one of the few shown at rest.
   */
  pinned: boolean;
}

/** How many catalogue matches a search shows before asking for a narrower query. */
export const MAX_SEARCH_RESULTS = 40;

/** The key that identifies one choice: a model belongs to the profile serving it. */
function keyFor(profileId: string, model: string): string {
  return [profileId, model].join("::");
}

function haystackFor(choice: CatalogueChoice): string {
  return [choice.model, modelName(choice.model), choice.provider].join(" ").toLowerCase();
}

/**
 * Every model this owner could choose: what each provider last published,
 * plus anything already in the quick list.
 *
 * The quick list is included even when it is not in a stored catalogue, because
 * a provider that has never been listed successfully still has the models the
 * owner selected in the past, and dropping those would be the disappearance
 * GLOBAL-MODEL-08 exists to prevent.
 */
export function catalogueChoices(
  quickList: ModelProfile[],
  catalogues: Record<string, string[]>,
): CatalogueChoice[] {
  const providerOf = new Map<string, string>();
  for (const profile of quickList) providerOf.set(profile.profile_id, profile.provider);

  const choices: CatalogueChoice[] = [];
  const seen = new Set<string>();
  const add = (profileId: string, provider: string, model: string, pinned: boolean) => {
    const key = keyFor(profileId, model);
    if (model.trim() === "" || seen.has(key)) return;
    seen.add(key);
    choices.push({ profile_id: profileId, provider, model, pinned });
  };

  for (const profile of quickList) {
    add(profile.profile_id, profile.provider, profile.model, true);
  }
  for (const [profileId, models] of Object.entries(catalogues)) {
    const provider = providerOf.get(profileId) ?? profileId;
    for (const model of models) add(profileId, provider, model, false);
  }
  return choices;
}

/**
 * The catalogue, filtered by what the owner typed.
 *
 * Matches on the model's displayed name as well as its identifier, because an
 * owner searching "opus" is using the word they read, not the string the
 * provider ships. Pinned models sort first: when a query matches both something
 * the owner works with and forty things they have never used, the former is
 * what they meant.
 */
export function searchCatalogue(choices: CatalogueChoice[], query: string): CatalogueChoice[] {
  const needle = query.trim().toLowerCase();
  if (needle === "") return [];
  const matches = choices.filter((choice) => haystackFor(choice).includes(needle));
  matches.sort((a, b) => Number(b.pinned) - Number(a.pinned));
  return matches.slice(0, MAX_SEARCH_RESULTS);
}

/**
 * How a search result set describes itself.
 *
 * A truncated list has to say so. "40 of 412" is the difference between a
 * catalogue that looks small and one the owner knows to narrow.
 */
export function searchSummary(choices: CatalogueChoice[], query: string): string {
  const needle = query.trim().toLowerCase();
  if (needle === "") return "";
  const total = choices.filter((choice) => haystackFor(choice).includes(needle)).length;
  const asked = query.trim();
  if (total === 0) return `No model matches “${asked}”.`;
  if (total <= MAX_SEARCH_RESULTS) {
    // "1 model matches", "2 models match": the verb agrees too.
    return total === 1 ? `1 model matches “${asked}”.` : `${total} models match “${asked}”.`;
  }
  return `Showing ${MAX_SEARCH_RESULTS} of ${total} matches. Narrow the search to see more.`;
}
