/**
 * MEM-MODE-02 — the owner's ambient-recall mode, and how a turn says which one
 * it ran under.
 *
 * The server decides; this module only words it. `recall_mode` is the owner's
 * setting and `effective_mode` is what actually ran — Incognito turns any mode
 * into `off` — so the transcript reads the second and names the first only when
 * they differ.
 */
import type { TurnMemoryDisclosure } from "./apiTypes";

export type MemoryRecallMode = "off" | "brief" | "search_when_relevant";

export interface RecallModeOption {
  value: MemoryRecallMode;
  label: string;
  detail: string;
}

export const RECALL_MODE_OPTIONS: readonly RecallModeOption[] = [
  {
    value: "off",
    label: "Off",
    detail: "No memory is added to a turn on its own. You can still ask Raiker to look something up.",
  },
  {
    value: "brief",
    label: "Brief only",
    detail: "A short, fixed brief of your approved memories joins every turn. Nothing is searched.",
  },
  {
    value: "search_when_relevant",
    label: "Search when relevant",
    detail: "The brief, plus approved memories, files and earlier chats that match what you asked.",
  },
];

export function recallModeLabel(mode: string): string {
  return RECALL_MODE_OPTIONS.find((option) => option.value === mode)?.label ?? "Off";
}

/**
 * The backend in words. The server sends the parts it used joined with ` + `
 * (`memory-brief-v1 + sqlite-fts5 + raiker-local-hash-v1`); the brief is named
 * by the mode already, so only the search parts are listed.
 */
export function retrievalBackendLabel(backend: string): string {
  if (!backend || backend === "none") return "nothing";
  const parts = backend
    .split("+")
    .map((part) => part.trim())
    .filter((part) => part !== "" && !part.startsWith("memory-brief-"));
  return parts.length === 0 ? "the memory brief" : parts.join(" + ");
}

/** One quiet line saying what memory this answer was given. */
export function disclosureSummary(disclosure: TurnMemoryDisclosure): string {
  if (disclosure.effective_mode === "off") {
    return disclosure.incognito ? "Memory not used: Incognito is on" : "Memory off for this answer";
  }
  return disclosure.effective_mode === "brief" ? "Memory: Brief only" : "Memory: Brief + search";
}

/** The mode in two words, for beside the "Remembered" count. */
export function disclosureShort(disclosure: TurnMemoryDisclosure): string {
  if (disclosure.effective_mode === "off") return disclosure.incognito ? "Incognito" : "Memory off";
  return disclosure.effective_mode === "brief" ? "Brief only" : "Brief + search";
}

/** The expanded detail: the mode, the backend, and what the budget left out. */
export function disclosureDetail(disclosure: TurnMemoryDisclosure): string {
  const parts = [`Recall mode: ${recallModeLabel(disclosure.recall_mode)}`];
  if (disclosure.incognito) parts.push("Incognito on, so nothing was recalled");
  if (disclosure.effective_mode === "search_when_relevant") {
    parts.push(`searched ${retrievalBackendLabel(disclosure.retrieval_backend)}`);
  } else if (disclosure.effective_mode === "brief") {
    parts.push("no search");
  }
  if (disclosure.brief_omitted > 0) {
    parts.push(`${disclosure.brief_omitted} approved ${disclosure.brief_omitted === 1 ? "memory" : "memories"} left out of the brief by its budget`);
  }
  return parts.join(" · ");
}

/**
 * The line under an answer that recalled nothing: what ran and what it
 * searched, so "nothing matched" is never mistaken for "memory is off".
 */
export function quietDisclosure(disclosure: TurnMemoryDisclosure): string {
  const summary = disclosureSummary(disclosure);
  if (disclosure.effective_mode === "off") return summary;
  if (disclosure.effective_mode === "brief") return `${summary} · nothing recalled`;
  return `${summary} · nothing recalled · searched ${retrievalBackendLabel(disclosure.retrieval_backend)}`;
}
