/**
 * QUI-P02 — how much Raiker does without asking, for one conversation.
 *
 * Decided 2026-10-22: the chip is per conversation and only ever **narrows**
 * the owner's own settings.
 *
 * * **Standard** (the default) — the owner's Permissions, as set. It sends no
 *   override at all.
 * * **Careful** — every capability that changes something waits for the
 *   owner, including ones Permissions allows. It is sent as the turn-scoped
 *   `capability_modes` map the runtime already enforces for Build's Edit mode
 *   (BUG-70): `ask` for each such capability, applied to that turn only. The
 *   runtime accepts only `ask` and `deny` there, so the chip cannot widen
 *   anything, and an `ask` it names also overrides an automatic approval mode.
 * * **Within limits** — Standard plus the owner's Allow-with-limits rules. It is
 *   not offered until those rules exist (QUI-P03).
 *
 * The global approval mode (Automatically approve, Skip, Decline) is not a
 * composer choice: it lives in Permissions › Advanced.
 */
import type { CapabilityGate } from "./apiTypes";

export type ConversationProfile = "careful" | "standard";

export const DEFAULT_PROFILE: ConversationProfile = "standard";

export const CONVERSATION_PROFILES: ReadonlyArray<{
  id: ConversationProfile;
  label: string;
  /** The consequence, in the menu. */
  consequence: string;
}> = [
  {
    id: "careful",
    label: "Careful",
    consequence: "Asks before every change, even ones your permissions allow. Reading and searching go ahead.",
  },
  {
    id: "standard",
    label: "Standard",
    consequence: "Follows your permissions as set: what they allow goes ahead, what they ask about waits for you.",
  },
];

/** Side-effect classes that change nothing, so Careful leaves them alone. */
const READS = new Set(["read", ""]);

/**
 * The turn-scoped override a profile sends with a prompt. Empty for Standard,
 * which sends nothing; for Careful, `ask` for every capability whose side
 * effect is more than a read.
 */
export function profileCapabilityModes(
  profile: ConversationProfile,
  gates: readonly Pick<CapabilityGate, "capability" | "side_effect">[] | null,
): Record<string, string> {
  if (profile !== "careful" || gates === null) return {};
  return Object.fromEntries(
    gates
      .filter((gate) => !READS.has(gate.side_effect ?? ""))
      .map((gate) => [gate.capability, "ask"]),
  );
}

export function profileLabel(profile: ConversationProfile): string {
  return CONVERSATION_PROFILES.find((item) => item.id === profile)?.label ?? "Standard";
}

/**
 * Where an earlier build kept the choice: this browser's storage, per
 * conversation. Read once, so a choice made before the profile moved to the
 * conversation is carried over rather than lost (`profileFromSession`).
 */
const LEGACY_KEY = "raiker.conversation-profile.";

/**
 * The profile a conversation carries, from its session record.
 *
 * Decided 2026-10-25: the profile belongs to the conversation, so another
 * device opening it sees the same choice. A Careful choice still sitting in
 * this browser from before is written to the conversation once, then forgotten
 * here; the server's answer wins in every other case.
 */
export function profileFromSession(
  sessionId: string,
  stored: string | null | undefined,
  save: (sessionId: string, profile: ConversationProfile) => void,
): ConversationProfile {
  const server: ConversationProfile = stored === "careful" ? "careful" : DEFAULT_PROFILE;
  let legacy: string | null;
  try {
    legacy = localStorage.getItem(`${LEGACY_KEY}${sessionId}`);
    localStorage.removeItem(`${LEGACY_KEY}${sessionId}`);
  } catch {
    legacy = null;
  }
  if (server === DEFAULT_PROFILE && legacy === "careful") {
    save(sessionId, "careful");
    return "careful";
  }
  return server;
}
