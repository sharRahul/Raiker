import { describe, expect, it } from "vitest";

import { CONVERSATION_SUMMARY_CHARS, memoriesFromConversationExport, memoriesFromText } from "./memoryImportText";

describe("memoriesFromText (RU-16)", () => {
  it("reads Hermes Agent's § entries", () => {
    const text = "Prefers metric units\n§\nWorks on the Raiker repository\nin Python\n§\n";
    expect(memoriesFromText(text).map((record) => record.text)).toEqual([
      "Prefers metric units",
      "Works on the Raiker repository in Python",
    ]);
  });

  it("reads a Markdown bullet list and leaves headings out", () => {
    const text = "# About me\n\n- Dentist is Dr. Okafor\n* Likes short replies\n1. Lives in Leeds\n";
    expect(memoriesFromText(text)).toEqual([
      { text: "Dentist is Dr. Okafor", scope: "user" },
      { text: "Likes short replies", scope: "user" },
      { text: "Lives in Leeds", scope: "user" },
    ]);
  });

  it("falls back to paragraphs, without duplicates or empty entries", () => {
    expect(memoriesFromText("One fact.\n\nOne fact.\n\n\n").map((record) => record.text)).toEqual(["One fact."]);
  });
});

describe("memoriesFromConversationExport (RU-16)", () => {
  it("reads a ChatGPT conversations.json as one record per conversation, from its first user message", () => {
    const exported = [
      {
        title: "Trip to Kyoto",
        create_time: 1767225600,
        mapping: {
          a: { message: { author: { role: "system" }, content: { parts: ["You are ChatGPT"] }, create_time: 1 } },
          c: { message: { author: { role: "user" }, content: { parts: ["And hotels?"] }, create_time: 3 } },
          b: { message: { author: { role: "user" }, content: { parts: ["Plan  a\nweek in Kyoto in April"] }, create_time: 2 } },
          d: { message: null },
        },
      },
    ];
    expect(memoriesFromConversationExport(exported)).toEqual([
      { text: "From ChatGPT, “Trip to Kyoto” (2026-01-01): Plan a week in Kyoto in April", scope: "user" },
    ]);
  });

  it("reads a Claude conversations.json from the first human message, text or content blocks", () => {
    const exported = [
      { name: "Tax questions", created_at: "2026-03-02T10:00:00Z", chat_messages: [{ sender: "human", text: "", content: [{ type: "text", text: "I file in India." }] }] },
      { name: "", created_at: "bad", chat_messages: [{ sender: "assistant", text: "Hello" }, { sender: "human", text: "Remember I prefer metric." }] },
      { name: "Empty", chat_messages: [] },
    ];
    expect(memoriesFromConversationExport(exported)).toEqual([
      { text: "From Claude, “Tax questions” (2026-03-02): I file in India.", scope: "user" },
      { text: "From Claude, a conversation: Remember I prefer metric.", scope: "user" },
    ]);
  });

  it("clips a long opening and ignores files that are not an export", () => {
    const long = "x".repeat(CONVERSATION_SUMMARY_CHARS + 50);
    const [only] = memoriesFromConversationExport([{ name: "Long", chat_messages: [{ sender: "human", text: long }] }]) ?? [];
    expect(only.text.endsWith("…")).toBe(true);
    expect(memoriesFromConversationExport([{ text: "a Raiker memory", scope: "user" }])).toBeNull();
    expect(memoriesFromConversationExport({ memories: [] })).toBeNull();
    expect(memoriesFromConversationExport([])).toBeNull();
  });
});
