import { describe, expect, it } from "vitest";
import { workDraft } from "./workDraft.svelte";
describe("project composer drafts", () => {
  it("shares exact text across modes and isolates project boundaries", () => {
    const chat = workDraft("a");
    chat.text = "Keep draft\nwith whitespace  ";
    expect(workDraft("a").text).toBe(chat.text);
    expect(workDraft("b").text).toBe("");
    workDraft("a").text = "Edited in Build";
    expect(chat.text).toBe("Edited in Build");
    workDraft("a").text = "";
    expect(chat.text).toBe("");
  });
});
