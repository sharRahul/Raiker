/**
 * QUI-W02 – W05 — first run as a setup conversation.
 *
 * Raiker asks, the owner answers with a card's buttons, and each answered step
 * stays above the next as a short exchange. Nothing secret is typed into the
 * conversation: an API key goes in the provider card's own secure field.
 * `firstRun.ts` keeps the stage order; this file keeps what is said.
 */
import { api } from "./api";

export const HELLO_LINE = "Hi, I'm Raiker. Let's set up three things, then do something useful. What should I call you?";
export const MODEL_QUESTION = "Where should I think?";
export const ASK_LINE = "Here is how I'll work for you.";
export const PROFILE_LINE = "I'll research and prepare on my own. I'll ask before I send, delete, pay or share anything.";
export const FIRST_TASK_READY = "You're set. What should we do first?";
export const FIRST_TASK_NO_MODEL = "Setup is saved. Chat and Build need a model before they can answer.";
/** QUI-W05 — the first conversation is kept in Threads under this name. */
export const FIRST_TASK_TITLE = "Getting started";

export interface SetupExchange {
  id: string;
  asked: string;
  answered: string;
}

/**
 * The steps already answered, as a conversation. Only steps the owner has
 * passed are drawn, and each answer is what was actually chosen.
 */
export function answeredExchanges(
  passed: readonly string[],
  answers: { name: string; model: string | null },
): SetupExchange[] {
  const exchanges: SetupExchange[] = [];
  if (passed.includes("welcome")) {
    exchanges.push({ id: "welcome", asked: HELLO_LINE, answered: answers.name.trim() || "Skipped" });
  }
  if (passed.includes("model")) {
    exchanges.push({ id: "model", asked: MODEL_QUESTION, answered: answers.model ?? "Decide later" });
  }
  if (passed.includes("privacy")) {
    exchanges.push({ id: "privacy", asked: ASK_LINE, answered: "Standard" });
  }
  return exchanges;
}

/**
 * Save the name Raiker calls the owner (`account.display_name`, the field
 * Settings › Account edits). Read first and written back with the revision,
 * so a setting saved elsewhere in the meantime is merged rather than lost.
 */
export async function saveOwnerName(name: string): Promise<void> {
  const current = await api.settings();
  const key = "account.display_name";
  await api.putSettings({ ...current.settings, [key]: name.trim() }, current.revision, { [key]: current.settings[key] ?? null });
}
