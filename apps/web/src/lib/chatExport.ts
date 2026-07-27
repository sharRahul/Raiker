export interface ExportTurn {
  prompt: string;
  answer: string;
}

/** Build a portable, human-readable transcript without runtime metadata. */
export function chatAsMarkdown(turns: ExportTurn[], title = "Raiker chat"): string {
  const sections = turns.flatMap((turn) => [
    `## You\n\n${turn.prompt.trim() || "_(No prompt text)_"}`,
    `## Raiker\n\n${turn.answer.trim() || "_(No answer text was returned.)_"}`,
  ]);
  return [`# ${title}`, ...sections].join("\n\n") + "\n";
}

export function markdownFilename(date = new Date()): string {
  return `raiker-chat-${date.toISOString().slice(0, 10)}.md`;
}
