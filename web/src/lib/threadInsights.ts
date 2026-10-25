/**
 * TOOL-131 — `/insights`: what this thread used and cost, from records only.
 *
 * The figures come from the turns already on screen (their tool rows) and the
 * conversation's own usage ledger (`GET /api/sessions/{id}/context-usage`).
 * Nothing is estimated here: a cost the ledger cannot price reads as unknown,
 * never as zero.
 */
import { toolActivity } from "./chatPresentation";
import { formatCost } from "./contextPresentation";
import type { ContextUsage, StreamEvent } from "./apiTypes";

export interface ThreadInsights {
  /** Exchanges in this conversation: one per prompt the owner sent. */
  turns: number;
  /** Model calls the ledger recorded; a turn that used tools makes several. */
  modelCalls: number | null;
  toolCalls: number;
  /** Tool labels by how often they ran, most used first; at most six. */
  topTools: { label: string; count: number }[];
  /** Calls that ended refused, denied or failed. */
  notDone: number;
  /** Calls that waited on an owner decision. */
  asked: number;
  model: string | null;
  inputTokens: number | null;
  outputTokens: number | null;
  /** The ledger's cost, with its currency, or null when it is not priced. */
  cost: string | null;
}

export function threadInsights(
  turns: readonly { events: StreamEvent[] }[],
  usage: ContextUsage | null,
): ThreadInsights {
  const counts = new Map<string, number>();
  let toolCalls = 0;
  let notDone = 0;
  let asked = 0;
  for (const turn of turns) {
    for (const row of toolActivity(turn.events)) {
      toolCalls += 1;
      counts.set(row.label, (counts.get(row.label) ?? 0) + 1);
      if (row.state === "failed" || row.state === "denied" || row.state === "refused") notDone += 1;
      if (row.state === "waiting") asked += 1;
    }
  }
  const topTools = [...counts.entries()]
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label))
    .slice(0, 6);
  const priced = usage?.session_cost && !usage.price_unknown;
  return {
    turns: turns.length,
    modelCalls: usage ? usage.session_turns : null,
    toolCalls,
    topTools,
    notDone,
    asked,
    model: usage?.model ?? null,
    inputTokens: usage ? usage.session_input_tokens : null,
    outputTokens: usage ? usage.session_output_tokens : null,
    cost: priced ? (formatCost(usage.session_cost, usage.currency) ?? `${usage.session_cost} ${usage.currency ?? ""}`.trim()) : null,
  };
}

/** The latest turn the server knows by id, which `/compress` summarises through. */
export function latestSettledTurnId(
  turns: readonly { streaming: boolean; response: { turn_id: string } | null }[],
): string | null {
  for (let index = turns.length - 1; index >= 0; index -= 1) {
    const turn = turns[index];
    if (!turn.streaming && turn.response?.turn_id) return turn.response.turn_id;
  }
  return null;
}

/** What the composer says after `/compress`, from the compaction route's answer. */
export function compressNotice(result: { compacted: boolean; source_turn_count?: number; reason_code?: string | null }): string {
  if (result.compacted) {
    const count = result.source_turn_count ?? 0;
    return `Summarised ${count} earlier ${count === 1 ? "exchange" : "exchanges"} for the model. Nothing was removed from this transcript.`;
  }
  return result.reason_code === "nothing_to_summarise"
    ? "Everything up to that point is already summarised."
    : `That range could not be summarised (${result.reason_code ?? "unknown"}).`;
}
