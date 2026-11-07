import { describe, expect, it } from "vitest";
import { MAX_PIN_CHARS, addPin, withPins } from "./promptPins";

describe("Add to prompt (QUI-C04)", () => {
  it("quotes each pinned answer above what was typed", () => {
    const sent = withPins("Shorten this.", [{ turnId: "t1", label: "Answer 1", text: "Line one\nLine two" }]);
    expect(sent).toBe("Context from answer 1 in this conversation:\n> Line one\n> Line two\n\nShorten this.");
  });
  it("leaves a prompt with no pins unchanged and never pins one answer twice", () => {
    expect(withPins("Hi", [])).toBe("Hi");
    const pin = { turnId: "t1", label: "Answer 1", text: "x" };
    expect(addPin(addPin([], pin), pin)).toHaveLength(1);
  });
  it("cuts a very long answer and says so", () => {
    const sent = withPins("Go", [{ turnId: "t1", label: "Answer 1", text: "a".repeat(MAX_PIN_CHARS + 50) }]);
    expect(sent).toContain(`[…cut at ${MAX_PIN_CHARS} characters]`);
  });
});
