import { describe, expect, it } from "vitest";

import { noteToMarkdown, openLinkQuery, parseLinkBody, radialLayout, suggestNotes } from "./notes";

describe("Raiker Notes syntax", () => {
  it("parses a wikilink body", () => {
    expect(parseLinkBody("Design#Goals|the goals")).toEqual({ target: "Design", heading: "Goals", alias: "the goals", embed: false });
    expect(parseLinkBody("Note#^block-1").heading).toBe("block-1");
  });

  it("turns wikilinks, embeds and tags into in-app links and drops properties", () => {
    const md = noteToMarkdown("---\ntags: [a]\n---\nSee [[Design#Goals|goals]] and ![[Diagram]] #idea ^b-1\n```\n[[code]]\n```");
    expect(md).not.toContain("tags:");
    expect(md).toContain("[goals](#/notes?note=Design&heading=Goals)");
    expect(md).toContain("[↳ Diagram](#/notes?note=Diagram)");
    expect(md).toContain("[#idea](#/notes?search=tag%3Aidea)");
    expect(md).not.toContain("^b-1");
    expect(md).toContain("[[code]]");
  });

  it("knows when the caret is inside an open [[", () => {
    expect(openLinkQuery("See [[Rai", 9)).toEqual({ start: 6, query: "Rai" });
    expect(openLinkQuery("See [[Raiker]] x", 16)).toBeNull();
  });

  it("suggests notes best match first", () => {
    expect(suggestNotes(["Ideas", "Raiker", "Projects/Raiker app", "Brainstorm"], "rai")).toEqual(["Raiker", "Projects/Raiker app", "Brainstorm"]);
  });

  it("lays a local graph out around its note", () => {
    const layout = radialLayout("a", ["a", "b", "c"], 200);
    expect(layout.a).toEqual({ x: 100, y: 100 });
    expect(Object.keys(layout)).toHaveLength(3);
  });
});
