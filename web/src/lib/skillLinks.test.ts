// Spotting a skill link in composer text. The detector deliberately refuses to
// guess: only HTTPS links on the published-skill hosts, whose own path names a
// skill, are offered — the server still decides whether the document is real.
import { describe, expect, it } from "vitest";
import { findSkillLinks, isArchiveLink, skillLinkLabel } from "./skillLinks";

describe("findSkillLinks", () => {
  it("finds a raw SKILL.md link", () => {
    expect(
      findSkillLinks("try https://raw.githubusercontent.com/o/r/main/skills/tidy/SKILL.md please"),
    ).toEqual(["https://raw.githubusercontent.com/o/r/main/skills/tidy/SKILL.md"]);
  });

  it("finds a GitHub blob link inside a skills folder", () => {
    expect(findSkillLinks("https://github.com/o/r/blob/main/skills/tidy/SKILL.md")).toHaveLength(1);
  });

  it("finds a .skill bundle link", () => {
    expect(findSkillLinks("https://github.com/o/r/raw/main/opus-mode.skill")).toEqual([
      "https://github.com/o/r/raw/main/opus-mode.skill",
    ]);
  });

  it("ignores an ordinary repository link", () => {
    expect(findSkillLinks("see https://github.com/o/r for context")).toEqual([]);
  });

  it("ignores a skill-looking link on another host", () => {
    expect(findSkillLinks("https://example.com/skills/tidy/SKILL.md")).toEqual([]);
  });

  it("ignores plain http", () => {
    expect(findSkillLinks("http://raw.githubusercontent.com/o/r/main/SKILL.md")).toEqual([]);
  });

  it("strips trailing sentence punctuation", () => {
    expect(findSkillLinks("install https://github.com/o/r/blob/main/skills/a/SKILL.md.")).toEqual([
      "https://github.com/o/r/blob/main/skills/a/SKILL.md",
    ]);
  });

  it("returns each distinct link once, in order", () => {
    const text = `
      https://github.com/o/r/blob/main/skills/a/SKILL.md
      https://github.com/o/r/blob/main/skills/a/SKILL.md
      https://github.com/o/r/blob/main/skills/b/SKILL.md
    `;
    expect(findSkillLinks(text)).toEqual([
      "https://github.com/o/r/blob/main/skills/a/SKILL.md",
      "https://github.com/o/r/blob/main/skills/b/SKILL.md",
    ]);
  });

  it("survives text with no links at all", () => {
    expect(findSkillLinks("no links here")).toEqual([]);
  });
});

describe("isArchiveLink", () => {
  it("is true for a .skill bundle", () => {
    expect(isArchiveLink("https://github.com/o/r/raw/main/opus-mode.skill")).toBe(true);
  });

  it("is false for a document", () => {
    expect(isArchiveLink("https://raw.githubusercontent.com/o/r/main/skills/a/SKILL.md")).toBe(
      false,
    );
  });
});

describe("skillLinkLabel", () => {
  it("names a SKILL.md by its folder", () => {
    expect(skillLinkLabel("https://raw.githubusercontent.com/o/r/main/skills/tidy/SKILL.md")).toBe(
      "tidy",
    );
  });

  it("names a bundle by its filename", () => {
    expect(skillLinkLabel("https://github.com/o/r/raw/main/opus-mode.skill")).toBe(
      "opus-mode.skill",
    );
  });
});
