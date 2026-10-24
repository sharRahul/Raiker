import { describe, expect, it } from "vitest";

import { correctionToRemember } from "./corrections";

describe("QUI-F20 corrections become memory", () => {
  it("offers the owner's own words after a correction", () => {
    expect(correctionToRemember("That's wrong — Anna prefers short replies.")).toBe("Anna prefers short replies.");
    expect(correctionToRemember("No, the meeting is on Tuesday now")).toBe("The meeting is on Tuesday now");
    expect(correctionToRemember("Actually, use metric units everywhere")).toBe("Use metric units everywhere");
  });

  it("offers only the correction, not the instruction after it (found live)", async () => {
    const { rememberQuestion } = await import("./corrections");
    const text = correctionToRemember("That's wrong — Anna prefers short replies. Reply with one short sentence acknowledging it.");
    expect(text).toBe("Anna prefers short replies.");
    expect(rememberQuestion(text ?? "")).toBe("Anna prefers short replies?");
  });

  it("says nothing for an ordinary message or a bare no", () => {
    expect(correctionToRemember("Summarise this document")).toBeNull();
    expect(correctionToRemember("No.")).toBeNull();
    expect(correctionToRemember("Nothing else, thanks")).toBeNull();
    expect(correctionToRemember("Notice the dates")).toBeNull();
  });
});
