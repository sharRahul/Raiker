/**
 * The Hugging Face flow as steps, not as one screen of controls.
 *
 * Adding a local model is a sequence: find something, pick the right build of
 * it, look at what it will cost in bytes and licence, fetch it, convert it if
 * Raiker cannot run it as-is, and put it in the library. The panel already did
 * all six — it just did them all *at once*, so a first-time owner met a search
 * box, a token form, a curated card, a results list, a variants list, a
 * download drawer and a conversion card with nothing saying which of them was
 * their next move.
 *
 * The fix is not to hide anything. It is to say where you are. This module
 * derives that from the state the panel already holds, which matters more than
 * it sounds: a step counter kept as its own variable is a second source of
 * truth about the flow, and it will disagree with the flow — the owner goes
 * back to the results list, the counter still says step 4, and now the page is
 * lying about something the owner can plainly see.
 *
 * Conversion is the one conditional step. A GGUF is ready to run and skips it;
 * Safetensors needs it. So {@link huggingFaceSteps} returns the steps that
 * apply to *this* download rather than a fixed six, and a flow that never needs
 * conversion never shows a step it will not take.
 */

/** One step, as the rail draws it. */
export interface HuggingFaceStep {
  id: string;
  label: string;
  /** `done` is behind you, `active` is now, `ahead` has not been reached. */
  state: "done" | "active" | "ahead";
}

/** What the panel knows about where the owner has got to. */
export interface HuggingFaceProgress {
  /** A repository has been chosen from the results. */
  repoSelected: boolean;
  /** A specific variant (format + quantisation + revision) has been chosen. */
  variantSelected: boolean;
  /** The immutable revision, byte count and licence have been resolved. */
  previewReady: boolean;
  /** A download is running now. */
  downloading: boolean;
  /** The download finished and the file is on disk. */
  downloaded: boolean;
  /** This variant needs a GGUF conversion before Raiker can run it. */
  needsConversion: boolean;
  /** The conversion has been run. */
  converted: boolean;
}

const FIND = { id: "find", label: "Find model" };
const VARIANT = { id: "variant", label: "Choose variant" };
const REVIEW = { id: "review", label: "Review download" };
const DOWNLOAD = { id: "download", label: "Download" };
const CONVERT = { id: "convert", label: "Convert" };
const ADD = { id: "add", label: "Add to My models" };

/**
 * The steps this download involves, and which one is current.
 *
 * Derived entirely from `progress`. Nothing here is remembered between calls,
 * so the rail cannot drift from the panel it describes.
 */
export function huggingFaceSteps(progress: HuggingFaceProgress): HuggingFaceStep[] {
  const stages = [FIND, VARIANT, REVIEW, DOWNLOAD];
  if (progress.needsConversion) stages.push(CONVERT);
  stages.push(ADD);

  const reached = currentIndex(progress, stages.length);
  return stages.map((stage, index) => ({
    ...stage,
    state: index < reached ? "done" : index === reached ? "active" : "ahead",
  }));
}

/** The index of the step the owner is on. */
function currentIndex(progress: HuggingFaceProgress, total: number): number {
  // Read backwards: the furthest thing that is true decides where they are.
  // Forwards, every early condition would have to be re-checked against every
  // later one, and one missed pair is a rail that sticks on step 2.
  if (progress.needsConversion && progress.downloaded && !progress.converted) {
    return total - 2;
  }
  if (progress.downloaded) return total - 1;
  if (progress.downloading) return progress.needsConversion ? total - 3 : total - 2;
  if (progress.previewReady) return 2;
  if (progress.variantSelected) return 2;
  if (progress.repoSelected) return 1;
  return 0;
}

/**
 * Whether the access-token control belongs on screen right now.
 *
 * The flow is specific about this one: the token button was a permanent
 * equal-weight hero action beside the search box, which told every owner that
 * signing in to Hugging Face was a normal part of downloading a public model.
 * It is not — it is needed for a gated or private repository, and for nothing
 * else. So it appears when the selected repository actually needs it, and
 * otherwise lives under Advanced for the owner who came looking for it.
 */
export function tokenControlVisible(options: {
  selectedRepoGated: boolean;
  advancedOpen: boolean;
}): boolean {
  return options.selectedRepoGated || options.advancedOpen;
}
