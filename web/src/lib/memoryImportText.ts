/**
 * RU-16 — memories written for another agent, read as records to review.
 *
 * Hermes Agent keeps `MEMORY.md` and `USER.md` as entries separated by a line
 * holding `§`; Claude Code's and Cursor's notes are Markdown bullet lists. Each
 * entry becomes one record with `scope: "user"`, shown in Memory's import review
 * where the owner keeps or skips it — nothing is stored before Import.
 * Headings, empty entries and anything over the per-record limit are left out.
 */
export const MAX_IMPORTED_TEXT = 2000;
const SECTION = /^\s*§\s*$/m;
const BULLET = /^\s*(?:[-*+]|\d+[.)])\s+(.*)$/;

export function memoriesFromText(text: string): { text: string; scope: string }[] {
  const body = text.replace(/\r\n?/g, "\n").replace(/^\uFEFF/, "");
  let entries: string[];
  if (SECTION.test(body)) {
    entries = body.split(SECTION);
  } else if (body.split("\n").some((line) => BULLET.test(line))) {
    entries = body
      .split("\n")
      .map((line) => BULLET.exec(line)?.[1] ?? "")
      .filter(Boolean);
  } else {
    entries = body.split(/\n\s*\n/);
  }
  const seen = new Set<string>();
  const records: { text: string; scope: string }[] = [];
  for (const entry of entries) {
    const cleaned = entry
      .split("\n")
      .filter((line) => !/^\s*#/.test(line))
      .join(" ")
      .replace(/\s+/g, " ")
      .trim();
    if (!cleaned || cleaned.length > MAX_IMPORTED_TEXT || seen.has(cleaned)) continue;
    seen.add(cleaned);
    records.push({ text: cleaned, scope: "user" });
  }
  return records;
}

/** How much of a conversation's opening request one record keeps. */
export const CONVERSATION_SUMMARY_CHARS = 300;

type Record_ = { text: string; scope: string };

function clip(text: string): string {
  const flat = text.replace(/\s+/g, " ").trim();
  return flat.length > CONVERSATION_SUMMARY_CHARS ? `${flat.slice(0, CONVERSATION_SUMMARY_CHARS - 1).trimEnd()}…` : flat;
}

function day(value: unknown): string {
  const ms = typeof value === "number" ? value * 1000 : typeof value === "string" ? Date.parse(value) : NaN;
  return Number.isFinite(ms) ? new Date(ms).toISOString().slice(0, 10) : "";
}

function record(source: string, title: unknown, when: unknown, opening: string): Record_ | null {
  const said = clip(opening);
  if (!said) return null;
  const name = typeof title === "string" && title.trim() ? `“${title.trim()}”` : "a conversation";
  const date = day(when);
  return { text: `From ${source}, ${name}${date ? ` (${date})` : ""}: ${said}`, scope: "user" };
}

/** ChatGPT's first user message: the earliest `user` node in the mapping. */
function chatgptOpening(mapping: Record<string, unknown>): string {
  const turns: { at: number; text: string }[] = [];
  for (const node of Object.values(mapping)) {
    const message = (node as { message?: Record<string, unknown> } | null)?.message;
    const role = (message?.author as { role?: unknown } | undefined)?.role;
    const parts = (message?.content as { parts?: unknown } | undefined)?.parts;
    if (role !== "user" || !Array.isArray(parts)) continue;
    const text = parts.filter((p): p is string => typeof p === "string").join(" ");
    if (text.trim()) turns.push({ at: typeof message?.create_time === "number" ? message.create_time : 0, text });
  }
  turns.sort((a, b) => a.at - b.at);
  return turns[0]?.text ?? "";
}

/** Claude's first human message: `text`, or its text content blocks. */
function claudeOpening(messages: unknown[]): string {
  for (const raw of messages) {
    const message = raw as { sender?: unknown; text?: unknown; content?: unknown };
    if (message?.sender !== "human") continue;
    if (typeof message.text === "string" && message.text.trim()) return message.text;
    if (Array.isArray(message.content)) {
      const text = message.content
        .map((block) => (block as { text?: unknown })?.text)
        .filter((t): t is string => typeof t === "string")
        .join(" ");
      if (text.trim()) return text;
    }
  }
  return "";
}

/**
 * RU-16 — a ChatGPT or Claude data export's `conversations.json`, read as one
 * record per conversation to review: where it came from, its title and day,
 * and what was first asked. Nothing is stored before Import, and the owner
 * keeps only the ones worth remembering. `null` when the file is neither.
 */
export function memoriesFromConversationExport(parsed: unknown): Record_[] | null {
  if (!Array.isArray(parsed) || parsed.length === 0) return null;
  const first = parsed[0] as Record<string, unknown> | null;
  const isChatgpt = typeof first === "object" && first !== null && typeof first.mapping === "object";
  const isClaude = typeof first === "object" && first !== null && Array.isArray(first.chat_messages);
  if (!isChatgpt && !isClaude) return null;
  const seen = new Set<string>();
  const records: Record_[] = [];
  for (const raw of parsed) {
    const conversation = raw as Record<string, unknown> | null;
    if (typeof conversation !== "object" || conversation === null) continue;
    const made = isChatgpt
      ? typeof conversation.mapping === "object" && conversation.mapping !== null
        ? record("ChatGPT", conversation.title, conversation.create_time, chatgptOpening(conversation.mapping as Record<string, unknown>))
        : null
      : Array.isArray(conversation.chat_messages)
        ? record("Claude", conversation.name, conversation.created_at, claudeOpening(conversation.chat_messages))
        : null;
    if (made && !seen.has(made.text)) {
      seen.add(made.text);
      records.push(made);
    }
  }
  return records;
}
