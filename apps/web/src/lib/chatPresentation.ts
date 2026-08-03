import type { StreamEvent } from "./apiTypes";

export interface ChatReaction {
  emoji: string;
  label: string;
}

const THINKING_COPY: Partial<Record<string, string>> = {
  intent_classified: "Understanding what you need.",
  context_gathered: "Reviewing the available context.",
  model_request_started: "Putting together a response.",
};

const REACTIONS: Array<{ pattern: RegExp; reaction: ChatReaction }> = [
  { pattern: /\b(thank you|thanks|you're welcome|happy to help|appreciate)\b/i, reaction: { emoji: "❤️", label: "Heart" } },
  { pattern: /\b(congratulations|congrats|well done|great job)\b/i, reaction: { emoji: "👏", label: "Clapping hands" } },
  { pattern: /\b(good luck|fingers crossed)\b/i, reaction: { emoji: "🤞", label: "Crossed fingers" } },
  { pattern: /\b(i agree|sounds good|absolutely|definitely|done)\b/i, reaction: { emoji: "👍", label: "Thumbs up" } },
  { pattern: /\b(hello|hi there|see you|goodbye)\b/i, reaction: { emoji: "👋", label: "Waving hand" } },
  { pattern: /\b(happy|glad|wonderful|lovely)\b/i, reaction: { emoji: "😊", label: "Smiling face" } },
  { pattern: /\b(exciting|celebrate|celebration)\b/i, reaction: { emoji: "🎉", label: "Party popper" } },
  { pattern: /\b(here for you|we can do this|together)\b/i, reaction: { emoji: "🤝", label: "Handshake" } },
  { pattern: /\b(laugh|funny|haha)\b/i, reaction: { emoji: "😂", label: "Face with tears of joy" } },
];

export function thinkingSteps(events: StreamEvent[]): string[] {
  const steps = events.flatMap((event) => {
    const copy = event.kind === "lifecycle" ? THINKING_COPY[event.event_type] : undefined;
    return copy ? [copy] : [];
  });
  return [...new Set(steps)];
}

export interface RefusedCall {
  toolName: string;
  reasons: string[];
}

/**
 * The calls policy refused during a turn, in the order they were refused (BUG-52).
 *
 * A refusal used to end the turn, so "denied" plus a reason was the whole story
 * Chat had to tell. Now that a refusal ends only its own call and the batch
 * carries on, the turn finishes normally — and without this the transcript would
 * show a call proposed and simply never answered.
 */
export function refusedCalls(events: StreamEvent[]): RefusedCall[] {
  const calls: RefusedCall[] = [];
  for (const event of events) {
    if (event.kind !== "lifecycle" || event.event_type !== "model_tool_call_refused") continue;
    const payload = event.payload ?? {};
    const toolName = typeof payload.tool_name === "string" ? payload.tool_name : "";
    if (toolName === "") continue;
    const reasons = Array.isArray(payload.reasons)
      ? payload.reasons.filter((reason): reason is string => typeof reason === "string")
      : [];
    calls.push({ toolName, reasons });
  }
  return calls;
}

export function reactionForPrompt(prompt: string): ChatReaction | null {
  if (prompt.trim() === "") return null;
  return REACTIONS.find(({ pattern }) => pattern.test(prompt))?.reaction ?? null;
}
