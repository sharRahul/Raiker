import { describe, expect, it } from "vitest";

import { ownerQuestions, previewFor } from "./clarify";

const approval = (options: unknown[]) => ({
  tool_name: "ask_owner_question",
  arguments: { questions: [{ question: "Which?", header: "Pick", options }] },
});

describe("TOOL-08 recommended option and previews", () => {
  it("keeps one recommendation and an option's preview", () => {
    const [question] = ownerQuestions(
      approval([
        { label: "A", description: "a", recommended: true, preview: "code A" },
        { label: "B", description: "b", preview: "  " },
      ]),
    )!;
    expect(question.options[0]).toEqual({ label: "A", description: "a", recommended: true, preview: "code A" });
    expect(question.options[1]).toEqual({ label: "B", description: "b" });
  });

  it("drops the tags when more than one option claims to be recommended", () => {
    const [question] = ownerQuestions(
      approval([
        { label: "A", description: "a", recommended: true },
        { label: "B", description: "b", recommended: true },
      ]),
    )!;
    expect(question.options.some((option) => option.recommended)).toBe(false);
  });

  it("shows the preview of the last option picked, and none before a pick", () => {
    const [question] = ownerQuestions(
      approval([
        { label: "A", description: "a", preview: "code A" },
        { label: "B", description: "b", preview: "code B" },
        { label: "C", description: "c" },
      ]),
    )!;
    expect(previewFor(question, [])).toBeNull();
    expect(previewFor(question, ["A", "B"])).toBe("code B");
    expect(previewFor(question, ["A", "C"])).toBe("code A");
  });
});
