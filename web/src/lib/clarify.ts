/**
 * QUI-F02 — a mid-task question's answer, built exactly as chosen.
 *
 * A turn asks with `ask_owner_question`, which parks it through the approval
 * transport without being an approval. The answer route takes either the
 * picked labels, which the server checks against what was offered, or the
 * owner's own words. Picks alone go back as picks; once anything is typed or
 * every question is skipped, the whole answer goes back as one message in the
 * owner's words, one line per question, so nothing they said is dropped.
 */
import type { OwnerQuestion } from "./apiTypes";

export const OWNER_QUESTION_TOOL = "ask_owner_question";

export type ClarifyReply = { picked: string[]; typed: string; skipped: boolean };

export type ClarifyBody = { answers: Record<string, string | string[]> } | { response: string };

/** One line per question: the question, then what was picked and typed, or Skipped. */
export function clarifyText(questions: readonly OwnerQuestion[], replies: readonly ClarifyReply[]): string {
  return questions
    .map((question, index) => {
      const reply = replies[index];
      if (reply === undefined || reply.skipped) return `${question.question} — Skipped`;
      const said = [...reply.picked, ...(reply.typed ? [reply.typed] : [])].join(", ");
      return `${question.question} — ${said}`;
    })
    .join("\n");
}

/** What the answer route is sent for these replies. */
export function clarifyBody(questions: readonly OwnerQuestion[], replies: readonly ClarifyReply[]): ClarifyBody {
  const typedAny = replies.some((reply) => !reply.skipped && reply.typed !== "");
  const pickedAny = replies.some((reply) => !reply.skipped && reply.picked.length > 0);
  if (typedAny || !pickedAny) return { response: clarifyText(questions, replies) };
  const answers: Record<string, string | string[]> = {};
  questions.forEach((question, index) => {
    const reply = replies[index];
    if (reply === undefined || reply.skipped || reply.picked.length === 0) return;
    answers[question.question] = reply.picked.length > 1 ? [...reply.picked] : reply.picked[0];
  });
  return { answers };
}

/** The questions a parked approval carries, or `null` when it is not a question. */
export function ownerQuestions(approval: { tool_name: string; arguments?: unknown } | null | undefined): OwnerQuestion[] | null {
  if (approval?.tool_name !== OWNER_QUESTION_TOOL) return null;
  const raw = (approval.arguments as { questions?: unknown } | undefined)?.questions;
  if (!Array.isArray(raw) || raw.length === 0) return null;
  return raw
    .filter((entry): entry is Record<string, unknown> => typeof entry === "object" && entry !== null)
    .map((entry) => ({
      question: String(entry.question ?? ""),
      header: String(entry.header ?? ""),
      multiSelect: entry.multiSelect === true,
      options: Array.isArray(entry.options)
        ? entry.options
            .filter((option): option is Record<string, unknown> => typeof option === "object" && option !== null)
            .map((option) => ({ label: String(option.label ?? ""), description: String(option.description ?? "") }))
            .filter((option) => option.label !== "")
        : [],
    }))
    .filter((question) => question.question !== "");
}
