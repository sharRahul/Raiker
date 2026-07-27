import { describe, expect, it } from "vitest";
import { chatAsMarkdown, markdownFilename } from "./chatExport";

describe("chat export", () => {
  it("preserves prompts and Markdown answers in transcript order", () => {
    expect(chatAsMarkdown([
      { prompt: "Summarise this", answer: "- First\n- Second" },
      { prompt: "And the gap?", answer: "" },
    ])).toBe(
      "# Raiker chat\n\n## You\n\nSummarise this\n\n## Raiker\n\n- First\n- Second\n\n" +
      "## You\n\nAnd the gap?\n\n## Raiker\n\n_(No answer text was returned.)_\n",
    );
  });

  it("uses a stable, filesystem-safe dated filename", () => {
    expect(markdownFilename(new Date("2026-07-27T22:30:00Z"))).toBe("raiker-chat-2026-07-27.md");
  });
});
