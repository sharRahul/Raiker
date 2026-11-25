import { describe, expect, it } from "vitest";

import { memoriesFromText } from "./memoryImportText";

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
