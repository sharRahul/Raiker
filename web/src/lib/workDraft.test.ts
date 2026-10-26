import { describe, expect, it } from "vitest";
import { workDraft } from "./workDraft.svelte";

describe("composer drafts", () => {
  it("preserves separate drafts for each workspace and project", () => {
    const chat = workDraft("a", "chat");
    chat.text = "Keep draft\nwith whitespace  ";
    workDraft("a", "build").text = "Build draft";
    workDraft("a", "design").text = "Design draft";
    expect(workDraft("a", "chat").text).toBe("Keep draft\nwith whitespace  ");
    expect(workDraft("a", "build").text).toBe("Build draft");
    expect(workDraft("a", "design").text).toBe("Design draft");
    expect(workDraft("b", "chat").text).toBe("");
  });
});
