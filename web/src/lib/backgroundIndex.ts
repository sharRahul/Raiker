/**
 * FIXED-1426 — what the background indexer last did, in the owner's words.
 *
 * The worker (`raiker/memory/background_index.py`) keeps semantic recall current
 * with the built-in embedding model and writes its last outcome to the
 * workspace's logs. Memory › Engine reads it back so "is recall keeping up?" has
 * an answer on screen, and each state says what would change it.
 */
import type { BackgroundIndexView } from "./generated/apiContract";
import { relativeTime } from "./format";

export type BackgroundIndexTone = "ok" | "attention" | "quiet";

export interface BackgroundIndexCopy {
  tone: BackgroundIndexTone;
  text: string;
  /** Where the owner goes to change it, when something is in their hands. */
  action?: { label: string; href: string };
}

export function backgroundIndexCopy(view: BackgroundIndexView | null | undefined, now: Date = new Date()): BackgroundIndexCopy | null {
  if (!view) return null;
  if (view.disabled) {
    return { tone: "quiet", text: "Background indexing is off on this computer (RAIKER_BACKGROUND_INDEX=off). Embed by hand below." };
  }
  const when = view.at ? ` ${relativeTime(view.at, now)}` : "";
  switch (view.state) {
    case "indexed":
      return { tone: "ok", text: `Indexed ${view.indexed} new ${view.indexed === 1 ? "item" : "items"} with ${view.model}${when}.` };
    case "up_to_date":
      return { tone: "ok", text: `Up to date with ${view.model}${when ? ` — checked${when}` : ""}.` };
    case "waiting_for_permission":
      return {
        tone: "attention",
        text: `Waiting: the local model runtime is not set to Always allow or Auto, so background indexing asks nothing and does nothing.`,
        action: { label: "Open Permissions", href: "#/capabilities" },
      };
    case "model_missing":
      return { tone: "attention", text: `${view.model} is not on this computer yet; Raiker asks Ollama for it on the next pass.` };
    case "ollama_unreachable":
      return {
        tone: "attention",
        text: "Ollama is not reachable on this computer, so recall matches words only until it is running.",
        action: { label: "Open Models", href: "#/models" },
      };
    case "no_owner":
      return { tone: "quiet", text: "Background indexing starts once this workspace has an owner." };
    default:
      return {
        tone: "attention",
        text: `The last background pass did not finish${when}${view.reason_code ? ` (${view.reason_code})` : ""}. It tries again in ten minutes.`,
      };
  }
}
