/**
 * QUI-F20 — when the owner corrects Raiker, offer to remember the correction.
 *
 * Only a message that *opens* as a correction counts ("That's wrong — Anna
 * prefers short replies", "No, the meeting is on Tuesday", "Actually, use
 * metric units"). What is offered is the rest of the owner's own sentence,
 * never a model's paraphrase, and it is only an offer: Save puts it through
 * Memory's own proposal and decision, Dismiss keeps nothing.
 */
const LEADS = [
  /^that'?s (?:wrong|not right|incorrect|not what i (?:meant|asked))\b[\s,.:;!—–-]*/i,
  /^(?:no|nope|wrong|incorrect|not quite)\b[\s,.:;!—–-]+/i,
  /^actually\b[\s,:;—–-]*/i,
];

/** The correction worth remembering, or `null` when the message is not one. */
export function correctionToRemember(message: string): string | null {
  const text = message.trim();
  for (const lead of LEADS) {
    const match = lead.exec(text);
    if (match === null) continue;
    // The correction is the first sentence after the lead; what follows is
    // usually an instruction for this turn ("…replies. Reply in one line."),
    // which is not something to remember (found live, RT-QUI-48).
    const rest = text.slice(match[0].length).trim().split(/(?<=[.!?])\s+/)[0] ?? "";
    if (rest.split(/\s+/).length < 3 || rest.length > 300 || rest.includes("\n")) return null;
    return rest.charAt(0).toUpperCase() + rest.slice(1);
  }
  return null;
}

/** The offer as a question: "Remember: Anna prefers short replies?" */
export function rememberQuestion(text: string): string {
  return `${text.replace(/[.!?…]+$/, "")}?`;
}
